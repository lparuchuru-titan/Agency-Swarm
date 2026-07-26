# Agency-Swarm

**Salesforce multi-agent framework for Cursor** — CEO orchestration, specialist agents, LangGraph planning, FleetView dashboard, and token-aware knowledge refresh.

Source of truth for swarm code. Consumer Salesforce DX projects link here instead of vendoring copies under `tools/`.

Inspired by [Agency Swarm](https://github.com/VRSEN/agency-swarm) and adapted for Salesforce delivery (Apex, LWC, metadata sync, sandbox promotion, Jira acceptance criteria).

---

## Live demo (video)

FleetView walkthrough recorded against a local Agency-Swarm install (fixture SFDX project — no customer org data):

**[▶ Watch demo video](docs/blog/assets/agency-swarm-fleetview-demo.webm)** · [Poster image](docs/blog/assets/agency-swarm-fleetview-poster.png)

<video src="docs/blog/assets/agency-swarm-fleetview-demo.webm" controls width="100%" poster="docs/blog/assets/agency-swarm-fleetview-poster.png">
  Your browser does not support HTML5 video. <a href="docs/blog/assets/agency-swarm-fleetview-demo.webm">Download the demo</a>.
</video>

What the recording shows:

1. **Skills Fleet** (`/skills-fleet.html`) — agents, skills, fleet health  
2. **Orchestrator home** (`/`) — run pipeline / delivery view  
3. **Swarm Fleet** + **Dev Swarm** dashboards  

Re-record locally (requires Playwright + browsers):

```bash
# terminal 1 — from a wired SFDX project
sfdc-swarm serve --port 8770

# terminal 2 — from a project that has playwright installed
export PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright"
FLEET_URL=http://127.0.0.1:8770 OUT_DIR=/tmp/agency-rec   node path/to/Agency-Swarm/scripts/record-fleetview-demo.mjs
```

## Prerequisites

Install these **before** cloning. Agency-Swarm will not work without them.

### Required

| Tool | Min version | Why | Install | Verify |
|------|-------------|-----|---------|--------|
| **[Cursor IDE](https://cursor.com)** | Latest | Host for agents, skills, and CEO orchestration | Download from cursor.com | Open Cursor |
| **[Salesforce CLI](https://developer.salesforce.com/tools/salesforcecli)** (`sf`) | v2+ | Org context, retrieve/deploy, SOQL | `npm install -g @salesforce/cli` | `sf --version` |
| **[Python](https://www.python.org/)** | 3.9+ (3.11 recommended) | CLI, LangGraph orchestrator, FleetView | `brew install python@3.11` or python.org | `python3 --version` |
| **[Node.js](https://nodejs.org/)** | 18+ | Cursor SDK agent runner (`cursor_agent_runner.js`) | `brew install node` or nodejs.org | `node --version` |
| **[Git](https://git-scm.com/)** | Any | Clone + install scripts | `brew install git` | `git --version` |
| **Salesforce DX project** | — | Must contain `sfdx-project.json` | Your existing SFDX repo | `ls sfdx-project.json` |

macOS one-liner for CLI tools:

```bash
brew install node python@3.11 git
npm install -g @salesforce/cli
```

Also ensure `~/.local/bin` is on your `PATH` (the `sfdc-swarm` shim is installed there):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

### Python packages (required for orchestrator)

```bash
pip install -r framework/requirements.txt
```

Installs: `langgraph`, `langchain`, `langchain-anthropic`, `rich`, `httpx`, `schedule`.  
FleetView (`sfdc-swarm serve`) itself uses the Python standard library only, but the CLI still imports these packages.

### Node packages (required for live Cursor agents)

After `./install.sh`, install the Cursor SDK into the global swarm home:

```bash
cd /tmp && npm install @cursor/sdk @bufbuild/protobuf
mkdir -p ~/.cursor/sfdc-knowledge-swarm/node_modules
cp -r /tmp/node_modules/@cursor ~/.cursor/sfdc-knowledge-swarm/node_modules/
cp -r /tmp/node_modules/@bufbuild ~/.cursor/sfdc-knowledge-swarm/node_modules/
```

### Salesforce org (required for real org work)

```bash
sf org login web --alias MY_SANDBOX --instance-url https://test.salesforce.com
cd /path/to/your-sfdx-project
sf config set target-org MY_SANDBOX
sfdc-swarm context   # should show project + org
```

No org alias is hardcoded. The swarm reads `.sf/config.json` / `sf config get target-org`.

### Optional (enable richer features)

| Item | Env / setup | What it unlocks |
|------|-------------|-----------------|
| **Cursor API key** | `export CURSOR_API_KEY=cursor_...` ([dashboard](https://cursor.com/dashboard/integrations)) | Live specialist agents during `orchestrate` (without it, teams run in offline stub mode) |
| **Anthropic API key** | `export ANTHROPIC_API_KEY=sk-ant-...` | LangChain LLM intent router fallback |
| **Atlassian MCP** | Cursor MCP for Jira/Confluence | Jira Analyst / Confluence feeds |
| **Google Workspace MCP** | Cursor MCP for Drive/Docs/Sheets | Drive/Sheets research agents |
| **`swarm.config.json`** | Copy from repo root into your SFDX project | Jira project key, promotion repo hints |

### What works with zero API keys

These work after prerequisites + install only (no `CURSOR_API_KEY`):

- `sfdc-swarm --help` / `context` / `fleet` / `agency-sync`
- `sfdc-swarm serve` (FleetView dashboard)
- `sfdc-swarm skill-refresh --tier manifest|weekly` (token-light KB refresh)
- Offline `orchestrate` routing + work-order scaffolding
- `python3 tests/test_framework.py` (full E2E suite)

Live Apex/LWC implementation via Cursor agents needs `CURSOR_API_KEY`.

## Repository layout

```
Agency-Swarm/
├── framework/              # Python LangGraph orchestrator, FleetView, KB indexer
├── templates/
│   ├── cursor/
│   │   ├── agency/         # Per-agent instructions (CEO, dev, QA, …)
│   │   ├── agents/         # Cursor subagent definitions
│   │   ├── rules/          # agency-swarm-cursor, swarm-framework, …
│   │   └── skills/         # Global Cursor skills (Apex, metadata sync, Jira, …)
│   └── project/
│       ├── AGENTS.md       # Entry point copied into DX projects
│       └── project-topics.example.json
├── docs/                   # Architecture, blog, implementation guide
├── scripts/
│   ├── install-to-project.sh
│   └── install-skills.sh
└── install.sh              # Global CLI (~/.cursor/sfdc-knowledge-swarm)
```

**Not in this repo (runtime, per project):**

| Path | Lives in |
|------|----------|
| `knowledge-base/codebase/*.md` | Each DX project |
| `.cursor/swarm/.fleet/` | Each DX project |
| `docs/swarm-deliveries/` | Each DX project |

---

## Quick start

### 1. Clone and install globally (once per machine)

```bash
git clone https://github.com/lparuchuru-titan/Agency-Swarm.git
cd Agency-Swarm
pip install -r framework/requirements.txt
./install.sh
./scripts/install-skills.sh
```

This installs:

- `~/.cursor/sfdc-knowledge-swarm` — framework copy
- `~/.local/bin/sfdc-swarm` — CLI
- `~/.cursor/skills/*` — specialist skills

### 2. Wire into a Salesforce DX project

```bash
cd /path/to/your-sfdx-project
/path/to/Agency-Swarm/scripts/install-to-project.sh --global-skills .
```

Creates:

- `tools/sfdc-knowledge-swarm` → symlink to `Agency-Swarm/framework`
- `.cursor/agency/`, `.cursor/agents/`, `.cursor/rules/`
- `AGENTS.md` (if missing)

### 3. Use from your project

```bash
sfdc-swarm context                              # resolve org from .sf/config.json
sfdc-swarm serve                                # FleetView → http://127.0.0.1:8765
sfdc-swarm orchestrate "Implement feature X"      # LangGraph work orders
sfdc-swarm skill-refresh --tier weekly          # KB refresh (0 LLM tokens)
```

In Cursor: describe work in plain English, or `@agency-swarm-cursor` for CEO mode.

---

## When to use the swarm

| Use | Skip |
|-----|------|
| Jira epics spanning metadata + Apex + LWC + promotion | One-line typo fixes |
| Retrieve → implement → test → promote | Quick SOQL / single-method edits |
| Onboarding to a large repo | Simple chat Q&A |
| Architecture docs + HTML explainers | |

---

## Updating consumer projects

After pulling changes in Agency-Swarm:

```bash
cd Agency-Swarm && git pull
./framework/install-global.sh                  # refresh global copy
cd /path/to/your-sfdx-project
./path/to/Agency-Swarm/scripts/install-to-project.sh --global-skills .
```

Regenerate agency folders from registry (optional):

```bash
cd /path/to/your-sfdx-project
sfdc-swarm agency-sync
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | LangGraph pipelines, agent roster, FleetView APIs |
| [docs/FRAMEWORK-README.md](docs/FRAMEWORK-README.md) | Detailed framework CLI reference |
| [docs/blog/20260624-sfdc-agent-swarm-blog.html](docs/blog/20260624-sfdc-agent-swarm-blog.html) | Publishable blog + screenshots |

---

## Development

Change agents or skill feeds in `framework/agents_registry.py`, then:

```bash
cd /path/to/your-sfdx-project   # or any wired project
sfdc-swarm agency-sync
```

Commit changes in **this repo** (`framework/`, `templates/`). Consumer projects pick them up via `git pull` + `install-to-project.sh`.

---

## Validation

Before publishing or after local changes, run the deep E2E suite (no API keys required):

```bash
pip install -r framework/requirements.txt
python3 tests/test_framework.py
# or:
./scripts/validate-e2e.sh
```

CI template: copy `docs/ci/github-actions-validate.yml` to `.github/workflows/validate.yml` (requires a GitHub token with `workflow` scope).

## License

[MIT](LICENSE)
