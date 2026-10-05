"""Reading issue references out of commit messages, and writing the note that
goes back to the tracker.

Both are strategies a rule picks: change the pattern or the template and the
rest of the service is untouched.
"""

from __future__ import annotations

import re

DEFAULT_PATTERN = r"(?<![\w&])#(\d+)\b"
# After a match, further "#N" joined by commas, "&" or "and" belong to the same
# reference, so "Fixes #1, #2 and #3" works with keyword patterns too.
LIST_CONTINUATION = re.compile(r"\s*(?:,|&|\band\b)?\s*#(\d+)\b", re.IGNORECASE)
DEFAULT_TEMPLATE = (
    "Referenced in commit {short_sha} ({project}, branch {branch})\n"
    "{url}\n\n"
    "Author: {author}\n"
    "Message: {message}"
)


class LenientMapping(dict):
    """Leaves unknown placeholders alone instead of raising KeyError."""

    def __missing__(self, key):
        return "{" + key + "}"


class IssueReferenceExtractor:
    """Finds the issue numbers a commit message mentions."""

    def __init__(self, pattern: str = "") -> None:
        self.pattern = pattern or DEFAULT_PATTERN

    def extract(self, message: str) -> list[int]:
        message = message or ""
        found: dict[int, None] = {}  # ordered set
        for match in re.finditer(self.pattern, message, re.IGNORECASE):
            found[int(match.group(1))] = None
            pos = match.end()
            while follow := LIST_CONTINUATION.match(message, pos):
                found[int(follow.group(1))] = None
                pos = follow.end()
        return list(found)

    def error(self) -> str | None:
        """Why this pattern is unusable, or None when it is fine."""
        try:
            if re.compile(self.pattern).groups != 1:
                return "Issue pattern must have exactly one (group) capturing the issue number."
        except re.error as exc:
            return f"Issue pattern is not a valid regular expression: {exc}"
        return None


class NoteTemplate:
    """Renders the comment posted on an issue."""

    def __init__(self, template: str = "") -> None:
        self.template = template or DEFAULT_TEMPLATE

    @property
    def wants_summary(self) -> bool:
        """Templates opt in, so a push is only sent to a model when asked."""
        return "{summary}" in self.template

    def render(self, commit, project: str, branch: str, summary: str = "") -> str:
        message = (commit.message or "").strip()
        return self.template.format_map(LenientMapping(
            summary=summary,
            sha=commit.sha,
            short_sha=commit.short_sha,
            url=commit.url,
            author=commit.author,
            message=message.splitlines()[0] if message else "",
            full_message=message,
            project=project,
            branch=branch,
        ))

    def error(self) -> str | None:
        try:
            self.template.format_map(LenientMapping())
        except (ValueError, IndexError) as exc:
            return f"Comment template has a formatting error: {exc}"
        return None
