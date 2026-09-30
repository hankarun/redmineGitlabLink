"""Talking to the issue tracker.

The service depends on the two narrow protocols below, not on Redmine or on
``requests``. Swapping in a different tracker, or a fake one in a test, means
writing a class with these methods and handing it to the factory.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import requests

from .models import Issue, Outcome, RedmineCredentials

TIMEOUT = 15
PAGE_SIZE = 100


@runtime_checkable
class IssueTracker(Protocol):
    """All the push pipeline needs."""

    def add_note(self, issue_id: int, note: str, private: bool = False) -> Outcome: ...


@runtime_checkable
class IssueReader(Protocol):
    """All the @mention assistant needs on top of posting notes."""

    def current_user_id(self) -> int | None: ...

    def updated_issue_ids(self, project: str, since: str) -> tuple[list[tuple[int, str]], Outcome]: ...

    def issue(self, issue_id: int) -> Issue | None: ...


@runtime_checkable
class ConnectionTester(Protocol):
    """All the settings page needs."""

    def check_connection(self) -> Outcome: ...


class UnconfiguredTracker:
    """Stands in when no credentials are saved yet.

    A real object rather than ``None`` so callers never special-case the
    unconfigured state: they post a note and get an explanatory failure.
    """

    REASON = "Redmine is not configured (see Settings)"

    def add_note(self, issue_id: int, note: str, private: bool = False) -> Outcome:
        return Outcome.failure(self.REASON)

    def current_user_id(self) -> int | None:
        return None

    def updated_issue_ids(self, project: str, since: str) -> tuple[list[tuple[int, str]], Outcome]:
        return [], Outcome.failure(self.REASON)

    def issue(self, issue_id: int) -> Issue | None:
        return None

    def check_connection(self) -> Outcome:
        return Outcome.failure("Save the Redmine URL and API key first.")


class RedmineTracker:
    """Redmine's REST API, with its failure modes translated into plain advice."""

    def __init__(self, credentials: RedmineCredentials, http=requests,
                 timeout: float = TIMEOUT) -> None:
        self._credentials = credentials
        self._http = http
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Redmine-API-Key": self._credentials.api_key}

    def _url(self, path: str) -> str:
        return f"{self._credentials.url}{path}"

    def add_note(self, issue_id: int, note: str, private: bool = False) -> Outcome:
        body = {"notes": note, **({"private_notes": True} if private else {})}
        try:
            resp = self._http.put(self._url(f"/issues/{issue_id}.json"),
                                  json={"issue": body},
                                  headers=self._headers, timeout=self._timeout)
        except requests.RequestException as exc:
            return Outcome.failure(f"Could not reach Redmine: {exc}")
        if resp.status_code in (200, 204):
            return Outcome.success()
        if resp.status_code == 404:
            return Outcome.failure("Issue not found, or the API user can't see it")
        if resp.status_code in (401, 403):
            return Outcome.failure(f"Redmine refused the API key (HTTP {resp.status_code})")
        return Outcome.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")

    def current_user_id(self) -> int | None:
        """The API key's own user, so the assistant never answers itself."""
        try:
            resp = self._http.get(self._url("/users/current.json"),
                                  headers=self._headers, timeout=self._timeout)
            return resp.json()["user"]["id"] if resp.status_code == 200 else None
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    def updated_issue_ids(self, project: str, since: str) -> tuple[list[tuple[int, str]], Outcome]:
        """(id, updated_on) of every issue in ``project`` (and its subprojects)
        changed at or after ``since``, oldest first."""
        found: list[tuple[int, str]] = []
        offset = 0
        while True:
            params = {"project_id": project, "status_id": "*", "sort": "updated_on",
                      "limit": PAGE_SIZE, "offset": offset}
            if since:
                params["updated_on"] = f">={since}"
            try:
                resp = self._http.get(self._url("/issues.json"), params=params,
                                      headers=self._headers, timeout=self._timeout)
            except requests.RequestException as exc:
                return found, Outcome.failure(f"Could not reach Redmine: {exc}")
            if resp.status_code == 404:
                return found, Outcome.failure(f"Redmine has no project “{project}” the API user can see")
            if resp.status_code != 200:
                return found, Outcome.failure(f"Listing issues of {project}: HTTP {resp.status_code}")
            try:
                data = resp.json()
                page = [(i["id"], i.get("updated_on", "")) for i in data.get("issues", [])]
            except (ValueError, KeyError, TypeError) as exc:
                return found, Outcome.failure(f"Unexpected answer from Redmine: {exc}")
            found.extend(page)
            offset += len(page)
            if not page or offset >= data.get("total_count", 0):
                return found, Outcome.success()

    def issue(self, issue_id: int) -> Issue | None:
        try:
            resp = self._http.get(self._url(f"/issues/{issue_id}.json"),
                                  params={"include": "journals"},
                                  headers=self._headers, timeout=self._timeout)
            return Issue.from_payload(resp.json()["issue"]) if resp.status_code == 200 else None
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    def check_connection(self) -> Outcome:
        try:
            resp = self._http.get(self._url("/users/current.json"),
                                  headers=self._headers, timeout=10)
            if resp.status_code == 200:
                login = resp.json()["user"].get("login", "?")
                return Outcome.success(f"Connected to Redmine as “{login}”.")
            if resp.status_code in (401, 403):
                return Outcome.failure(
                    "Redmine rejected the API key. Also check that the REST API is enabled "
                    "(Administration → Settings → API).")
            return Outcome.failure(f"Redmine answered HTTP {resp.status_code}.")
        except (requests.RequestException, ValueError, KeyError) as exc:
            return Outcome.failure(f"Could not reach Redmine: {exc}")


class TrackerFactory:
    """Builds a tracker from whatever credentials are saved *right now*.

    Credentials are editable in the admin UI, so they are resolved per use
    rather than captured once at startup.
    """

    def __init__(self, settings, http=requests) -> None:
        self._settings = settings
        self._http = http

    def create(self):
        credentials = self._settings.redmine_credentials()
        if not credentials.configured:
            return UnconfiguredTracker()
        return RedmineTracker(credentials, http=self._http)
