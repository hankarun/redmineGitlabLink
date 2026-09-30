"""The admin UI's HTML.

A dict of Jinja sources rather than a templates/ tree, so the service stays a
handful of importable modules with no data files to deploy alongside them.
"""

TEMPLATES = {
"base.html": """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}GitLab → Redmine{% endblock %}</title>
<style>
:root{--bg:#f6f6f3;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e1db;--accent:#2d6a4f;--on-accent:#fff;--danger:#b3261e;--ok:#2d6a4f;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--fg:#ececea;--muted:#a3a39c;--line:#34342f;--accent:#74c69d;--on-accent:#0f1a14;--danger:#f2877f;--ok:#74c69d;--warn:#e0b44f}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
a{color:var(--accent)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
header{background:var(--card);border-bottom:1px solid var(--line)}
header .wrap{display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center;min-height:56px;padding-top:8px;padding-bottom:8px}
header .brand{font-weight:650;margin-right:auto}
header nav a{color:var(--muted);text-decoration:none;margin-left:18px}
header nav a:first-child{margin-left:0}
header nav a.on,header nav a:hover{color:var(--fg)}
main{padding:28px 0 56px}
h1{font-size:22px;margin:0}
h2{font-size:16px;margin:32px 0 10px}
.head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.scroll{overflow-x:auto;padding:0}
table{width:100%;border-collapse:collapse;min-width:640px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
code.url{display:inline-block;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:3px 8px;word-break:break-all}
.btn{display:inline-block;border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 13px;border-radius:7px;font:inherit;font-size:14px;cursor:pointer;text-decoration:none;white-space:nowrap}
.btn:hover{border-color:var(--muted)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.btn.danger{color:var(--danger)}
.btn.small{padding:3px 10px;font-size:13px}
.actions{display:flex;gap:6px;justify-content:flex-end}
.actions form{margin:0}
label{display:block;font-weight:600;margin:18px 0 5px}
label:first-of-type{margin-top:4px}
.hint{display:block;color:var(--muted);font-size:13px;font-weight:400;margin-top:4px}
input[type=text],input[type=password],input[type=url],select,textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg);font:inherit}
input:focus,select:focus,textarea:focus{outline:2px solid var(--accent);outline-offset:-1px}
input.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
textarea{font-family:ui-monospace,Menlo,monospace;font-size:13px;min-height:120px;resize:vertical}
.check{display:flex;gap:8px;align-items:center;font-weight:600;margin-top:18px}
details{margin-top:22px;border-top:1px solid var(--line);padding-top:14px}
summary{cursor:pointer;color:var(--muted)}
.formbar{display:flex;gap:8px;margin-top:24px}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;border:1px solid currentColor}
.ok{color:var(--ok)}.err{color:var(--danger)}.warn{color:var(--warn)}.skip{color:var(--muted)}
.muted{color:var(--muted)}.small{font-size:13px}
.flash{padding:10px 14px;border-radius:8px;margin-bottom:16px;border:1px solid var(--ok);color:var(--ok);background:var(--card)}
.flash.error{border-color:var(--danger);color:var(--danger)}
.empty{padding:22px 18px;margin:0}
.steps{margin:8px 0 0;padding-left:20px;color:var(--muted)}
</style></head><body>
<header><div class="wrap"><span class="brand">GitLab → Redmine</span>
<nav><a href="{{ url_for('admin.index') }}" class="{{ 'on' if active=='rules' }}">Rules</a><a href="{{ url_for('admin.log_page') }}" class="{{ 'on' if active=='activity' }}">Activity</a><a href="{{ url_for('admin.assistant_page') }}" class="{{ 'on' if active=='assistant' }}">Assistant</a><a href="{{ url_for('admin.settings_page') }}" class="{{ 'on' if active=='settings' }}">Settings</a></nav>
</div></header>
<main class="wrap">
{% with msgs = get_flashed_messages(with_categories=true) %}{% for cat, m in msgs %}<div class="flash {{ cat }}">{{ m }}</div>{% endfor %}{% endwith %}
{% block content %}{% endblock %}
</main></body></html>""",

"log_table.html": """{% if entries %}<table>
<tr><th>Time (UTC)</th><th>Rule</th><th>Project / branch</th><th>Commit</th><th>Issue</th><th>Result</th></tr>
{% for e in entries %}<tr>
<td class="mono">{{ e.ts }}</td>
<td>{{ e.rule_name }}</td>
<td class="mono">{{ e.project }}<br><span class="muted">{{ e.branch }}</span></td>
<td class="mono">{% if e.sha %}{% if e.commit_url and e.commit_url.startswith('http') %}<a href="{{ e.commit_url }}" target="_blank" rel="noopener">{{ e.sha[:8] }}</a>{% else %}{{ e.sha[:8] }}{% endif %}{% else %}—{% endif %}</td>
<td>{% if e.issue %}{% if redmine_url %}<a href="{{ redmine_url }}/issues/{{ e.issue }}" target="_blank" rel="noopener">#{{ e.issue }}</a>{% else %}#{{ e.issue }}{% endif %}{% else %}—{% endif %}</td>
<td><span class="{{ {'posted':'ok','failed':'err','warning':'warn'}.get(e.status,'skip') }}">{{ e.status }}</span>{% if e.detail %}<div class="muted small" style="white-space:pre-wrap">{{ e.detail }}</div>{% endif %}</td>
</tr>{% endfor %}</table>
{% else %}<p class="muted empty">Nothing yet. Push a commit whose message mentions an issue (like <code>#324</code>), or use “Test → Push events” on the GitLab webhook.</p>{% endif %}""",

"index.html": """{% extends "base.html" %}{% block content %}
<div class="head"><h1>Rules</h1><a class="btn primary" href="{{ url_for('admin.rule_new') }}">New rule</a></div>
{% if not redmine_ok %}<div class="flash error">Redmine isn't connected yet. <a href="{{ url_for('admin.settings_page') }}">Open Settings</a> to add its URL and API key.</div>{% endif %}
<div class="card" style="margin-bottom:18px">
<strong>Webhook URL</strong>&nbsp; <code class="url">{{ hook_url }}</code>
<ol class="steps small">
<li>In GitLab, open a project or group → <em>Settings → Webhooks → Add new webhook</em>.</li>
<li>Paste this URL, set <em>Secret token</em> to the token of the rule it should use, and tick <em>Push events</em>.</li>
<li>Rules that share a token can all be served by one GitLab webhook (handy for a group-level webhook).</li>
</ol></div>
<div class="card scroll">
{% if rules %}<table>
<tr><th>Name</th><th>GitLab projects</th><th>Branches</th><th>Token</th><th>Status</th><th></th></tr>
{% for r in rules %}<tr>
<td><a href="{{ url_for('admin.rule_edit', rule_id=r.id) }}">{{ r.name }}</a></td>
<td class="mono">{{ r.project or '' }}{% if not r.project %}<span class="muted">all projects</span>{% endif %}</td>
<td class="mono">{{ r.branches or '' }}{% if not r.branches %}<span class="muted">all branches</span>{% endif %}</td>
<td class="mono muted">{{ r.secret[:6] }}…</td>
<td>{% if r.enabled %}<span class="pill ok">active</span>{% else %}<span class="pill skip">paused</span>{% endif %}</td>
<td><div class="actions">
<a class="btn small" href="{{ url_for('admin.rule_edit', rule_id=r.id) }}">Edit</a>
<form method="post" action="{{ url_for('admin.rule_toggle', rule_id=r.id) }}"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn small">{{ 'Pause' if r.enabled else 'Enable' }}</button></form>
<form method="post" action="{{ url_for('admin.rule_delete', rule_id=r.id) }}" data-msg="Delete rule “{{ r.name }}”?" onsubmit="return confirm(this.dataset.msg)"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn small danger">Delete</button></form>
</div></td></tr>{% endfor %}</table>
{% else %}<p class="muted empty">No rules yet. Create one to tell the service which GitLab projects and branches to watch.</p>{% endif %}
</div>
<div class="head" style="margin:32px 0 10px"><h2 style="margin:0">Recent activity</h2><a href="{{ url_for('admin.log_page') }}">See all</a></div>
<div class="card scroll">{% include "log_table.html" %}</div>
{% endblock %}""",

"activity.html": """{% extends "base.html" %}{% block content %}
<div class="head"><h1>Activity</h1><span class="muted small">Last 300 events</span></div>
<div class="card scroll">{% include "log_table.html" %}</div>
{% endblock %}""",

"rule_form.html": """{% extends "base.html" %}{% block content %}
<div class="head"><h1>{{ 'Edit rule' if rule_id else 'New rule' }}</h1></div>
<form method="post" class="card" style="max-width:720px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label for="name">Name</label>
<input type="text" id="name" name="name" value="{{ form.name }}" placeholder="Backend – main and release branches" required>

<label for="project">GitLab projects</label>
<input type="text" id="project" name="project" class="mono" value="{{ form.project }}" placeholder="team/backend, team/frontend">
<span class="hint">Full project path as shown in GitLab. Separate several with commas; <code>*</code> works as a wildcard (<code>team/*</code>). Leave empty for all projects.</span>

<label for="branches">Branches</label>
<input type="text" id="branches" name="branches" class="mono" value="{{ form.branches }}" placeholder="main, develop, release/*">
<span class="hint">Separate with commas; wildcards allowed. Leave empty for all branches.</span>

<label for="secret">Secret token</label>
<input type="text" id="secret" name="secret" class="mono" value="{{ form.secret }}" required minlength="12">
<span class="hint">Paste this into the GitLab webhook's <em>Secret token</em> field. Webhook URL: <code>{{ hook_url }}</code></span>

<label class="check"><input type="checkbox" name="enabled" value="1" {{ 'checked' if form.enabled }}> Active</label>

<details {{ 'open' if form.issue_pattern or form.template }}>
<summary>Advanced: issue pattern and comment text</summary>
<label for="issue_pattern">Issue pattern (regular expression)</label>
<input type="text" id="issue_pattern" name="issue_pattern" class="mono" value="{{ form.issue_pattern }}" placeholder="{{ default_pattern }}">
<span class="hint">Must contain one group that captures the issue number. The default matches <code>#324</code>. Example to only match keywords: <code>(?:refs|fixes|closes)\\s+#(\\d+)</code></span>

<label for="template">Comment template</label>
<textarea id="template" name="template" placeholder="{{ default_template }}">{{ form.template }}</textarea>
<span class="hint">Leave empty for the default shown. <code>{summary}</code> inserts an AI summary of the whole push (configure it under Settings). Placeholders: <code>{short_sha}</code> <code>{sha}</code> <code>{url}</code> <code>{author}</code> <code>{message}</code> <code>{full_message}</code> <code>{project}</code> <code>{branch}</code> <code>{summary}</code></span>
</details>

<div class="formbar"><button class="btn primary">Save rule</button><a class="btn" href="{{ url_for('admin.index') }}">Cancel</a></div>
</form>
{% endblock %}""",

"assistant.html": """{% extends "base.html" %}{% block content %}
<div class="head"><h1>Assistant</h1>
<form method="post" action="{{ url_for('admin.assistant_poll') }}"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn">Check now</button></form></div>
{% if not redmine_ok %}<div class="flash error">Redmine isn't connected yet. <a href="{{ url_for('admin.settings_page') }}">Open Settings</a> first.</div>{% endif %}
<p class="muted" style="max-width:720px">Mention the assistant in a comment on a Redmine issue, e.g. <code>{{ assistant.handle }} why does the export time out?</code>. It reads the issue, inspects that project's source code and replies with a likely root cause and fix. Redmine is checked every {{ poll_seconds|int }} seconds{% if poll_seconds <= 0 %} — polling is off (<code>ASSISTANT_POLL_SECONDS=0</code>), use “Check now”{% endif %}.</p>

<form method="post" action="{{ url_for('admin.assistant_settings') }}" class="card" style="max-width:720px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label class="check" style="margin-top:4px"><input type="checkbox" name="enabled" value="1" {{ 'checked' if assistant.enabled }}> Answer mentions</label>
<span class="hint">Only comments written after it is switched on are answered.</span>

<label for="handle">Handle</label>
<input type="text" id="handle" name="handle" class="mono" value="{{ assistant.handle }}" required>
<span class="hint">What people type to call it. Making this the login of the Redmine user whose API key is saved in Settings lets Redmine autocomplete it. That user's own comments are never answered.</span>

<label for="model">Model</label>
<input type="text" id="model" name="model" class="mono" value="{{ assistant.model }}" placeholder="{{ default_model }}">
<span class="hint">Runs through the Claude Code CLI on this server, like the Claude option for push summaries.</span>
<div class="formbar"><button class="btn primary">Save</button></div>
</form>

<h2>Code directories</h2>
<div class="card scroll" style="margin-bottom:12px">
{% if projects %}<table>
<tr><th>Redmine project</th><th>Code directory</th><th>Status</th><th></th></tr>
{% for p in projects %}<tr>
<td class="mono">{{ p.redmine_project }}</td>
<td class="mono">{{ p.code_path }}</td>
<td>{% if p.enabled %}<span class="pill ok">active</span>{% else %}<span class="pill skip">paused</span>{% endif %}</td>
<td><div class="actions">
<form method="post" action="{{ url_for('admin.assistant_project_test', project_id=p.id) }}"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn small">Test</button></form>
<form method="post" action="{{ url_for('admin.assistant_project_toggle', project_id=p.id) }}"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn small">{{ 'Pause' if p.enabled else 'Enable' }}</button></form>
<form method="post" action="{{ url_for('admin.assistant_project_delete', project_id=p.id) }}" data-msg="Stop analysing “{{ p.redmine_project }}”?" onsubmit="return confirm(this.dataset.msg)"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="btn small danger">Delete</button></form>
</div></td></tr>{% endfor %}</table>
{% else %}<p class="muted empty">No projects yet. Map a Redmine project to the directory holding its source code below.</p>{% endif %}
</div>

<form method="post" action="{{ url_for('admin.assistant_project_add') }}" class="card" style="max-width:720px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label for="redmine_project">Redmine project identifier</label>
<input type="text" id="redmine_project" name="redmine_project" class="mono" placeholder="backend" required>
<span class="hint">The identifier from the project's URL (<code>/projects/<strong>backend</strong></code>). Its subprojects are included.</span>
<label for="code_path">Code directory on this server</label>
<input type="text" id="code_path" name="code_path" class="mono" placeholder="/srv/checkouts/backend" required>
<span class="hint">A checkout of the repository. The assistant can only read inside it; keep it up to date yourself (e.g. a cron <code>git pull</code>).</span>
<div class="formbar"><button class="btn primary">Add</button></div>
</form>
<p class="muted small" style="max-width:720px">Anyone who can comment on an issue can ask about the code, and the answer is posted where they can read it. Only map code those people may see.</p>
{% endblock %}""",

"settings.html": """{% extends "base.html" %}{% block content %}
<div class="head"><h1>Settings</h1></div>
<form method="post" class="card" style="max-width:720px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label for="redmine_url">Redmine URL</label>
<input type="url" id="redmine_url" name="redmine_url" value="{{ redmine_url }}" placeholder="https://redmine.example.com">

<label for="redmine_api_key">Redmine API key</label>
<input type="password" id="redmine_api_key" name="redmine_api_key" autocomplete="off" placeholder="{{ '•••••••• saved — leave empty to keep' if has_key else 'API key of the user that will post comments' }}">
<span class="hint">Use a dedicated user (e.g. <em>gitlab-bot</em>) that is a member of your Redmine projects with permission to add notes. Its key is under <em>My account → API access key</em>. The REST API must be enabled in <em>Administration → Settings → API</em>.</span>
<div class="formbar"><button class="btn primary">Save</button></div>
</form>
<form method="post" action="{{ url_for('admin.settings_test') }}" style="margin-top:12px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<button class="btn">Test connection</button>
</form>

<h2>Push summaries</h2>
<form method="post" action="{{ url_for('admin.settings_summary') }}" class="card" style="max-width:720px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label for="provider">Summarize each push with</label>
<select id="provider" name="provider">
{% for value, label in providers %}<option value="{{ value }}" {{ 'selected' if summary.provider == value }}>{{ label }}</option>{% endfor %}
</select>
<span class="hint">Off by default. A summary is only requested when a rule's comment template contains <code>{summary}</code>, so turning this on costs nothing until you use it.</span>

<label for="model">Model</label>
<input type="text" id="model" name="model" class="mono" value="{{ summary.model }}" placeholder="{{ default_claude_model }} — or e.g. qwen3:0.6b for Ollama">
<span class="hint">Leave empty for the default of the chosen provider. Small local models (under a few billion parameters) summarize fine but are easily steered by text inside a commit message, so prefer them only for repositories you trust.</span>

<label for="endpoint">Ollama address</label>
<input type="text" id="endpoint" name="endpoint" class="mono" value="{{ summary.endpoint }}" placeholder="{{ default_ollama_endpoint }}">
<span class="hint">Only used by the Ollama provider.</span>
<div class="formbar"><button class="btn primary">Save</button></div>
</form>
<form method="post" action="{{ url_for('admin.settings_summary_test') }}" style="margin-top:12px">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<button class="btn">Test summarizer</button>
</form>
<p class="muted small" style="max-width:720px">The Claude option runs the <code>claude</code> command on this server using whatever account is signed in there, which is a developer tool rather than a service API — a Claude subscription does not include API access. Ollama keeps everything on your own machine.</p>
{% endblock %}""",
}
