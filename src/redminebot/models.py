"""Domain objects.

These know nothing about sqlite, HTTP or Flask; they are what the rest of the
service reasons about, which keeps the interesting logic trivially testable.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any, Mapping

from .notes import IssueReferenceExtractor, NoteTemplate


@dataclass(frozen=True)
class PatternList:
    """Comma/newline separated fnmatch patterns. Empty means "match anything"."""

    raw: str = ""

    @property
    def patterns(self) -> list[str]:
        return [p.strip() for p in (self.raw or "").replace("\n", ",").split(",") if p.strip()]

    def matches(self, value: str) -> bool:
        patterns = self.patterns
        return not patterns or any(fnmatch.fnmatchcase(value, p) for p in patterns)


@dataclass(frozen=True)
class Outcome:
    """Result of an operation that is expected to fail sometimes."""

    ok: bool
    detail: str = ""

    @classmethod
    def success(cls, detail: str = "") -> "Outcome":
        return cls(True, detail)

    @classmethod
    def failure(cls, detail: str) -> "Outcome":
        return cls(False, detail)


@dataclass(frozen=True)
class RedmineCredentials:
    url: str = ""
    api_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.api_key)


@dataclass(frozen=True)
class SummarySettings:
    """Which summarizer the admin picked, if any."""

    provider: str = "none"
    model: str = ""
    endpoint: str = ""

    @property
    def enabled(self) -> bool:
        return self.provider not in ("", "none")


@dataclass(frozen=True)
class Commit:
    sha: str = ""
    message: str = ""
    url: str = ""
    author: str = "unknown"

    @property
    def short_sha(self) -> str:
        return self.sha[:8]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Commit":
        return cls(
            sha=payload.get("id", ""),
            message=payload.get("message", ""),
            url=payload.get("url", ""),
            author=(payload.get("author") or {}).get("name", "unknown"),
        )


@dataclass(frozen=True)
class PushEvent:
    """A GitLab push, translated out of webhook JSON once, at the edge."""

    project: str
    branch: str
    commits: tuple[Commit, ...] = ()
    total_commits: int = 0

    BRANCH_PREFIX = "refs/heads/"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PushEvent | None":
        """None when this is not a push to a branch (tag pushes, deletions...)."""
        ref = payload.get("ref", "")
        if not ref.startswith(cls.BRANCH_PREFIX):
            return None
        return cls(
            project=(payload.get("project") or {}).get("path_with_namespace", ""),
            branch=ref[len(cls.BRANCH_PREFIX):],
            commits=tuple(Commit.from_payload(c) for c in payload.get("commits", [])),
            total_commits=payload.get("total_commits_count", 0),
        )

    @property
    def dropped_commits(self) -> int:
        """GitLab only sends the latest commits of a large push."""
        return max(0, self.total_commits - len(self.commits))


@dataclass(frozen=True)
class Rule:
    """Which pushes to act on, and what to say about them."""

    name: str
    secret: str
    id: int | None = None
    project: str = ""
    branches: str = ""
    issue_pattern: str = ""
    template: str = ""
    enabled: bool = True
    created_at: str = ""

    def accepts(self, project: str, branch: str) -> bool:
        return (PatternList(self.project).matches(project)
                and PatternList(self.branches).matches(branch))

    @property
    def issue_extractor(self) -> IssueReferenceExtractor:
        return IssueReferenceExtractor(self.issue_pattern)

    @property
    def note_template(self) -> NoteTemplate:
        return NoteTemplate(self.template)


@dataclass(frozen=True)
class ActivityEntry:
    """One line in the activity log."""

    rule_name: str = "—"
    project: str = ""
    branch: str = ""
    sha: str = ""
    commit_url: str = ""
    issue: int | None = None
    status: str = ""
    detail: str = ""
    ts: str = ""
    id: int | None = None


@dataclass(frozen=True)
class AssistantSettings:
    """The @mention assistant, as configured in the admin UI."""

    enabled: bool = False
    handle: str = "@claude"
    model: str = ""
    since: str = ""   # mentions older than this (UTC, ISO) are never answered
    cursor: str = ""  # Redmine updated_on of the newest issue already polled


@dataclass(frozen=True)
class CodeProject:
    """Where the source code of a Redmine project lives on this host."""

    redmine_project: str
    code_path: str
    id: int | None = None
    enabled: bool = True
    created_at: str = ""


@dataclass(frozen=True)
class Journal:
    """One comment (Redmine calls them journals) on an issue."""

    id: int
    author_id: int | None = None
    author: str = ""
    notes: str = ""
    created_on: str = ""
    private: bool = False

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Journal":
        user = payload.get("user") or {}
        return cls(
            id=payload.get("id", 0),
            author_id=user.get("id"),
            author=user.get("name", ""),
            notes=payload.get("notes") or "",
            created_on=payload.get("created_on", ""),
            private=bool(payload.get("private_notes")),
        )


@dataclass(frozen=True)
class Issue:
    id: int
    subject: str = ""
    description: str = ""
    project: str = ""
    tracker: str = ""
    status: str = ""
    updated_on: str = ""
    journals: tuple[Journal, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Issue":
        return cls(
            id=payload.get("id", 0),
            subject=payload.get("subject", ""),
            description=payload.get("description") or "",
            project=(payload.get("project") or {}).get("name", ""),
            tracker=(payload.get("tracker") or {}).get("name", ""),
            status=(payload.get("status") or {}).get("name", ""),
            updated_on=payload.get("updated_on", ""),
            journals=tuple(Journal.from_payload(j) for j in payload.get("journals", [])),
        )
