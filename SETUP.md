# SFDC Agent Swarm — Setup Guide

Get the swarm running against **any Salesforce sandbox** in under 30 minutes.

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Cursor IDE | Any | `cursor --version` |
| Salesforce CLI | v2+ | `sf --version` |
| Node.js | v18+ | `node --version` |
| Python | v3.9+ | `python3 --version` |

---

## Step 1 — Clone and install

```bash
git clone https://github.com/lparuchuru-titan/Agency-Swarm ~/Agency-Swarm
cd ~/Agency-Swarm
./install-global.sh          # installs sfdc-swarm CLI globally
pip install -r framework/requirements.txt
```

Verify:
```bash
sfdc-swarm --version
sfdc-swarm context           # should print your default org and project root
```

---

## Step 2 — Connect to your Salesforce org

The swarm reads **whatever org is currently active** in your Salesforce CLI. No hardcoded org aliases.

```bash
# Authenticate to your sandbox
sf org login web --alias MY_SANDBOX

# Set it as default for the project
cd /path/to/your/sfdx-project
sf config set target-org MY_SANDBOX

# Verify the swarm can see it
sfdc-swarm context
# → Project: ...  Org: MY_SANDBOX
```

> **Switch sandboxes anytime** — just run `sf config set target-org <alias>` and the swarm automatically uses the new org on next run. No config files to update.

---

## Step 3 — Copy the agency template into your SFDX project

```bash
cp -r ~/Agency-Swarm/templates/cursor/.cursor /path/to/your/sfdx-project/
cp ~/Agency-Swarm/templates/cursor/AGENTS.md /path/to/your/sfdx-project/
```

---

## Step 4 — Configure for your project

Copy and edit the config file:

```bash
cp ~/Agency-Swarm/swarm.config.json /path/to/your/sfdx-project/swarm.config.json
```

Edit `swarm.config.json`:
```json
{
  "project": { "name": "Your Project Name" },
  "jira": {
    "project_key": "YOUR_JIRA_KEY",
    "base_url": "https://yourcompany.atlassian.net"
  },
  "promotion": {
    "repo_name": "your-sfdc-repo",
    "base_branch": "main"
  }
}
```

---

## Step 5 — Set your Cursor API key

```bash
# Get your key at cursor.com/dashboard/integrations
export CURSOR_API_KEY=cursor_...

# Or add to your shell profile for persistence
echo 'export CURSOR_API_KEY=cursor_...' >> ~/.zshrc
```

---

## Step 6 — Configure Cursor rules

In **Cursor Settings → Rules**:
- `agency-swarm-cursor` → set to **Apply Intelligently**
- `agency-swarm-salesforce-files` → set to **Auto-attach** on `force-app/**`

---

## Step 7 — Start FleetView and run a task

```bash
cd /path/to/your/sfdx-project
./start-fleetview.sh         # keeps running in this terminal tab
```

Open `http://127.0.0.1:8765` and type a task.

---

## How org-switching works

The swarm is **fully dynamic** — it never hardcodes org aliases, record IDs, or sandbox-specific names:

| What you change | How the swarm adapts |
|---|---|
| `sf config set target-org NEW_ORG` | All SOQL, retrieves, and deployments use NEW_ORG |
| Connect to a different Jira project | Update `swarm.config.json` → `jira.project_key` |
| Different Cursor API key | Update `CURSOR_API_KEY` env var |
| New agent needed | Add to `agents_registry.py` → run `agency_cursor_sync.py` |

---

## Connect MCP tools (optional but powerful)

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.atlassian.com/v1/mcp/authv2",
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
               "--allowedUrlPattern", "*://*.force.com/*"]
    }
  }
}
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `sfdc-swarm context` shows wrong org | `sf config set target-org <alias>` in the project folder |
| Agents can't query org | `sf org login web --alias <alias>` — re-authenticate |
| FleetView won't start | `lsof -ti:8765 \| xargs kill -9` then `./start-fleetview.sh` |
| `CURSOR_API_KEY not set` | `export CURSOR_API_KEY=cursor_...` or set in FleetView UI |
| SSL cert errors | Add `NODE_TLS_REJECT_UNAUTHORIZED=0` to your shell env |
