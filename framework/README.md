# SFDC Knowledge Swarm + Dev Development Swarm

Unified swarm for **three development teams**, **codebase knowledge base**, and **live FleetView**.

## Agency Swarm-style Cursor template

Plain-English CEO delegation (like [Agency Swarm + Cursor](https://agency-swarm.ai/welcome/getting-started/cursor-ide)):

| Path | Purpose |
|------|---------|
| `AGENTS.md` | Agency entry — describe work in chat |
| `.cursor/agency/` | Manifesto, chart, per-agent `instructions.md` + `tools/` |
| `.cursor/rules/agency-swarm-cursor.mdc` | CEO — Apply Intelligently (no globs) |
| `.cursor/rules/agency-swarm-salesforce-files.mdc` | Auto-attach on `force-app/`, `manifest/`, agents |
| `.cursor/agents/ceo.md` | CEO subagent |

Sync from registry:

```bash
python3 run.py agency-sync
# or: python3 agency_cursor_sync.py
```

## Teams

| Team | Agents / skills | Codebase topics |
|------|-----------------|-----------------|
| **UI/UX Team** | `codebase-explainer`, `playwright-e2e-validation` | LWC, Aura, flexipages, custom UI |
| **Salesforce Team** | `advanced-salesforce-developer`, `jira-subtask-workflow`, `codebase-explainer`, `sfdc-cta-mentor` | Apex, triggers, quoting, CPQ |
| **Salesforce Admin Team** | `sfdc-metadata-sync`, `sfdc-promotion-workflow`, `jira-subtask-workflow` | Objects/fields, FLS, flows, manifests |

## Live dashboard

**The server must be running** — opening the URL alone does nothing if nothing is listening on port 8765.

```bash
cd tools/sfdc-knowledge-swarm
./start-fleet.sh
```

This opens **http://127.0.0.1:8765** in your browser and keeps the server running. **Leave the terminal open.**

If the page won't load:
```bash
lsof -ti:8765 | xargs kill -9   # stop stale server
./start-fleet.sh                  # start fresh (opens browser)
```

**Always-on (optional):**
```bash
cp launchd/com.agency-swarm.dev-swarm-fleetview.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.agency-swarm.dev-swarm-fleetview.plist
```

Shows: team KB progress, active swarm agents, knowledge catalog, schedule status, registered skill agents.

## LangGraph architecture

### Supervisor orchestrator (user requests)

Routes natural-language input through specialist teams:

```
START → plan → dispatch (requirements → design → dev → admin → qa → docs → training) → finalize → END
```

```bash
python3 run.py orchestrate "Implement quote line editor view for PROJ-1234"
```

FleetView: enter request in **Supervisor orchestrator** box → **Run Orchestrator**.

Artifacts: `.fleet/runs/{run_id}/` and `docs/swarm-deliveries/{run_id}-delivery.md`

See `ARCHITECTURE.md` for agent roster, Cursor handoff model, and APIs.

### Codebase KB swarm (scheduled refresh)

```
START → plan → ui_ux_team → salesforce_dev_team → salesforce_admin_team → index → END
```

Doc swarm (`langgraph_doc_swarm.py`):

```
START → plan → research (loop per topic) → index → END
```

Each team node scans `force-app/` for its topics. With `--deep` + `ANTHROPIC_API_KEY`, topics get a **ReAct agent** (`create_react_agent`) for synthesis.

Graph topology API: `GET /api/graph` on the FleetView server.

## Install (required for swarm runs)

```bash
pip install -r requirements.txt
```

Static scan of `force-app/` — **no API key**:

```bash
python3 run.py dev-once              # all teams, stale/missing topics
python3 run.py dev-once --force      # refresh all codebase topics
python3 run.py dev-once --teams ui-ux salesforce-dev
python3 run.py dev-once --deep       # + LangChain if ANTHROPIC_API_KEY set
```

Output: `knowledge-base/codebase/<topic>.md` + `knowledge-base/codebase/INDEX.md`

## Skill refresh schedule (token-aware)

Keeps agent skills linked to fresh KB + connected/open resources without burning tokens daily.

| Tier | Cadence | What | Tokens |
|------|---------|------|--------|
| `daily` | 02:00 daily | Codebase static scan + skill manifest | **0** |
| `weekly` | Sun 03:00 | Jira/Confluence/Drive indexes + open doc static fetch | **0** |
| `monthly` | 1st 04:00 | Stale-only LLM synthesis (max 2 topics) | **Low** |

```bash
python3 run.py skill-refresh --tier weekly      # manifest + connected + open static
python3 run.py skill-refresh --tier all_light   # everything except LLM
python3 run.py skill-refresh --tier open_deep   # stale LLM (needs ANTHROPIC_API_KEY)
python3 run.py skill-refresh-schedule           # in-process cron (keep terminal open)
```

**launchd (recommended — always-on Mac):**

```bash
cd tools/sfdc-knowledge-swarm/launchd
cp com.agency-swarm.skill-refresh-daily.plist ~/Library/LaunchAgents/
cp com.agency-swarm.skill-refresh-weekly.plist ~/Library/LaunchAgents/
cp com.agency-swarm.skill-refresh-monthly.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.agency-swarm.skill-refresh-daily.plist
launchctl load ~/Library/LaunchAgents/com.agency-swarm.skill-refresh-weekly.plist
launchctl load ~/Library/LaunchAgents/com.agency-swarm.skill-refresh-monthly.plist
```

**Connected resources (Jira REST — optional, still 0 LLM tokens):**

```bash
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="you@company.com"
export JIRA_API_TOKEN="..."
export JIRA_PROJECT_KEYS="PROJ"
```

Without credentials, connected refresh writes MCP checklists for Cursor (Atlassian + Google Workspace MCPs).

**Outputs:**

- `knowledge-base/skills/MANIFEST.md` — skill ↔ KB map
- `.cursor/skills/<skill>/KNOWLEDGE-LINKS.md` — pointer files per skill
- `knowledge-base/connected/` — Jira, Confluence, Drive/Sheets indexes
- `knowledge-base/sfdc/` — open docs (static excerpts or LLM when monthly)

Tune cost: `REFRESH_AFTER_DAYS=14`, `SKILL_DEEP_MAX_TOPICS=2`, `SKILL_OPEN_STATIC_MAX=6000`

## Schedule (legacy dev swarm)

```bash
python3 run.py dev-schedule          # dev swarm at SWARM_CRON (default 02:00)
python3 run.py schedule              # dev + doc swarm
```

**launchd** (weekly Sunday 02:15 — superseded by skill-refresh-daily for codebase):

```bash
cp launchd/com.agency-swarm.dev-development-swarm.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.agency-swarm.dev-development-swarm.plist
```

## Knowledge base layout

```
knowledge-base/
  codebase/     ← dev swarm (force-app scan)
  connected/    ← Jira, Confluence, Drive/Sheets indexes
  skills/       ← MANIFEST.md + sync state
  project/      ← your org's architecture notes
  sfdc/         ← public Salesforce docs (static or LLM)
  INDEX.md
```

## CLI summary

| Command | Purpose |
|---------|---------|
| `serve` / `serve_fleet.py` | Live HTML dashboard |
| `skill-refresh` | Tiered KB/skill refresh (token-aware) |
| `skill-refresh-schedule` | In-process scheduler for all tiers |
| `orchestrate` | Supervisor agent pipeline |
| `dev-once` | Codebase KB swarm (3 teams) |
| `dev-schedule` | Daily scheduled dev swarm |
| `once` | Public docs LangChain swarm (API key) |
| `fleet` / `watch` | Terminal fleet view |

## Files

```
teams.py           — UI/UX, Salesforce Dev, Admin team definitions
codebase_indexer.py — static force-app scanner
dev_swarm.py       — orchestrator + KB catalog API
fleet.py           — unified snapshot (Claude + dev + langchain runs)
static/dev-swarm.html — FleetView UI
```
