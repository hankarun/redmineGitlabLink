"""Stored collections, one class per thing that is stored.

Callers ask these for domain objects and never see a row or a SQL string, so
the rest of the service could be pointed at a different store unchanged.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Callable, Iterable

from .database import Database
from .models import (ActivityEntry, AssistantSettings, CodeProject, RedmineCredentials, Rule,
                     SummarySettings)

RULE_COLUMNS = ("name", "project", "branches", "secret", "issue_pattern", "template", "enabled")
LOG_KEEP = 5000


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _to_rule(row: sqlite3.Row) -> Rule:
    return Rule(
        id=row["id"], name=row["name"], secret=row["secret"],
        project=row["project"], branches=row["branches"],
        issue_pattern=row["issue_pattern"], template=row["template"],
        enabled=bool(row["enabled"]), created_at=row["created_at"] or "",
    )


class RuleRepository:
    def __init__(self, db: Database, clock: Callable[[], str] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def all(self) -> list[Rule]:
        return [_to_rule(r) for r in self._db.query("SELECT * FROM rules ORDER BY name COLLATE NOCASE")]

    def enabled(self) -> list[Rule]:
        return [_to_rule(r) for r in self._db.query("SELECT * FROM rules WHERE enabled=1")]

    def get(self, rule_id: int) -> Rule | None:
        row = self._db.query("SELECT * FROM rules WHERE id=?", (rule_id,), one=True)
        return _to_rule(row) if row else None

    def add(self, rule: Rule) -> int:
        placeholders = ", ".join("?" * len(RULE_COLUMNS))
        return self._db.execute(
            f"INSERT INTO rules ({', '.join(RULE_COLUMNS)}, created_at) VALUES ({placeholders}, ?)",
            self._values(rule) + (self._clock(),))

    def update(self, rule_id: int, rule: Rule) -> None:
        assignments = ", ".join(f"{c}=?" for c in RULE_COLUMNS)
        self._db.execute(f"UPDATE rules SET {assignments} WHERE id=?",
                         self._values(rule) + (rule_id,))

    def toggle(self, rule_id: int) -> None:
        self._db.execute("UPDATE rules SET enabled = 1 - enabled WHERE id=?", (rule_id,))

    def delete(self, rule_id: int) -> Rule | None:
        rule = self.get(rule_id)
        self._db.execute("DELETE FROM rules WHERE id=?", (rule_id,))
        return rule

    @staticmethod
    def _values(rule: Rule) -> tuple:
        return tuple(int(getattr(rule, c)) if c == "enabled" else getattr(rule, c)
                     for c in RULE_COLUMNS)


class SettingsRepository:
    """Key/value settings, including the ones the admin UI can change at runtime."""

    def __init__(self, db: Database, defaults: RedmineCredentials = RedmineCredentials()) -> None:
        self._db = db
        self._defaults = defaults

    def _get(self, key: str) -> str:
        row = self._db.query("SELECT value FROM settings WHERE key=?", (key,), one=True)
        return row["value"] if row else ""

    def _set(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))

    def redmine_credentials(self) -> RedmineCredentials:
        return RedmineCredentials(
            url=(self._get("redmine_url") or self._defaults.url).rstrip("/"),
            api_key=self._get("redmine_api_key") or self._defaults.api_key,
        )

    def save_redmine_url(self, url: str) -> None:
        self._set("redmine_url", url)

    def save_redmine_api_key(self, api_key: str) -> None:
        self._set("redmine_api_key", api_key)

    def summary_settings(self) -> SummarySettings:
        return SummarySettings(
            provider=self._get("summary_provider") or "none",
            model=self._get("summary_model"),
            endpoint=self._get("summary_endpoint"),
        )

    def save_summary_settings(self, chosen: SummarySettings) -> None:
        self._set("summary_provider", chosen.provider)
        self._set("summary_model", chosen.model)
        self._set("summary_endpoint", chosen.endpoint)

    def assistant_settings(self) -> AssistantSettings:
        return AssistantSettings(
            enabled=self._get("assistant_enabled") == "1",
            handle=self._get("assistant_handle") or AssistantSettings.handle,
            model=self._get("assistant_model"),
            since=self._get("assistant_since"),
            cursor=self._get("assistant_cursor"),
        )

    def save_assistant_settings(self, chosen: AssistantSettings) -> None:
        self._set("assistant_enabled", "1" if chosen.enabled else "0")
        self._set("assistant_handle", chosen.handle)
        self._set("assistant_model", chosen.model)
        self._set("assistant_since", chosen.since)
        self._set("assistant_cursor", chosen.cursor)

    def save_assistant_cursor(self, cursor: str) -> None:
        self._set("assistant_cursor", cursor)

    def flask_secret_key(self) -> str:
        """Shared across gunicorn workers so sessions and CSRF work on every one."""
        self._db.execute("INSERT OR IGNORE INTO settings VALUES ('_secret_key', ?)",
                         (secrets.token_hex(32),))
        return self._get("_secret_key")


class CodeProjectRepository:
    """Which Redmine project's code lives in which directory on this host."""

    def __init__(self, db: Database, clock: Callable[[], str] = utc_now) -> None:
        self._db = db
        self._clock = clock

    @staticmethod
    def _to_project(row: sqlite3.Row) -> CodeProject:
        return CodeProject(id=row["id"], redmine_project=row["redmine_project"],
                           code_path=row["code_path"], enabled=bool(row["enabled"]),
                           created_at=row["created_at"] or "")

    def all(self) -> list[CodeProject]:
        rows = self._db.query("SELECT * FROM code_projects ORDER BY redmine_project COLLATE NOCASE")
        return [self._to_project(r) for r in rows]

    def enabled(self) -> list[CodeProject]:
        return [p for p in self.all() if p.enabled]

    def get(self, project_id: int) -> CodeProject | None:
        row = self._db.query("SELECT * FROM code_projects WHERE id=?", (project_id,), one=True)
        return self._to_project(row) if row else None

    def save(self, project: CodeProject) -> None:
        """Adding a Redmine project that is already mapped repoints it."""
        self._db.execute(
            "INSERT INTO code_projects (redmine_project, code_path, enabled, created_at)"
            " VALUES (?, ?, ?, ?) ON CONFLICT(redmine_project) DO UPDATE SET"
            " code_path=excluded.code_path, enabled=excluded.enabled",
            (project.redmine_project, project.code_path, int(project.enabled), self._clock()))

    def toggle(self, project_id: int) -> None:
        self._db.execute("UPDATE code_projects SET enabled = 1 - enabled WHERE id=?", (project_id,))

    def delete(self, project_id: int) -> CodeProject | None:
        project = self.get(project_id)
        self._db.execute("DELETE FROM code_projects WHERE id=?", (project_id,))
        return project


class MentionLedger:
    """Remembers which comments were already answered. Claiming is atomic, so
    every gunicorn worker can poll and still only one of them replies."""

    def __init__(self, db: Database, clock: Callable[[], str] = utc_now) -> None:
        self._db = db
        self._clock = clock

    def claim(self, journal_id: int, issue: int) -> bool:
        return self._db.insert_ignore("INSERT OR IGNORE INTO mentions VALUES (?, ?, ?)",
                                      (journal_id, issue, self._clock()))


class PostedLedger:
    """Remembers which commit/issue pairs were already linked, so a commit that
    reaches several branches is only commented on once."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def contains(self, sha: str, issue: int) -> bool:
        return self._db.query("SELECT 1 FROM posted WHERE sha=? AND issue=?",
                              (sha, issue), one=True) is not None

    def record(self, sha: str, issue: int) -> None:
        self._db.execute("INSERT OR IGNORE INTO posted VALUES (?, ?)", (sha, issue))


class ActivityLog:
    def __init__(self, db: Database, keep: int = LOG_KEEP,
                 clock: Callable[[], str] = utc_now) -> None:
        self._db = db
        self._keep = keep
        self._clock = clock

    def record(self, entry: ActivityEntry) -> None:
        new_id = self._db.execute(
            "INSERT INTO log (ts, rule_name, project, branch, sha, commit_url, issue, status, detail)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (self._clock(), entry.rule_name, entry.project, entry.branch, entry.sha,
             entry.commit_url, entry.issue, entry.status, entry.detail))
        if new_id % 100 == 0:
            self._db.execute("DELETE FROM log WHERE id <= ?", (new_id - self._keep,))

    def recent(self, limit: int) -> list[ActivityEntry]:
        rows = self._db.query("SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,))
        return [ActivityEntry(
            id=r["id"], ts=r["ts"], rule_name=r["rule_name"], project=r["project"],
            branch=r["branch"], sha=r["sha"] or "", commit_url=r["commit_url"] or "",
            issue=r["issue"], status=r["status"] or "", detail=r["detail"] or "",
        ) for r in rows]
