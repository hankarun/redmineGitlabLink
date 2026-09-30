"""The endpoint GitLab calls, plus the health check.

Deliberately not part of the admin blueprint: that is what keeps it outside the
admin login instead of relying on an endpoint-name skip list.
"""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from ..models import ActivityEntry, PushEvent


def create_webhook_blueprint(*, authenticator, processor, tasks, activity) -> Blueprint:
    bp = Blueprint("webhook", __name__)

    @bp.post("/gitlab/webhook")
    def receive():
        rules = authenticator.rules_for(request.headers.get("X-Gitlab-Token") or "")
        if not rules:
            abort(401)
        if request.headers.get("X-Gitlab-Event") != "Push Hook":
            return jsonify(status="ignored", reason="not a push event")

        push = PushEvent.from_payload(request.get_json(silent=True) or {})
        if push is None:
            return jsonify(status="ignored", reason="not a branch push")

        matched = [r for r in rules if r.accepts(push.project, push.branch)]
        if not matched:
            activity.record(ActivityEntry(
                project=push.project, branch=push.branch, status="ignored",
                detail="Token is valid, but no rule matches this project/branch"))
            return jsonify(status="ignored", reason="no matching rule")

        tasks.submit(processor.process, push, matched)
        return jsonify(status="accepted", rules=[r.name for r in matched])

    @bp.get("/health")
    def health():
        return "ok"

    return bp
