"""GitLab -> Redmine commit linker.

``create_app`` is the composition root: the single place that picks concrete
implementations and wires them together. Everything it builds depends on
protocols and constructor arguments, so a test can call it with a fake tracker,
an in-memory database or an inline task runner and get a working app.
"""

from __future__ import annotations

import logging

from flask import Flask
from jinja2 import DictLoader

from .assistant import AnalyzerFactory, MentionPoller, MentionService
from .config import Config
from .database import Database
from .repositories import (ActivityLog, CodeProjectRepository, MentionLedger, PostedLedger,
                           RuleRepository, SettingsRepository)
from .security import AdminGuard, CsrfGuard, WebhookAuthenticator
from .services import PushProcessor
from .summaries import SummarizerFactory
from .tasks import TaskRunner, ThreadTaskRunner
from .templates import TEMPLATES
from .trackers import TrackerFactory
from .web import create_admin_blueprint, create_webhook_blueprint

__all__ = ["create_app", "Config"]

log = logging.getLogger("gitlab-redmine")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def create_app(config: Config | None = None, *,
               database: Database | None = None,
               trackers=None,
               summarizers=None,
               analyzers=None,
               tasks: TaskRunner | None = None) -> Flask:
    config = config or Config.from_env()
    db = (database or Database(config.db_path)).initialize()

    rules = RuleRepository(db)
    settings = SettingsRepository(db, defaults=config.redmine_defaults)
    posted = PostedLedger(db)
    activity = ActivityLog(db)
    code_projects = CodeProjectRepository(db)
    trackers = trackers or TrackerFactory(settings)
    summarizers = summarizers or SummarizerFactory(settings, config)
    analyzers = analyzers or AnalyzerFactory(settings, config)
    tasks = tasks or ThreadTaskRunner()
    mentions = MentionService(settings, code_projects, MentionLedger(db), trackers,
                              analyzers, activity)

    csrf = CsrfGuard()
    app = Flask(__name__)
    app.secret_key = settings.flask_secret_key()
    app.jinja_loader = DictLoader(TEMPLATES)
    app.jinja_env.globals["csrf_token"] = csrf.token

    app.register_blueprint(create_webhook_blueprint(
        authenticator=WebhookAuthenticator(rules),
        processor=PushProcessor(trackers, posted, activity, summarizers),
        tasks=tasks,
        activity=activity,
    ))
    app.register_blueprint(create_admin_blueprint(
        rules=rules,
        settings=settings,
        activity=activity,
        trackers=trackers,
        summarizers=summarizers,
        code_projects=code_projects,
        analyzers=analyzers,
        mentions=mentions,
        tasks=tasks,
        guard=AdminGuard(config, csrf),
        config=config,
    ))

    # Not started here, so building an app (e.g. in a test) has no side effects;
    # app.py starts it. Every gunicorn worker polls; the mention ledger makes
    # sure only one of them answers a given comment.
    app.extensions["mention_poller"] = MentionPoller(mentions, config.assistant_poll_seconds)

    if not config.admin_enabled:
        log.warning("ADMIN_PASSWORD is not set: the admin UI will be locked.")
    return app
