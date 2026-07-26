# Multi-Agent Orchestrator Architecture

LangGraph supervisor pattern for the Salesforce dev swarm, aligned with LangGraph multi-agent docs (supervisor routes workers, shared state, conditional edges).

## Multi-project (all Cursor Salesforce repos)

The framework is **global**; each DX project gets its own org + KB paths automatically.

| Scope | Location |
|-------|----------|
| Framework code | `~/.cursor/sfdc-knowledge-swarm` |
| CLI | `sfdc-swarm` (after `install-global.sh`) |
| Per-project KB | `<repo>/knowledge-base/` (codebase, connected, project) |
| Shared open docs | `~/.cursor/sfdc-knowledge-swarm/knowledge-base/sfdc/` |
| Fleet state | `<repo>/.cursor/swarm/.fleet/` |
| Project registry | `~/.cursor/sfdc-knowledge-swarm/projects.registry.json` |

**Org resolution** (same as all skills): walk up to `sfdx-project.json`, read `.sf/config.json` `target-org`, optional `.cursor/sfdc-project/config.json`.

```bash
tools/sfdc-knowledge-swarm/install-global.sh   # once
cd any-sfdc-project && sfdc-swarm context
```

Optional per project: `.cursor/swarm/project-topics.json` for project-specific KB stubs.

Scheduled refresh for **all projects**: `launchd/com.agency-swarm.skill-refresh-all.plist`

## Two modes

| Mode | Entry | Graph | Purpose |
|------|-------|-------|---------|
| **Supervisor orchestrator** | `run.py orchestrate "…"` or FleetView **Run Orchestrator** | `plan → dispatch (loop) → finalize` | Route user input through specialist teams |
| **Codebase KB swarm** | `run.py dev-once` or **Run Swarm** | `plan → ui_ux → sf_dev → sf_admin → index` | Refresh `knowledge-base/codebase/` from `force-app/` |

Both update the same FleetView dashboard (`tools/sfdc-knowledge-swarm/.fleet/state.json`).

## Supervisor pipeline

```
START → plan (intent + agent assignment)
     → dispatch → requirements_team
     → dispatch → design_team
     → dispatch → development_team
     → dispatch → admin_team
     → dispatch → qa_team
     → dispatch → documentation_team
     → dispatch → training_team
     → finalize → END
```

`dispatch` loops until `pipeline_index >= len(pipeline)`. Intent routing (`intent_router.py`) selects a shorter pipeline when appropriate (e.g. `test` → QA + docs only).

## Agent roster (17 agents, 8 teams)

Defined in `agents_registry.py`:

| Team | Agents | Cursor skills / agents |
|------|--------|------------------------|
| Orchestrator | Swarm Orchestrator | Routes locally |
| Requirements | Jira, Confluence, GDrive, GSheets analysts | `jira-subtask-workflow`, Atlassian + Google MCP |
| Design | Technical Architect, UX Designer | `sfdc-cta-mentor`, `codebase-explainer` |
| Development | Apex, UI/LWC, Codebase worker | `advanced-salesforce-developer` |
| Admin | Salesforce Admin, Promotion Engineer | `sfdc-metadata-sync`, `sfdc-promotion-workflow` |
| QA | Playwright E2E, Apex & Data | `playwright-e2e-validation` |
| Documentation | Change Documenter | `codebase-explainer` |
| Training | Skill Trainer | Triggers codebase KB refresh |

## Python vs Cursor execution

The LangGraph layer is the **orchestration and planning plane**:

1. **Plan** — classify intent, pick pipeline, register agents in FleetView.
2. **Team nodes** — write artifacts under `.fleet/runs/{run_id}/` (requirements briefs, work orders, QA checklists).
3. **Documentation** — copies `DELIVERY.md` to `docs/swarm-deliveries/{run_id}-delivery.md`.
4. **Training** — optionally runs codebase KB swarm to refresh agent knowledge.

**Implementation** (Apex/LWC edits, Jira reads, Playwright runs) happens in **Cursor** using the work orders and mapped `cursor_agent` + skills. The orchestrator does not call Cursor APIs directly; it produces structured handoffs.

### Typical flow

1. User: `orchestrate "Implement quote line editor view for PROJ-1234"`
2. Orchestrator writes `work-apex-developer.md`, `work-ui-developer.md`, etc.
3. User opens Cursor, launches `advanced-salesforce-developer` with the work order.
4. MCP agents pull Jira/Confluence/Drive when requirements team briefs say so.
5. QA agent runs Playwright + `sf apex run test` per `qa-*.md`.
6. Documenter produces HTML deep dive via `codebase-explainer`.

## FleetView APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/fleet` | GET | Unified snapshot (runs, agents, KB) |
| `/api/orchestrate` | POST | `{"input": "your request"}` — start supervisor |
| `/api/swarm/run` | POST | Start codebase KB swarm |
| `/api/agents` | GET | Agent registry + teams |
| `/api/graph` | GET | LangGraph topology (orchestrator + legacy swarms) |

## Files

| File | Role |
|------|------|
| `langgraph_orchestrator.py` | Supervisor graph compile + `run_orchestrator()` |
| `agent_nodes.py` | Team node implementations |
| `agents_registry.py` | Agent roster, skills, MCP, intents |
| `intent_router.py` | Rule-based intent → pipeline (no API key) |
| `fleet_hooks.py` | Live state for dashboard |
| `serve_fleet.py` | HTTP server on port 8765 |
| `static/dev-swarm.html` | Live dashboard |

## Future: LLM supervisor

When `ANTHROPIC_API_KEY` is set, team nodes can use ReAct agents for synthesis (same as codebase swarm `--deep`). Intent routing can be upgraded to an LLM supervisor node that picks workers dynamically instead of rule-based `intent_router.py`.
