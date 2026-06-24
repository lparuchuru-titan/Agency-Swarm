# Salesforce Agency (Cursor template)

This repo uses an **Agency Swarm-style** layout from [Agency-Swarm](https://github.com/lparuchuru-titan/Agency-Swarm) — plain-English roles, CEO delegation, per-agent instructions.

Inspired by [Agency Swarm](https://github.com/VRSEN/agency-swarm) and [Cursor + Agency guide](https://agency-swarm.ai/welcome/getting-started/cursor-ide).

## How to work (plain English)

1. Open Cursor chat and describe your task like you would to a project lead.
2. The **CEO** (Cursor applies rule `agency-swarm-cursor` intelligently from your prompt, or auto-attaches `agency-swarm-salesforce-files` when editing `force-app/`) breaks down work and delegates to specialists.
3. Specialists live in `.cursor/agency/<agent>/instructions.md` and `.cursor/agents/*.md`.
4. Watch progress: `sfdc-swarm serve` → http://127.0.0.1:8765/skills-fleet.html

### How Cursor applies the agency

| Mode | Rule | When it fires |
|------|------|----------------|
| **Apply Intelligently** | `agency-swarm-cursor` | Agent reads the rule `description` and pulls it in for implementation, Jira, deploy, QA, etc. |
| **Auto-attach (globs)** | `agency-swarm-salesforce-files` | When you edit or reference `force-app/`, `manifest/`, or `.cursor/agents/` |
| **Manual** | `@agency-swarm-cursor` | Force CEO mode in any chat |

Verify in **Cursor Settings → Rules** — `agency-swarm-cursor` should show type **Apply Intelligently**, not "Manual".

## Quick commands

```bash
sfdc-swarm context
sfdc-swarm orchestrate "your request"
sfdc-swarm skill-refresh --tier weekly
python3 tools/sfdc-knowledge-swarm/agency_cursor_sync.py
```

## Agency manifesto

Shared rules: `.cursor/agency/agency_manifesto.md`

## Communication chart

`.cursor/agency/agency_chart.md`

## Specialists

- `CEO` — Client communication, routing, delegation → `.cursor/agency/CEO/instructions.md`
- `jira-subtask-workflow` — Jira stories, subtasks, acceptance criteria → `.cursor/agency/jira-subtask-workflow/instructions.md`
- `advanced-salesforce-developer` — Apex, LWC, CPQ implementation → `.cursor/agency/advanced-salesforce-developer/instructions.md`
- `sfdc-metadata-sync` — Retrieve, delta sync, manifests → `.cursor/agency/sfdc-metadata-sync/instructions.md`
- `sfdc-promotion-workflow` — Sandbox to UAT promotion → `.cursor/agency/sfdc-promotion-workflow/instructions.md`
- `sfdc-cta-mentor` — Architecture blueprints and trade-offs → `.cursor/agency/sfdc-cta-mentor/instructions.md`
- `codebase-explainer` — Deep dives, HTML explainers → `.cursor/agency/codebase-explainer/instructions.md`
- `playwright-e2e-validation` — Playwright E2E and regression → `.cursor/agency/playwright-e2e-validation/instructions.md`

## Teams (swarm registry)

- **Orchestrator** (`orchestrator`)
- **Research & RAG** (`research`)
- **Design & Architecture** (`design`)
- **Development Workers** (`development`)
- **Salesforce Admin** (`admin`)
- **QA & Regression** (`qa`)
- **Documentation** (`documentation`)
- **Agent Training** (`training`)

## Regenerate agency folders

After changing `agents_registry.py` or skill feeds:

```bash
python3 tools/sfdc-knowledge-swarm/agency_cursor_sync.py
```

_Last synced: 2026-06-18T05:11:13.549601+00:00_
