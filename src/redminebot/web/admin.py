"""The admin UI: rules, activity, settings and the @mention assistant.

Every dependency arrives as an argument, so the blueprint has no module-level
state and can be built against fakes.
"""

from __future__ import annotations

import os

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

from ..assistant import utc_now_iso
from ..models import ActivityEntry, AssistantSettings, CodeProject, SummarySettings
from ..notes import DEFAULT_PATTERN, DEFAULT_TEMPLATE
from ..summaries import CLAUDE_CLI, DEFAULT_OLLAMA_ENDPOINT, NONE, OLLAMA
from ..validation import RuleForm

RECENT_ON_DASHBOARD = 10
RECENT_ON_ACTIVITY_PAGE = 300


def create_admin_blueprint(*, rules, settings, activity, trackers, summarizers,
                           code_projects, analyzers, mentions, tasks,
                           guard, config) -> Blueprint:
    bp = Blueprint("admin", __name__)
    bp.before_request(guard.before_request)

    def hook_url() -> str:
        return (config.public_url or request.url_root.rstrip("/")) + "/gitlab/webhook"

    def render_form(form: RuleForm, rule_id: int | None):
        return render_template("rule_form.html", active="rules", form=form, rule_id=rule_id,
                               hook_url=hook_url(), default_pattern=DEFAULT_PATTERN,
                               default_template=DEFAULT_TEMPLATE)

    # ---------------------------------------------------------------- rules

    @bp.get("/")
    def index():
        credentials = settings.redmine_credentials()
        return render_template(
            "index.html", active="rules",
            rules=rules.all(),
            entries=activity.recent(RECENT_ON_DASHBOARD),
            hook_url=hook_url(),
            redmine_url=credentials.url,
            redmine_ok=credentials.configured,
        )

    @bp.route("/rules/new", methods=["GET", "POST"], endpoint="rule_new")
    @bp.route("/rules/<int:rule_id>", methods=["GET", "POST"], endpoint="rule_edit")
    def rule_form(rule_id: int | None = None):
        existing = rules.get(rule_id) if rule_id else None
        if rule_id and not existing:
            abort(404)

        if request.method == "GET":
            return render_form(RuleForm.of(existing) if existing else RuleForm.blank(), rule_id)

        form = RuleForm.submitted(request.form)
        errors = form.errors()
        if errors:
            for error in errors:
                flash(error, "error")
            return render_form(form, rule_id)

        if rule_id:
            rules.update(rule_id, form.to_rule(rule_id))
        else:
            rules.add(form.to_rule())
        flash(f"Rule “{form.name}” saved.")
        return redirect(url_for("admin.index"))

    @bp.post("/rules/<int:rule_id>/toggle")
    def rule_toggle(rule_id: int):
        rules.toggle(rule_id)
        return redirect(url_for("admin.index"))

    @bp.post("/rules/<int:rule_id>/delete")
    def rule_delete(rule_id: int):
        deleted = rules.delete(rule_id)
        if deleted:
            flash(f"Rule “{deleted.name}” deleted.")
        return redirect(url_for("admin.index"))

    # ------------------------------------------------------------- activity

    @bp.get("/activity")
    def log_page():
        return render_template("activity.html", active="activity",
                               entries=activity.recent(RECENT_ON_ACTIVITY_PAGE),
                               redmine_url=settings.redmine_credentials().url)

    # ------------------------------------------------------------- settings

    @bp.route("/settings", methods=["GET", "POST"])
    def settings_page():
        if request.method == "POST":
            url = request.form.get("redmine_url", "").strip().rstrip("/")
            if url and not url.startswith(("http://", "https://")):
                flash("Redmine URL must start with http:// or https://", "error")
            else:
                settings.save_redmine_url(url)
                api_key = request.form.get("redmine_api_key", "").strip()
                if api_key:
                    settings.save_redmine_api_key(api_key)
                flash("Settings saved.")
            return redirect(url_for("admin.settings_page"))

        credentials = settings.redmine_credentials()
        return render_template(
            "settings.html", active="settings",
            redmine_url=credentials.url, has_key=bool(credentials.api_key),
            summary=settings.summary_settings(),
            providers=[(NONE, "Off"), (CLAUDE_CLI, "Claude Code CLI (uses this host's Claude login)"),
                       (OLLAMA, "Ollama (local model)")],
            default_claude_model=config.summary_model,
            default_ollama_endpoint=config.ollama_endpoint or DEFAULT_OLLAMA_ENDPOINT)

    @bp.post("/settings/test")
    def settings_test():
        outcome = trackers.create().check_connection()
        flash(outcome.detail, "message" if outcome.ok else "error")
        return redirect(url_for("admin.settings_page"))

    @bp.post("/settings/summary")
    def settings_summary():
        provider = request.form.get("provider", NONE)
        if provider not in (NONE, CLAUDE_CLI, OLLAMA):
            flash("Unknown summary provider.", "error")
            return redirect(url_for("admin.settings_page"))
        settings.save_summary_settings(SummarySettings(
            provider=provider,
            model=request.form.get("model", "").strip(),
            endpoint=request.form.get("endpoint", "").strip().rstrip("/"),
        ))
        flash("Summary settings saved." if provider != NONE else "Push summaries turned off.")
        return redirect(url_for("admin.settings_page"))

    @bp.post("/settings/summary/test")
    def settings_summary_test():
        outcome = summarizers.create().check()
        flash(outcome.detail, "message" if outcome.ok else "error")
        return redirect(url_for("admin.settings_page"))

    # ------------------------------------------------------------ assistant

    @bp.get("/assistant")
    def assistant_page():
        return render_template(
            "assistant.html", active="assistant",
            assistant=settings.assistant_settings(),
            projects=code_projects.all(),
            default_model=config.summary_model,
            poll_seconds=config.assistant_poll_seconds,
            redmine_ok=settings.redmine_credentials().configured)

    @bp.post("/assistant/settings")
    def assistant_settings():
        current = settings.assistant_settings()
        enabled = bool(request.form.get("enabled"))
        handle = request.form.get("handle", "").strip()
        if not handle.lstrip("@") or any(c.isspace() for c in handle):
            flash("The handle must be one word, like @claude.", "error")
            return redirect(url_for("admin.assistant_page"))
        switched_on = enabled and not current.enabled
        settings.save_assistant_settings(AssistantSettings(
            enabled=enabled,
            handle="@" + handle.lstrip("@"),
            model=request.form.get("model", "").strip(),
            # Turning it on starts from now: mentions written while it was off
            # are not answered all at once.
            since=utc_now_iso() if switched_on else current.since,
            cursor="" if switched_on else current.cursor,
        ))
        flash("Assistant settings saved." if enabled else "Assistant turned off.")
        return redirect(url_for("admin.assistant_page"))

    @bp.post("/assistant/projects")
    def assistant_project_add():
        identifier = request.form.get("redmine_project", "").strip()
        path = os.path.expanduser(request.form.get("code_path", "").strip()).rstrip("/")
        if not identifier:
            flash("Enter the Redmine project identifier.", "error")
        elif not os.path.isabs(path):
            flash("The code directory must be an absolute path.", "error")
        elif not os.path.isdir(path):
            flash(f"{path} is not a directory on this server.", "error")
        else:
            code_projects.save(CodeProject(redmine_project=identifier, code_path=path))
            flash(f"Issues in “{identifier}” will be analysed against {path}.")
        return redirect(url_for("admin.assistant_page"))

    @bp.post("/assistant/projects/<int:project_id>/toggle")
    def assistant_project_toggle(project_id: int):
        code_projects.toggle(project_id)
        return redirect(url_for("admin.assistant_page"))

    @bp.post("/assistant/projects/<int:project_id>/delete")
    def assistant_project_delete(project_id: int):
        deleted = code_projects.delete(project_id)
        if deleted:
            flash(f"“{deleted.redmine_project}” removed.")
        return redirect(url_for("admin.assistant_page"))

    @bp.post("/assistant/projects/<int:project_id>/test")
    def assistant_project_test(project_id: int):
        project = code_projects.get(project_id) or abort(404)

        def run_check():
            outcome = analyzers.create().check(project.code_path)
            activity.record(ActivityEntry(
                rule_name="Assistant test", project=project.redmine_project,
                branch=project.code_path, status="posted" if outcome.ok else "failed",
                detail=outcome.detail))

        # A real analysis can take minutes: longer than a gunicorn worker may
        # hold a request.
        tasks.submit(run_check)
        flash("Test started. The result appears in Activity within a minute or two.")
        return redirect(url_for("admin.assistant_page"))

    @bp.post("/assistant/poll")
    def assistant_poll():
        tasks.submit(mentions.poll_once)
        flash("Checking Redmine for new mentions now. Answers show up in Activity.")
        return redirect(url_for("admin.assistant_page"))

    return bp
