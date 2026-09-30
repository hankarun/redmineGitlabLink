"""The sqlite connection and the schema. The only module that knows sqlite exists."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from typing import Any, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT '',
    branches TEXT NOT NULL DEFAULT '',
    secret TEXT NOT NULL,
    issue_pattern TEXT NOT NULL DEFAULT '',
    template TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS posted (
    sha TEXT, issue INTEGER, PRIMARY KEY (sha, issue)
);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, rule_name TEXT, project TEXT, branch TEXT,
    sha TEXT, commit_url TEXT, issue INTEGER, status TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS code_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redmine_project TEXT NOT NULL UNIQUE,
    code_path TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS mentions (
    journal_id INTEGER PRIMARY KEY, issue INTEGER, ts TEXT
);
"""


class Database:
    """Short-lived connections plus a write lock, so gunicorn workers and the
    webhook threads can share one sqlite file."""

    def __init__(self, path: str, timeout: float = 10) -> None:
        self.path = path
        self.timeout = timeout
        self._write_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql: str, args: Sequence[Any] = (), one: bool = False):
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, args).fetchall()
        return (rows[0] if rows else None) if one else rows

    def execute(self, sql: str, args: Sequence[Any] = ()) -> int:
        with self._write_lock, closing(self._connect()) as conn, conn:
            return conn.execute(sql, args).lastrowid

    def insert_ignore(self, sql: str, args: Sequence[Any] = ()) -> bool:
        """Run an INSERT OR IGNORE; True when this call is the one that inserted.

        The row is the claim, so several gunicorn workers can race for the
        same piece of work and exactly one wins.
        """
        with self._write_lock, closing(self._connect()) as conn, conn:
            return conn.execute(sql, args).rowcount == 1

    def initialize(self) -> "Database":
        with self._write_lock, closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
        return self
