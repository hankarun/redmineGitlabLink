"""Process configuration, read once and passed around explicitly."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv

from .models import RedmineCredentials


@dataclass(frozen=True)
class Config:
    db_path: str = "hooks.db"
    admin_user: str = "admin"
    admin_password: str = ""
    public_url: str = ""
    redmine_url: str = ""
    redmine_api_key: str = ""
    port: int = 8000
    summary_command: str = "claude"
    summary_model: str = "claude-sonnet-5"
    summary_timeout: float = 120
    summary_max_commits: int = 50
    ollama_endpoint: str = "http://localhost:11434"
    ollama_timeout: float = 300
    assistant_timeout: float = 600
    assistant_poll_seconds: float = 60

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        if env is None:
            # Anything already exported wins; .env only fills in the gaps.
            load_dotenv()
            env = os.environ
        return cls(
            db_path=env.get("DB_PATH", "hooks.db"),
            admin_user=env.get("ADMIN_USER", "admin"),
            admin_password=env.get("ADMIN_PASSWORD", ""),
            public_url=env.get("PUBLIC_URL", "").rstrip("/"),
            redmine_url=env.get("REDMINE_URL", "").rstrip("/"),
            redmine_api_key=env.get("REDMINE_API_KEY", ""),
            port=int(env.get("PORT", 8000)),
            summary_command=env.get("SUMMARY_COMMAND", "claude"),
            summary_model=env.get("SUMMARY_MODEL", "claude-sonnet-5"),
            summary_timeout=float(env.get("SUMMARY_TIMEOUT", 120)),
            summary_max_commits=int(env.get("SUMMARY_MAX_COMMITS", 50)),
            ollama_endpoint=env.get("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/"),
            ollama_timeout=float(env.get("OLLAMA_TIMEOUT", 300)),
            assistant_timeout=float(env.get("ASSISTANT_TIMEOUT", 600)),
            assistant_poll_seconds=float(env.get("ASSISTANT_POLL_SECONDS", 60)),
        )

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)

    @property
    def redmine_defaults(self) -> RedmineCredentials:
        """Fallback used until someone saves credentials in the admin UI."""
        return RedmineCredentials(self.redmine_url, self.redmine_api_key)
