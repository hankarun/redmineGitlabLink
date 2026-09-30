"""GitLab -> Redmine commit linker, with a small admin web UI.

GitLab sends a "Push Hook" to  /gitlab/webhook . For every commit whose message
mentions a Redmine issue (e.g. "Fix login bug #324"), a note is added to that
issue with the commit hash and a link to the commit.

Which pushes are handled is decided by *rules* you manage in the web UI:
    - GitLab projects   e.g. "team/backend, team/*"   (empty = all)
    - branches          e.g. "main, release/*"        (empty = all)
    - secret token      must equal the GitLab webhook's "Secret token"
    - optional issue regex and comment template

Environment variables (read from the environment, or from a .env file):
    ADMIN_PASSWORD   password for the web UI (required to open the UI)
    ADMIN_USER       username for the web UI (default: admin)
    DB_PATH          sqlite file (default: hooks.db)
    PUBLIC_URL       external base URL, e.g. https://hooks.example.com
                     (only used to display the webhook URL; optional)
    REDMINE_URL / REDMINE_API_KEY   optional defaults; can be set in the UI instead
    SUMMARY_COMMAND / SUMMARY_MODEL / SUMMARY_TIMEOUT / SUMMARY_MAX_COMMITS
    OLLAMA_ENDPOINT / OLLAMA_TIMEOUT
                     defaults for the optional push summaries; which provider
                     is used is chosen in the UI under Settings
    ASSISTANT_POLL_SECONDS / ASSISTANT_TIMEOUT
                     how often Redmine is checked for @mentions of the
                     assistant (0 turns polling off), and how long one code
                     analysis may take; the assistant itself is set up under
                     Assistant in the UI

This module is only the entry point; the service lives in src/redminebot/.

Run:  gunicorn -w 2 -b 0.0.0.0:8000 app:app
"""

from redminebot import Config, configure_logging, create_app

configure_logging()
config = Config.from_env()
app = create_app(config)
app.extensions["mention_poller"].start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.port)
