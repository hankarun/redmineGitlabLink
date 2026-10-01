# redmine-bot

Links GitLab commits to Redmine issues, and answers `@claude` mentions on
Redmine issues by reading the project's source code and posting a likely root
cause and fix. Has a small admin web UI for rules, settings and activity.

- GitLab sends a "Push Hook" to `/gitlab/webhook`. Commits whose message
  mentions an issue (e.g. `Fix login bug #324`) get a note added to that issue.
- Mention the bot in a Redmine comment (e.g. `@claude why does this crash?`)
  and, once a Redmine project is mapped to a code checkout on this host, it
  analyses that code and replies on the issue. See the **Assistant** page in
  the admin UI.

This document covers installing it and running it as a background service on
Linux and Windows. For day-to-day configuration (rules, Redmine credentials,
the assistant) use the admin UI once it's running.

## Requirements

- Python 3.10+
- Network access to your Redmine instance (and to GitLab if you use the
  commit-linking feature)
- For the AI features: the [Claude Code CLI](https://claude.com/claude-code)
  installed and signed in as the OS user the service runs as (`claude` on
  PATH, or point `SUMMARY_COMMAND` at its full path), and/or a local
  [Ollama](https://ollama.com) daemon

## Install

```bash
git clone <this repo> redmine-bot
cd redmine-bot
python3 -m venv venv
```

**Linux/macOS**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install waitress   # production WSGI server for Windows — see below
```

Then configure:

```bash
cp .env.example .env
```

Edit `.env` and set at least `ADMIN_PASSWORD` (the admin UI is locked without
it). `REDMINE_URL`/`REDMINE_API_KEY` can also be set later from the Settings
page. See the comments in `.env.example` for every variable, including
`ASSISTANT_POLL_SECONDS`/`ASSISTANT_TIMEOUT` for the @mention assistant.

`.env` is loaded automatically from the process's working directory, so
whichever way you run the service, **start it with the repo root as the
working directory** (a systemd `WorkingDirectory=` / an NSSM `AppDirectory`
set to the repo path takes care of this).

Try it out first with the dev server before wiring up a service:

```bash
python app.py        # http://localhost:8000
```

## Running as a service

Gunicorn (already in `requirements.txt`) is what's used in production on
Linux/macOS. It does not run on Windows (it depends on `fork`/`fcntl`), so the
Windows instructions below use [Waitress](https://github.com/Pylons/waitress)
instead — a pure-Python WSGI server with no other moving parts. Both serve the
same `app:app` object from `app.py`.

### Linux (systemd)

1. Put the repo somewhere permanent, e.g. `/opt/redmine-bot`, with `.env`
   filled in there.

2. (Recommended) create a dedicated, unprivileged user:

   ```bash
   sudo useradd --system --home /opt/redmine-bot --shell /usr/sbin/nologin redminebot
   sudo chown -R redminebot:redminebot /opt/redmine-bot
   ```

3. Create `/etc/systemd/system/redmine-bot.service`:

   ```ini
   [Unit]
   Description=redmine-bot
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=redminebot
   Group=redminebot
   WorkingDirectory=/opt/redmine-bot
   ExecStart=/opt/redmine-bot/venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:app
   Restart=on-failure
   RestartSec=5
   # Hardening (optional but recommended)
   NoNewPrivileges=true
   PrivateTmp=true
   ProtectSystem=strict
   # code directories the assistant reads must be reachable despite ProtectSystem=strict
   ReadWritePaths=/opt/redmine-bot
   ReadOnlyPaths=/srv/checkouts

   [Install]
   WantedBy=multi-user.target
   ```

   Adjust `ReadOnlyPaths` to wherever you check out project source for the
   @mention assistant to read (see the Assistant page); drop the hardening
   lines entirely if that's simpler while you get things working.

   `-w 2` runs two gunicorn workers. Every worker polls Redmine for mentions
   independently, but the mentions table makes sure only one of them ever
   answers a given comment — you don't need to special-case worker count.

4. Enable and start it:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now redmine-bot
   sudo systemctl status redmine-bot
   journalctl -u redmine-bot -f          # logs
   ```

5. Put a reverse proxy (nginx/Caddy) in front of it for TLS, and set
   `PUBLIC_URL` in `.env` to the externally visible `https://...` URL so the
   admin UI displays the correct webhook URL to paste into GitLab.

To update: `git pull`, `venv/bin/pip install -r requirements.txt`, then
`sudo systemctl restart redmine-bot`.

### Windows

Gunicorn doesn't work on Windows, so serve with Waitress instead
(`pip install waitress`, done above). The simplest way to run anything as a
proper Windows service — one that starts at boot, restarts on crash, and logs
to a file — is [NSSM](https://nssm.cc/) (the Non-Sucking Service Manager).
A Task Scheduler alternative that needs no extra tools is below.

#### Option A — NSSM (recommended)

1. Download NSSM from https://nssm.cc/download and put `nssm.exe` somewhere
   on `PATH` (e.g. `C:\nssm\nssm.exe`).

2. Confirm the venv has everything (from the repo root, in the activated venv):

   ```powershell
   pip install -r requirements.txt
   pip install waitress
   ```

3. Install the service, pointing it at `waitress-serve` inside the venv:

   ```powershell
   nssm install RedmineBot "E:\redmineGitlabLink\venv\Scripts\waitress-serve.exe" --host=0.0.0.0 --port=8000 app:app
   nssm set RedmineBot AppDirectory E:\redmineGitlabLink
   nssm set RedmineBot Start SERVICE_AUTO_START
   nssm set RedmineBot AppStdout E:\redmineGitlabLink\logs\service.log
   nssm set RedmineBot AppStderr E:\redmineGitlabLink\logs\service.log
   nssm set RedmineBot AppRotateFiles 1
   ```

   `AppDirectory` matters: it's what makes the process pick up `.env` and
   resolve the (relative, by default) sqlite `DB_PATH`. Create the `logs`
   folder first (`mkdir E:\redmineGitlabLink\logs`).

   If the Claude CLI needs a specific PATH or a user profile to find its
   login (e.g. it's signed in under a particular Windows account), either run
   the service as that user (`nssm set RedmineBot ObjectName ".\username" "password"`)
   or set `SUMMARY_COMMAND` in `.env` to the CLI's full `.cmd`/`.exe` path.

4. Start it and check status:

   ```powershell
   nssm start RedmineBot
   nssm status RedmineBot
   ```

   `services.msc` also shows it as **RedmineBot**, startup type Automatic.

5. To update: stop the service (`nssm stop RedmineBot`), `git pull`,
   reinstall requirements, `nssm start RedmineBot`.

6. To remove it later: `nssm remove RedmineBot confirm`.

#### Option B — Task Scheduler (no extra tools)

Less robust than a real service (e.g. it runs in a user session rather than
as a system service), but works with nothing but what Windows ships.

1. Create `E:\redmineGitlabLink\run.bat`:

   ```bat
   @echo off
   cd /d E:\redmineGitlabLink
   venv\Scripts\waitress-serve.exe --host=0.0.0.0 --port=8000 app:app
   ```

2. Open **Task Scheduler → Create Task...**
   - **General**: name it `RedmineBot`; "Run whether user is logged on or
     not"; "Run with highest privileges".
   - **Triggers**: New → "At startup".
   - **Actions**: New → Start a program → `E:\redmineGitlabLink\run.bat`.
   - **Settings**: tick "Restart the task if it fails" (e.g. every 1 minute,
     up to 3 times), and untick "Stop the task if it runs longer than..." —
     it's meant to run indefinitely.

3. Right-click the task → **Run** to start it immediately without rebooting.

Either way, put IIS with the ARR module, or another reverse proxy, in front of
it for TLS if this is reachable from outside the host, and set `PUBLIC_URL`
in `.env` accordingly.

## After the service is running

1. Open `http://<host>:8000/` (or your `PUBLIC_URL`), sign in with
   `ADMIN_USER`/`ADMIN_PASSWORD`.
2. **Settings** → add the Redmine URL and API key, "Test connection".
3. **Rules** → add a rule, copy its webhook URL and secret token into
   GitLab's project/group webhook settings (Push events).
4. Optional — **Settings → Push summaries**: pick Claude CLI or Ollama to
   have pushes summarized in the issue comment.
5. Optional — **Assistant**: turn it on, map a Redmine project identifier to
   a local checkout directory, and try "Test". Then mention the configured
   handle (default `@claude`) in a Redmine comment.

## Troubleshooting

- **Admin UI says "Set the ADMIN_PASSWORD..."** — it's empty or not loaded;
  confirm `.env` sits in the service's working directory.
- **GitLab webhook gets 401** — the `X-Gitlab-Token` header doesn't match any
  enabled rule's secret.
- **Assistant never replies** — check `ASSISTANT_POLL_SECONDS` isn't `0`,
  that the mention was written after the assistant was turned on, that the
  code directory exists and is readable by the service's OS user/account,
  and use **Assistant → Test** to see the exact error in Activity.
- **Claude CLI errors** ("not found" / not signed in) — the service's OS
  user needs `claude` on PATH (or `SUMMARY_COMMAND` set to its full path) and
  needs to be signed in under that same account.
