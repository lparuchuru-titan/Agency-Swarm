# Agency-Swarm

**Salesforce multi-agent framework for Cursor** — CEO orchestration, specialist agents, LangGraph planning, FleetView dashboard, and token-aware knowledge refresh.

Source of truth for swarm code. Consumer Salesforce DX projects link here instead of vendoring copies under `tools/`.

Inspired by [Agency Swarm](https://github.com/VRSEN/agency-swarm) and adapted for Salesforce delivery (Apex, LWC, metadata sync, sandbox promotion, Jira acceptance criteria).

---

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


---

## Validation

Before publishing or after local changes, run the deep E2E suite (no API keys required):

```bash
pip install -r framework/requirements.txt
python3 tests/test_framework.py
# or:
./scripts/validate-e2e.sh
```

CI runs the same suite on every push via `.github/workflows/validate.yml`.

## License

[MIT](LICENSE)
