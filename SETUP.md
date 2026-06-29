# SFDC Agent Swarm — Complete Setup Guide

Get the swarm running against **any Salesforce sandbox** in under 30 minutes.

---

## Prerequisites (install these first)

| Tool | Min version | Install | Verify |
|---|---|---|---|
| **Cursor IDE** | Any | [cursor.com](https://cursor.com) | Open Cursor |
| **Salesforce CLI** | v2+ | `npm install -g @salesforce/cli` | `sf --version` |
| **Node.js** | v18+ | [nodejs.org](https://nodejs.org) | `node --version` |
| **Python** | v3.9+ | [python.org](https://python.org) | `python3 --version` |
| **Git** | Any | [git-scm.com](https://git-scm.com) | `git --version` |

> **macOS shortcut:** `brew install node python@3.11 git` then install Salesforce CLI.

---

## Step 1 — Clone and install globally

```bash
git clone https://github.com/lparuchuru-titan/Agency-Swarm ~/Agency-Swarm
cd ~/Agency-Swarm

# Install Python dependencies (LangGraph orchestrator)
pip install -r framework/requirements.txt

# Install the sfdc-swarm CLI globally
./install.sh

# Install Node.js dependency for Cursor SDK (agents need this to call Cursor LLM)
cd /tmp && npm install @cursor/sdk @bufbuild/protobuf
mkdir -p ~/.cursor/sfdc-knowledge-swarm/node_modules
cp -r /tmp/node_modules/@cursor ~/.cursor/sfdc-knowledge-swarm/node_modules/
cp -r /tmp/node_modules/@bufbuild ~/.cursor/sfdc-knowledge-swarm/node_modules/

# Install global skills (agent knowledge files)
./scripts/install-skills.sh
```

Verify everything works:
```bash
sfdc-swarm --version
node ~/.cursor/sfdc-knowledge-swarm/cursor_agent_runner.js --prompt "test" 2>&1 | head -3
# → should show {"type":"error","text":"CURSOR_API_KEY not set..."}  (expected — means Node works)
```

---

## Step 2 — Authenticate to your Salesforce org

The swarm reads **whatever org is currently active** in sf CLI. No hardcoded aliases.

```bash
# Log in to your sandbox
sf org login web --alias MY_SANDBOX --instance-url https://test.salesforce.com

# Set it as the default for your project
cd /path/to/your/sfdx-project
sf config set target-org MY_SANDBOX

# Verify the swarm sees it
sfdc-swarm context
# → Project: MyProject  Org: MY_SANDBOX  Root: /path/to/sfdx-project
```

> **Switch sandboxes anytime:** `sf config set target-org OTHER_SANDBOX` — swarm picks it up immediately.

---

## Step 3 — Copy the agency template into your SFDX project

```bash
cd ~/Agency-Swarm
./scripts/install-to-project.sh --global-skills /path/to/your/sfdx-project
```

This creates:
- `tools/sfdc-knowledge-swarm` → symlink to `~/Agency-Swarm/framework`
- `.cursor/agency/` — CEO + all specialist instructions
- `.cursor/agents/` — Cursor subagent definitions
- `.cursor/rules/` — Cursor auto-attach rules
- `.cursor/skills/` — specialist skills
- `AGENTS.md` — agency entry point

---

## Step 4 — Configure for your project (2 minutes)

Copy the config template and fill in your details:

```bash
cp ~/Agency-Swarm/swarm.config.json /path/to/your/sfdx-project/swarm.config.json
```

Edit `swarm.config.json` — only these matter:
```json
{
  "project": {
    "name": "My Salesforce Project"
  },
  "jira": {
    "project_key": "YOUR-KEY",
    "base_url": "https://yourcompany.atlassian.net"
  },
  "promotion": {
    "repo_name": "your-sfdc-prod-repo",
    "base_branch": "main"
  }
}
```

Everything else is optional or auto-detected.

---

## Step 5 — Get your Cursor API key

Agents run via the **Cursor SDK** — same LLM, same subscription, no extra cost.

1. Go to [cursor.com/dashboard/integrations](https://cursor.com/dashboard/integrations)
2. Generate a **User API key** (starts with `cursor_`)
3. Set it:

```bash
# Temporary (current session)
export CURSOR_API_KEY=cursor_...

# Permanent (recommended)
echo 'export CURSOR_API_KEY=cursor_...' >> ~/.zshrc
source ~/.zshrc

# Or save to .env in project root (auto-loaded by start-fleetview.sh)
echo 'CURSOR_API_KEY=cursor_...' > /path/to/your/sfdx-project/.env
```

---

## Step 6 — Configure Cursor rules

In **Cursor Settings → Rules** (`Cmd+,`):

| Rule | Type | Purpose |
|---|---|---|
| `agency-swarm-cursor` | **Apply Intelligently** | CEO routes your requests to agents automatically |
| `agency-swarm-salesforce-files` | Auto-attach on `force-app/**` | Salesforce context loads when editing org files |
| `project-memory` | Auto-attach | Loads project decisions and constraints |

---

## Step 7 — Start FleetView

```bash
cd /path/to/your/sfdx-project
./start-fleetview.sh
```

Keep this terminal open. Then visit:
- **`http://127.0.0.1:8765/dev-swarm.html`** — Orchestrator (run tasks)
- **`http://127.0.0.1:8765/skills-fleet.html`** — Skills & Agents (feeds, org scan)

---

## Step 8 — Connect MCP tools (optional but powerful)

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "mcp-remote",
               "https://mcp.atlassian.com/v1/mcp/authv2",
               "--resource", "https://YOURCOMPANY.atlassian.net/"],
      "env": { "NODE_TLS_REJECT_UNAUTHORIZED": "0" }
    },
    "slack": {
      "url": "https://mcp.slack.com/mcp",
      "auth": { "CLIENT_ID": "3660753192626.8903469228982" }
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--autoConnect",
               "--allowedUrlPattern", "*://*.salesforce.com/*",
               "--allowedUrlPattern", "*://*.force.com/*",
               "--viewport", "1440x900"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }
    }
  }
}
```

Authenticate each MCP in **Cursor Settings → MCP** → click Connect.

---

## Run your first task

Open `http://127.0.0.1:8765/dev-swarm.html` and type:

```
Analyze the security model of this org
```

The orchestrator will:
1. **Org Scout** → SOQL scan of all metadata (22 types) + retrieve permission files
2. **Cursor LLM** → analyse real org data and write findings
3. **Change Documenter** → produce an HTML report with recommendations

---

## Refresh skill feeds

Agent knowledge is refreshed separately from org data:

```bash
# Free: static Salesforce docs + OSS frameworks (runs in seconds)
sfdc-swarm skill-refresh --tier daily

# Free: Jira/Confluence/Drive indexes via MCP (needs MCPs connected)
sfdc-swarm skill-refresh --tier weekly
```

Or click **Sync Skill Feeds** in `skills-fleet.html`.

---

## How org-switching works

The swarm is fully dynamic — no org aliases, record IDs, or project names are hardcoded:

| What you do | How the swarm adapts |
|---|---|
| `sf config set target-org NEW_SANDBOX` | All SOQL, retrieves, deploys → NEW_SANDBOX |
| Edit `swarm.config.json` jira key | Jira Analyst uses your project key |
| New custom agent needed | Add to `agents_registry.py` → run `sfdc-swarm agency-sync` |
| New knowledge topic needed | Add URL to `config.py TOPICS` → `sfdc-swarm skill-refresh --force` |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `sfdc-swarm: command not found` | `export PATH=$HOME/.local/bin:$PATH` (or run `~/.local/bin/sfdc-swarm`) |
| `sfdc-swarm context` shows wrong org | `sf config set target-org <alias>` in your project folder |
| Agents can't reach org | `sf org login web --alias <alias>` — re-authenticate |
| `CURSOR_API_KEY not set` | `export CURSOR_API_KEY=cursor_...` or set in FleetView API key panel |
| FleetView won't start (port in use) | `lsof -ti:8765 \| xargs kill -9` then `./start-fleetview.sh` |
| SSL cert errors (corporate proxy) | `export NODE_TLS_REJECT_UNAUTHORIZED=0` in your shell |
| `Cannot find module '@cursor/sdk'` | Re-run the Node.js install step from Step 1 |
| Agents produce generic text (no org data) | Check Org Scout is in the pipeline — run a `discover` intent request |

---

## What each agent does

| Agent | When it runs | What it produces |
|---|---|---|
| **Org Scout** | Every research request | Full org metadata scan → `RESEARCH.md` |
| **Jira Analyst** | When Jira ticket mentioned | Requirements → `requirements-*.md` |
| **Technical Architect** | Design/architecture requests | Architecture blueprint → `design-*.md` |
| **Apex Developer** | Implementation requests | Apex code + tests → `work-apex-developer.md` |
| **UI Developer** | LWC/UI requests | LWC components → `work-ui-developer.md` |
| **Salesforce Admin** | Metadata/FLS/deploy requests | Deploy plan → `admin-*.md` |
| **PR Reviewer** | Review requests | APPROVE/BLOCK with checklist → `docs/reviews/` |
| **QA Engineer** | Testing requests | Test plan + Playwright spec → `qa-*.md` |
| **Promotion Engineer** | Deploy/promote requests | Promotion runbook → `admin-*.md` |
| **Change Documenter** | Always (final step) | HTML delivery summary → `docs/swarm-deliveries/` |
| **Org Analyst** | Audit requests | Health score + security report → `docs/explainers/` |
| **Reverse Engineer** | Document org requests | BRD + ERD + data dictionary → `docs/explainers/` |
