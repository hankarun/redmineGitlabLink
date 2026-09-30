"""Turning submitted form fields into a valid Rule.

Kept apart from both the web layer and the repository: parsing and checking
user input is its own reason to change.
"""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass
from typing import Mapping

from .models import Rule

FIELDS = ("name", "project", "branches", "secret", "issue_pattern", "template")
MIN_SECRET_LENGTH = 12


@dataclass
class RuleForm:
    name: str = ""
    project: str = ""
    branches: str = ""
    secret: str = ""
    issue_pattern: str = ""
    template: str = ""
    enabled: bool = True

    @classmethod
    def blank(cls) -> "RuleForm":
        return cls(secret=secrets.token_urlsafe(24))

    @classmethod
    def of(cls, rule: Rule) -> "RuleForm":
        return cls(**{f: getattr(rule, f) for f in FIELDS}, enabled=rule.enabled)

    @classmethod
    def submitted(cls, form: Mapping[str, str]) -> "RuleForm":
        return cls(**{f: form.get(f, "").strip() for f in FIELDS},
                   enabled=bool(form.get("enabled")))

    def errors(self) -> list[str]:
        found = []
        if not self.name:
            found.append("Name is required.")
        if len(self.secret) < MIN_SECRET_LENGTH:
            found.append(f"Secret token must be at least {MIN_SECRET_LENGTH} characters.")
        rule = self.to_rule()
        if self.issue_pattern:
            found.append(rule.issue_extractor.error())
        if self.template:
            found.append(rule.note_template.error())
        return [e for e in found if e]

    def to_rule(self, rule_id: int | None = None) -> Rule:
        return Rule(id=rule_id, **asdict(self))
