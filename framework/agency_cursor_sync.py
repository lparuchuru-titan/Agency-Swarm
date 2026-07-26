"""Sync Agency Swarm-style Cursor agency folders from agents_registry + skill feeds."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from agents_registry import AGENTS, TEAMS
from config import REPO_ROOT, ensure_dirs
from skill_feed_registry import feeds_for_skill, kb_paths_for_skill

AGENCY_DIR = REPO_ROOT / ".cursor" / "agency"

# Cursor subagent id -> agency folder name
CURSOR_AGENTS: List[Dict[str, str]] = [
    {"folder": "CEO", "cursor_id": "ceo", "name": "CEO Orchestrator", "description": "Client communication, routing, delegation"},
    {"folder": "jira-subtask-workflow", "cursor_id": "jira-subtask-workflow", "name": "Jira Analyst", "description": "Jira stories, subtasks, acceptance criteria"},
    {"folder": "advanced-salesforce-developer", "cursor_id": "advanced-salesforce-developer", "name": "Salesforce Developer", "description": "Apex, LWC, CPQ implementation"},
    {"folder": "sfdc-metadata-sync", "cursor_id": "sfdc-metadata-sync", "name": "Metadata Sync", "description": "Retrieve, delta sync, manifests"},
    {"folder": "sfdc-promotion-workflow", "cursor_id": "sfdc-promotion-workflow", "name": "Promotion Engineer", "description": "Sandbox to UAT promotion"},
    {"folder": "sfdc-cta-mentor", "cursor_id": "sfdc-cta-mentor", "name": "Technical Architect", "description": "Architecture blueprints and trade-offs"},
    {"folder": "codebase-explainer", "cursor_id": "codebase-explainer", "name": "Documenter", "description": "Deep dives, HTML explainers"},
    {"folder": "playwright-e2e-validation", "cursor_id": "qa-playwright", "name": "QA Engineer", "description": "Playwright E2E and regression"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _swarm_roles_for_skill(skill_id: str) -> List[str]:
    return [a["name"] for a in AGENTS if skill_id in a.get("skills", [])]


def _instructions_body(meta: Dict[str, str], skill_id: str | None) -> str:
    skill = skill_id or meta["folder"]
    spec = feeds_for_skill(skill) if skill_id else {}
    feeds = kb_paths_for_skill(skill) if skill_id else []
    open_topics = spec.get("open_topics", [])
    roles = _swarm_roles_for_skill(skill) if skill_id else ["Orchestrator"]

    lines = [
        f"# Agent Role",
        "",
        f"You are the **{meta['name']}** in the Salesforce agency (Agency-Swarm).",
        meta["description"] + ".",
        "",
        f"Cursor subagent / skill id: `{meta['cursor_id']}`",
        "",
        "# Goals",
        "",
        "- Deliver production-ready Salesforce work aligned with project conventions.",
        "- Read allowed knowledge feeds before acting (see below).",
        "- Report blockers clearly; do not guess org-specific API names or IDs.",
        "",
    ]
    if skill_id and skill_id != "ceo":
        lines.extend(
            [
                f"- Invoke skill **`{skill_id}`** (`/.cursor/skills/{skill_id}/SKILL.md` or global copy).",
                f"- Swarm roles using this skill: {', '.join(roles) or '—'}.",
                "",
            ]
        )

    if open_topics:
        lines.append("# Allowed open-source feeds")
        lines.append("")
        for topic in open_topics:
            lines.append(f"- `{topic}`")
        lines.append("")
    if feeds:
        lines.append("# Knowledge paths (restricted)")
        lines.append("")
        for path in feeds[:12]:
            lines.append(f"- `{path}`")
        lines.append("")

    lines.extend(
        [
            "# Process Workflow",
            "",
            "1. Run `sfdc-swarm context` or `python3 ~/.cursor/skills/_shared/show-context.py` for org + paths.",
            "2. Read `KNOWLEDGE-LINKS.md` and `knowledge-base/skills/feeds/" + (skill_id or "CEO") + ".md` if present.",
            "3. Execute the task using the skill guardrails and repo patterns in `force-app/`.",
            "4. Summarize changes, test commands run, and manual follow-ups.",
            "",
            f"_Generated {_now()} by agency_cursor_sync_",
        ]
    )
    return "\n".join(lines)


def _ceo_instructions() -> str:
    return f"""# Agent Role

You are the **CEO Orchestrator** of a Salesforce development agency.
You talk to the user in plain English, plan work, and **delegate** to specialist agents.
You do not implement Apex/LWC yourself unless the user explicitly asks you to do a tiny fix.

# Goals

- Understand the user request and map it to the right specialist(s).
- Launch Cursor subagents (Task tool) with clear mandates — one specialist per task when possible.
- Optionally run `sfdc-swarm orchestrate "<request>"` to produce fleet work orders, then execute them via specialists.
- Keep FleetView updated: `sfdc-swarm serve` → http://127.0.0.1:8765/

# Communication flows

Read `.cursor/agency/agency_chart.md`. You may delegate to any specialist below you.

| Specialist | Folder | When to use |
| --- | --- | --- |
| Jira Analyst | `jira-subtask-workflow/` | Stories, epics, acceptance criteria |
| Technical Architect | `sfdc-cta-mentor/` | Design, architecture, trade-offs |
| Salesforce Developer | `advanced-salesforce-developer/` | Apex, LWC, CPQ implementation |
| Metadata Sync | `sfdc-metadata-sync/` | Retrieve, manifests, org sync |
| Promotion Engineer | `sfdc-promotion-workflow/` | Deploy, promote, UAT |
| Documenter | `codebase-explainer/` | HTML explainers, change docs |
| QA Engineer | `playwright-e2e-validation/` | E2E, regression |

# Process Workflow

1. Clarify ambiguous requests in one short question if needed.
2. Read `.cursor/agency/agency_manifesto.md` for shared rules.
3. For multi-step delivery: run orchestrator OR delegate sequentially (requirements → dev → qa → docs).
4. Launch subagent with: goal, file paths, success criteria, and which skill to follow.
5. Report consolidated outcome with links to artifacts (`docs/swarm-deliveries/`, `.cursor/swarm/.fleet/runs/`).

# Tools (Cursor-native)

- **Subagents**: `.cursor/agents/<name>.md` — launch via Task tool / agent picker.
- **Skills**: `~/.cursor/skills/<skill>/SKILL.md`
- **CLI**: `sfdc-swarm orchestrate`, `sfdc-swarm skill-refresh --tier weekly`
- **MCP**: Jira/Confluence via `.cursor/mcp.json` when credentials are configured

_Generated {_now()}_
"""


def _tools_readme(skill_id: str) -> str:
    paths = [
        REPO_ROOT / ".cursor" / "skills" / skill_id / "scripts",
        Path.home() / ".cursor" / "skills" / skill_id / "scripts",
    ]
    lines = [
        f"# Tools for `{skill_id}`",
        "",
        "Agency Swarm pattern: agent-specific scripts live here.",
        "This project maps tools to the global skill:",
        "",
        f"- `~/.cursor/skills/{skill_id}/scripts/`",
        f"- `.cursor/skills/{skill_id}/scripts/` (if present)",
        "",
    ]
    for p in paths:
        if p.is_dir():
            for script in sorted(p.glob("*.py"))[:10]:
                lines.append(f"- `{script}`")
    lines.append("")
    lines.append("Add new tools as Python scripts in this folder or extend the skill scripts.")
    return "\n".join(lines) + "\n"


def sync_agency_cursor(force: bool = True) -> Dict[str, Any]:
    ensure_dirs()
    AGENCY_DIR.mkdir(parents=True, exist_ok=True)

    manifest_src = AGENCY_DIR / "agency_manifesto.md"
    if not manifest_src.is_file():
        _write_default_manifesto()

    chart_path = AGENCY_DIR / "agency_chart.md"
    _write_agency_chart(chart_path)

    agents_written: List[str] = []
    for entry in CURSOR_AGENTS:
        folder = AGENCY_DIR / entry["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        tools_dir = folder / "tools"
        tools_dir.mkdir(exist_ok=True)

        if entry["folder"] == "CEO":
            body = _ceo_instructions()
            (tools_dir / "README.md").write_text(
                "# CEO tools\n\n- `sfdc-swarm orchestrate`\n- FleetView at http://127.0.0.1:8765/\n",
                encoding="utf-8",
            )
        else:
            body = _instructions_body(entry, entry["folder"])
            (tools_dir / "README.md").write_text(_tools_readme(entry["folder"]), encoding="utf-8")

        (folder / "instructions.md").write_text(body, encoding="utf-8")
        agents_written.append(entry["folder"])

    # Root AGENTS.md for Cursor (Agency Swarm mirror pattern)
    agents_md = REPO_ROOT / "AGENTS.md"
    agents_md.write_text(_agents_md_content(), encoding="utf-8")

    return {
        "ok": True,
        "agency_dir": str(AGENCY_DIR),
        "agents": agents_written,
        "agents_md": str(agents_md),
        "chart": str(chart_path),
    }


def _write_default_manifesto() -> None:
    text = """# Salesforce Agency — Manifesto

## Agency description

Multi-agent development agency for a Salesforce DX codebase.
Specialists cover Jira requirements, architecture, Apex/LWC, metadata, promotion, documentation, and QA.

## Mission

Ship correct, bulkified, secure Salesforce changes that match existing repo patterns and Jira acceptance criteria.

## Operating environment

- **Project**: Salesforce DX repo (`sfdx-project.json`)
- **Org**: from `.sf/config.json` `target-org` (run `sfdc-swarm context`)
- **Source**: `force-app/main/default` (or Master package if configured)
- **Knowledge**: `knowledge-base/` + per-skill feeds in `knowledge-base/skills/feeds/`
- **Fleet state**: `.cursor/swarm/.fleet/`

## Shared rules (all agents)

1. Never hardcode org aliases or record IDs.
2. Enforce CRUD/FLS and bulkification in Apex.
3. Read only **allowed** knowledge paths listed in your `instructions.md` and skill `KNOWLEDGE-LINKS.md`.
4. Prefer skills and scripts over improvising CLI commands.
5. CEO orchestrates; specialists implement.

## Promotion context

Sandbox work promotes to your production metadata repo per the `sfdc-promotion-workflow` skill and `.cursor/sfdc-promotion/`.
"""
    (AGENCY_DIR / "agency_manifesto.md").write_text(text, encoding="utf-8")


def _write_agency_chart(path: Path) -> None:
    lines = [
        "# Agency communication chart",
        "",
        "Directional flows (left can initiate → right). **CEO** is the user entry point.",
        "",
        "```",
        "User → CEO",
        "CEO → jira-subtask-workflow",
        "CEO → sfdc-cta-mentor",
        "CEO → advanced-salesforce-developer",
        "CEO → sfdc-metadata-sync",
        "CEO → sfdc-promotion-workflow",
        "CEO → codebase-explainer",
        "CEO → playwright-e2e-validation",
        "jira-subtask-workflow → advanced-salesforce-developer  (story handoff)",
        "sfdc-cta-mentor → advanced-salesforce-developer  (design handoff)",
        "advanced-salesforce-developer → playwright-e2e-validation  (test handoff)",
        "advanced-salesforce-developer → codebase-explainer  (doc handoff)",
        "sfdc-metadata-sync → sfdc-promotion-workflow  (promote handoff)",
        "```",
        "",
        "In Cursor: CEO uses the **Task** tool to launch subagents matching `.cursor/agents/*.md`.",
        "",
        f"_Updated {_now()}_",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _agents_md_content() -> str:
    team_lines = "\n".join(f"- **{t['name']}** (`{t['id']}`)" for t in TEAMS[:8])
    agent_lines = "\n".join(
        f"- `{e['folder']}` — {e['description']} → `.cursor/agency/{e['folder']}/instructions.md`"
        for e in CURSOR_AGENTS
    )
    return f"""# Salesforce Agency (Cursor template)

This repo uses an **Agency Swarm-style** layout from [Agency-Swarm](https://github.com/lparuchuru-titan/Agency-Swarm) — plain-English roles, CEO delegation, per-agent instructions.

Inspired by [Agency Swarm](https://github.com/VRSEN/agency-swarm) and [Cursor + Agency guide](https://agency-swarm.ai/welcome/getting-started/cursor-ide).

## How to work (plain English)

1. Open Cursor chat and describe your task like you would to a project lead.
2. The **CEO** (this chat when following `.cursor/rules/agency-swarm-cursor.mdc`) breaks down work and delegates to specialists.
3. Specialists live in `.cursor/agency/<agent>/instructions.md` and `.cursor/agents/*.md`.
4. Watch progress: `sfdc-swarm serve` → http://127.0.0.1:8765/skills-fleet.html

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

{agent_lines}

## Teams (swarm registry)

{team_lines}

## Regenerate agency folders

After changing `agents_registry.py` or skill feeds:

```bash
python3 tools/sfdc-knowledge-swarm/agency_cursor_sync.py
```

_Last synced: {_now()}_
"""


if __name__ == "__main__":
    import json

    print(json.dumps(sync_agency_cursor(), indent=2))
