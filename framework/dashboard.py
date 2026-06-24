"""Web FleetView dashboard for agent swarm health."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from fleet import fleet_snapshot

app = FastAPI(title="SFDC Agent Fleet", version="1.0.0")


@app.get("/api/fleet")
def api_fleet():
    return JSONResponse(fleet_snapshot())


@app.get("/", response_class=HTMLResponse)
def index():
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SFDC Agent Fleet</title>
  <style>
    :root {
      --bg: #0f1419;
      --card: #1a2332;
      --border: #2d3a4f;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --green: #3dd68c;
      --yellow: #f5c542;
      --red: #f56565;
      --blue: #5b9cf5;
      --purple: #a78bfa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: ui-sans-serif, system-ui, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.5;
    }
    header {
      padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
    }
    h1 { margin: 0; font-size: 1.25rem; font-weight: 600; }
    .badge {
      padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.75rem;
      font-weight: 600; text-transform: uppercase;
    }
    .healthy { background: rgba(61,214,140,.15); color: var(--green); }
    .degraded { background: rgba(245,197,66,.15); color: var(--yellow); }
    .unhealthy { background: rgba(245,101,101,.15); color: var(--red); }
    .active { background: rgba(91,156,245,.15); color: var(--blue); }
    main { padding: 1.5rem; max-width: 1200px; margin: 0 auto; }
    .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
    .card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 10px; padding: 1rem;
    }
    .card h2 { margin: 0 0 .5rem; font-size: .95rem; color: var(--muted); }
    .stat-row { display: flex; gap: .75rem; flex-wrap: wrap; margin-top: .5rem; }
    .stat { font-size: .85rem; color: var(--muted); }
    .stat b { color: var(--text); }
    .run { margin-bottom: 1.5rem; }
    .run-head {
      display: flex; align-items: center; gap: .75rem; margin-bottom: .75rem;
      flex-wrap: wrap;
    }
    .run-title { font-weight: 600; }
    .source { color: var(--purple); font-size: .8rem; }
    .agent {
      border: 1px solid var(--border); border-radius: 8px; padding: .75rem;
      background: rgba(255,255,255,.02);
    }
    .agent-title { font-weight: 600; font-size: .9rem; }
    .agent-label { font-size: .75rem; color: var(--muted); }
    .status { font-size: .7rem; font-weight: 700; text-transform: uppercase; margin-top: .35rem; }
    .status-running { color: var(--blue); }
    .status-written { color: var(--green); }
    .status-partial { color: var(--yellow); }
    .status-error { color: var(--red); }
    .status-pending { color: var(--muted); }
    .summary { font-size: .8rem; color: var(--muted); margin-top: .5rem; }
    .skills { margin-top: 2rem; }
    .skill { font-size: .85rem; padding: .35rem 0; border-bottom: 1px solid var(--border); }
    footer { padding: 1rem 1.5rem; color: var(--muted); font-size: .75rem; text-align: center; }
  </style>
</head>
<body>
  <header>
    <h1>SFDC Agent Fleet</h1>
    <span id="health-badge" class="badge">loading</span>
    <span id="updated" style="color:var(--muted);font-size:.8rem"></span>
  </header>
  <main>
    <div class="grid" id="stats"></div>
    <section id="runs" style="margin-top:1.5rem"></section>
    <section class="skills">
      <h2 style="font-size:1rem;margin-bottom:.75rem">Skill agents (~/.claude/agents)</h2>
      <div id="skills"></div>
    </section>
  </main>
  <footer>LangChain swarm + Claude Code workflow monitor · refreshes every 3s</footer>
  <script>
    function statusClass(s) {
      return 'status status-' + (s || 'pending');
    }
    function esc(s) {
      const d = document.createElement('div');
      d.textContent = s || '';
      return d.innerHTML;
    }
    async function refresh() {
      const res = await fetch('/api/fleet');
      const data = await res.json();
      const h = data.health || {};
      const badge = document.getElementById('health-badge');
      badge.textContent = h.overall || 'unknown';
      badge.className = 'badge ' + (h.overall || '');
      document.getElementById('updated').textContent = 'Updated ' + (data.timestamp || '');

      const counts = h.counts || {};
      document.getElementById('stats').innerHTML = [
        { label: 'Score', val: h.score + '%' },
        { label: 'Running', val: counts.running || 0 },
        { label: 'Written', val: counts.written || 0 },
        { label: 'Partial', val: counts.partial || 0 },
        { label: 'Errors', val: counts.error || 0 },
        { label: 'Total', val: h.total_agents || 0 },
      ].map(c => `<div class="card"><h2>${c.label}</h2><div style="font-size:1.5rem;font-weight:700">${c.val}</div></div>`).join('');

      const runsEl = document.getElementById('runs');
      runsEl.innerHTML = (data.runs || []).map(run => {
        const agents = (run.agents || []).map(a => `
          <div class="agent">
            <div class="agent-title">${esc(a.title || a.id)}</div>
            <div class="agent-label">${esc(a.label || '')}</div>
            <div class="${statusClass(a.status)}">${esc(a.status || 'pending')}</div>
            ${a.summary ? `<div class="summary">${esc(a.summary)}</div>` : ''}
          </div>`).join('');
        return `<div class="run">
          <div class="run-head">
            <span class="run-title">${esc(run.workflow || 'workflow')} · ${esc(run.run_id)}</span>
            <span class="source">${esc(run.source)}</span>
            <span class="badge ${run.status === 'running' ? 'active' : 'healthy'}">${esc(run.status)}</span>
          </div>
          <div class="grid">${agents}</div>
        </div>`;
      }).join('') || '<p style="color:var(--muted)">No swarm runs detected yet.</p>';

      document.getElementById('skills').innerHTML = (data.skill_agents || []).map(s =>
        `<div class="skill"><b>${esc(s.name)}</b> — ${esc(s.description)}</div>`
      ).join('');
    }
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""
