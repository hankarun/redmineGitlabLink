"""The actual job: given a push and the rules that matched it, comment on issues.

Depends only on the protocols in ``trackers`` and on the repositories, so it can
be exercised with fakes and has no idea a web framework is involved.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from .models import ActivityEntry, PushEvent, Rule

log = logging.getLogger("gitlab-redmine")


class PushProcessor:
    def __init__(self, trackers, posted, activity, summarizers=None,
                 logger: logging.Logger = log) -> None:
        self._trackers = trackers
        self._summarizers = summarizers
        self._posted = posted
        self._activity = activity
        self._log = logger

    def process(self, push: PushEvent, rules: list[Rule]) -> None:
        tracker = self._trackers.create()
        summary = self._summarize(push, rules)
        for commit in push.commits:
            for issue, rule in sorted(self._targets(commit, rules).items()):
                self._link(tracker, push, commit, issue, rule, summary)
        self._warn_if_truncated(push, rules)

    def _summarize(self, push: PushEvent, rules: list[Rule]) -> str:
        """Summarize the push once, and only if some matched rule wants it."""
        if not self._summarizers or not any(r.note_template.wants_summary for r in rules):
            return ""
        outcome = self._summarizers.create().summarize(push)
        if outcome.ok:
            return outcome.detail
        if outcome.detail:  # the off switch reports no detail; real errors do
            self._log.warning("Could not summarize push to %s: %s", push.project, outcome.detail)
            self._activity.record(ActivityEntry(
                rule_name=rules[0].name, project=push.project, branch=push.branch,
                status="warning", detail=f"Could not summarize the push: {outcome.detail}"))
        return ""

    @staticmethod
    def _targets(commit, rules: list[Rule]) -> dict[int, Rule]:
        """Issue number -> the first rule that claimed it."""
        targets: dict[int, Rule] = {}
        for rule in rules:
            for issue in rule.issue_extractor.extract(commit.message):
                targets.setdefault(issue, rule)
        return targets

    def _link(self, tracker, push: PushEvent, commit, issue: int, rule: Rule,
              summary: str = "") -> None:
        entry = ActivityEntry(rule_name=rule.name, project=push.project, branch=push.branch,
                              sha=commit.sha, commit_url=commit.url, issue=issue)

        if self._posted.contains(commit.sha, issue):
            self._activity.record(_with(entry, "skipped",
                                        "Already linked earlier (e.g. pushed to another branch)"))
            return

        note = rule.note_template.render(commit, push.project, push.branch, summary)
        outcome = tracker.add_note(issue, note)
        if outcome.ok:
            self._posted.record(commit.sha, issue)
            self._log.info("Linked %s to Redmine #%s", commit.short_sha, issue)
        else:
            self._log.warning("Failed %s -> #%s: %s", commit.short_sha, issue, outcome.detail)
        self._activity.record(_with(entry, "posted" if outcome.ok else "failed", outcome.detail))

    def _warn_if_truncated(self, push: PushEvent, rules: list[Rule]) -> None:
        if not push.dropped_commits:
            return
        self._activity.record(ActivityEntry(
            rule_name=rules[0].name, project=push.project, branch=push.branch, status="warning",
            detail=f"Push had {push.total_commits} commits; "
                   f"GitLab only sent the latest {len(push.commits)}"))


def _with(entry: ActivityEntry, status: str, detail: str) -> ActivityEntry:
    return replace(entry, status=status, detail=detail)
