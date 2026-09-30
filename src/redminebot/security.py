"""Who is allowed to do what.

Three separate jobs that used to share one ``before_request``: proving you are
the admin, proving a form came from a page we served, and proving a webhook
carries a known token.
"""

from __future__ import annotations

import hmac
import secrets

from flask import Response, abort, request, session

from .models import Rule


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode(), (b or "").encode())


class CsrfGuard:
    """A per-session token echoed back by every form we render."""

    FIELD = "csrf"

    def token(self) -> str:
        if self.FIELD not in session:
            session[self.FIELD] = secrets.token_hex(16)
        return session[self.FIELD]

    def valid(self) -> bool:
        return request.form.get(self.FIELD) == session.get(self.FIELD)


class AdminGuard:
    """HTTP basic auth for the admin UI, plus the CSRF check on writes."""

    REALM = 'Basic realm="GitLab-Redmine"'
    LOCKED = "Set the ADMIN_PASSWORD environment variable to use the admin UI."
    EXPIRED = "Form expired, please reload the page and try again."

    def __init__(self, config, csrf: CsrfGuard) -> None:
        self._config = config
        self._csrf = csrf

    def before_request(self) -> Response | None:
        if not self._config.admin_enabled:
            return Response(self.LOCKED, 503)
        if not self._authenticated():
            return Response("Login required", 401, {"WWW-Authenticate": self.REALM})
        if request.method == "POST" and not self._csrf.valid():
            abort(400, self.EXPIRED)
        return None

    def _authenticated(self) -> bool:
        auth = request.authorization
        return bool(auth
                    and _same(auth.username, self._config.admin_user)
                    and _same(auth.password, self._config.admin_password))


class WebhookAuthenticator:
    """A GitLab webhook proves itself with its secret token; that token selects
    the rules it is allowed to trigger."""

    def __init__(self, rules) -> None:
        self._rules = rules

    def rules_for(self, token: str) -> list[Rule]:
        return [r for r in self._rules.enabled() if _same(r.secret, token)]
