"""LangGraph team nodes — execute agent work and update fleet state."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from agents_registry import AGENTS, agents_for_team
from codebase_indexer import build_topic_note
from config import (
    CODEBASE_NOTES_DIR,
    FLEET_DIR,
    GLOBAL_SFDC_NOTES_DIR,
    KB_DIR,
    REPO_ROOT,
    ensure_dirs,
    get_runtime,
)
from fleet_hooks import mark_team_phase, update_agent
from teams import CODEBASE_TOPICS

FLEET_RUNS = FLEET_DIR / "runs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(run_id: str) -> Path:
    d = FLEET_RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _agents_for_team_ids(team_id: str, assigned: List[str]) -> List[Dict[str, Any]]:
    team_agents = agents_for_team(team_id)
    if not assigned:
        return team_agents
    ids = set(assigned)
    picked = [a for a in AGENTS if a["id"] in ids and a.get("team") == team_id]
    return picked or team_agents


def _write_artifact(run_id: str, name: str, content: str) -> str:
    path = _run_dir(run_id) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _kb_snippet(topic_keys: List[str], max_chars: int = 6000) -> str:
    chunks: List[str] = []
    for key in topic_keys:
        for base in [CODEBASE_NOTES_DIR, KB_DIR / "project", KB_DIR / "nextgen2", GLOBAL_SFDC_NOTES_DIR, KB_DIR / "sfdc"]:
            path = base / f"{key.replace('codebase/', '').replace('nextgen2/', '').replace('sfdc/', '')}.md"
            if not path.suffix:
                path = base / f"{key.split('/')[-1]}.md"
            if path.exists():
                chunks.append(f"### {path}\n{path.read_text(encoding='utf-8')[:2000]}")
    text = "\n\n".join(chunks)
    return text[:max_chars]


def run_requirements_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "requirements", "gathering requirements", "requirements_team")
    assigned = state.get("assigned_agents", [])
    outcomes: List[Dict[str, Any]] = []

    for agent in _agents_for_team_ids("requirements", assigned):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "requirements"})
        brief_parts = [
            f"# Requirements brief — {agent['name']}",
            f"_Generated {_now()}_",
            "",
            f"**User request:** {state['user_input']}",
            "",
            f"**Agent:** {agent['id']} · MCP: {', '.join(agent.get('mcp', []))}",
            "",
            "## Cursor execution",
            f"Launch Cursor agent: `{agent.get('cursor_agent')}` with skill `{', '.join(agent.get('skills', []))}`",
            "",
            "## MCP actions (in Cursor)",
        ]
        for mcp in agent.get("mcp", []):
            brief_parts.append(f"- Call `{mcp}` for topics in user request")
        if "jira" in agent["id"]:
            import re
            keys = re.findall(r"SFDCLQ-\d+", state["user_input"], re.I)
            if keys:
                brief_parts.append(f"\n**Jira keys detected:** {', '.join(keys)}")
        path = _write_artifact(run_id, f"requirements-{agent['id']}.md", "\n".join(brief_parts))
        update_agent(
            run_id,
            agent["id"],
            {"status": "written", "ended_at": _now(), "summary": f"brief → {path}", "note_path": path},
        )
        outcomes.append({"agent": agent["id"], "status": "written", "artifact": path})

    return {"phase": "requirements_done", "artifacts": outcomes}


def _load_connected_indexes(max_chars: int = 4000) -> str:
    conn = KB_DIR / "connected"
    if not conn.is_dir():
        return "_No connected indexes — run skill-refresh --tier weekly._"
    parts: List[str] = []
    for path in sorted(conn.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        parts.append(f"### {path.name}\n{path.read_text(encoding='utf-8')[:1500]}")
    text = "\n\n".join(parts)
    return text[:max_chars] if text else "_Connected folder empty._"


def run_research_team(state: Dict[str, Any]) -> Dict[str, Any]:
    """Research subgraph: KB + connected indexes (video-style research before workers)."""
    run_id = state["run_id"]
    mark_team_phase(run_id, "research", "KB + connected research", "research_team")
    ctx = get_runtime()
    agent_id = "kb-researcher"
    update_agent(run_id, agent_id, {"status": "running", "started_at": _now(), "team_id": "research"})

    kb_chunks: List[str] = []
    # Codebase index sample
    idx = CODEBASE_NOTES_DIR / "INDEX.md"
    if idx.exists():
        kb_chunks.append(f"### codebase/INDEX.md\n{idx.read_text(encoding='utf-8')[:2000]}")

    # Keyword-driven codebase topics
    text = state["user_input"].lower()
    for topic in CODEBASE_TOPICS[:6]:
        for kw in topic.get("grep", [])[:3]:
            if kw.lower() in text:
                path = CODEBASE_NOTES_DIR / f"{topic['key']}.md"
                if path.exists():
                    kb_chunks.append(f"### {topic['key']}\n{path.read_text(encoding='utf-8')[:1500]}")
                break

    connected = _load_connected_indexes()
    snippets = _kb_snippet([], max_chars=3000) if not kb_chunks else "\n\n".join(kb_chunks)[:6000]

    body = [
        f"# Research brief — KB + connected resources",
        f"_Generated {_now()}_",
        "",
        f"**Request:** {state['user_input']}",
        f"**Project:** {ctx.get('projectName')} · **Org:** `{ctx.get('targetOrgAlias')}`",
        "",
        "## Codebase / project KB",
        snippets or "_Run skill-refresh or dev-once to populate codebase KB._",
        "",
        "## Connected resources (Jira / Confluence / Drive indexes)",
        connected,
        "",
        "## Next steps",
        "- Development agents should read this file before implementing",
        "- Use MCP for full Jira/Confluence bodies when indexes are insufficient",
    ]

    import os

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage
            from config import SWARM_MODEL

            model = ChatAnthropic(model=SWARM_MODEL, temperature=0, max_tokens=800)
            summary = model.invoke(
                [
                    HumanMessage(
                        content=(
                            "Summarize in 8 bullets what implementers must know from this research "
                            f"for: {state['user_input'][:300]}\n\n{snippets[:3000]}\n\n{connected[:2000]}"
                        )
                    )
                ]
            )
            from usage_tracker import record_from_message

            record_from_message("research-synthesis", SWARM_MODEL, summary, run_id=run_id, note="research team")
            body.extend(["", "## LLM synthesis (router-enabled)", str(summary.content)])
        except Exception as exc:  # noqa: BLE001
            body.append(f"\n_LLM synthesis skipped: {exc}_")

    path = _write_artifact(run_id, "RESEARCH.md", "\n".join(body))
    update_agent(
        run_id,
        agent_id,
        {"status": "written", "ended_at": _now(), "summary": f"research → {path}", "note_path": path},
    )
    return {"phase": "research_done", "delivery_path": path, "artifacts": [{"agent": agent_id, "artifact": path}]}


def run_design_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "design", "architecture & UX", "design_team")
    outcomes = []
    for agent in _agents_for_team_ids("design", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "design"})
        kb = _kb_snippet(agent.get("kb_topics", []))
        content = [
            f"# Design output — {agent['name']}",
            f"**Request:** {state['user_input']}",
            "",
            "## Knowledge context",
            kb or "_Run codebase KB refresh for richer context._",
            "",
            "## Deliverables",
            "- Architecture decision record (ADR)",
            "- UX mockup notes / component map for LWC",
            "- Invoke Cursor: `sfdc-cta-mentor` for HTML blueprint when needed",
        ]
        path = _write_artifact(run_id, f"design-{agent['id']}.md", "\n".join(content))
        update_agent(run_id, agent["id"], {"status": "written", "ended_at": _now(), "summary": path})
        outcomes.append({"agent": agent["id"], "artifact": path})
    return {"phase": "design_done", "artifacts": outcomes}


def _run_codebase_topics_for_agent(run_id: str, agent: Dict[str, Any]) -> str:
    keys = agent.get("kb_topics", [])
    scanned = []
    for topic in CODEBASE_TOPICS:
        if any(k.replace("codebase/", "") == topic["key"] or k.endswith(topic["key"]) for k in keys) or not keys:
            if keys and topic["key"] not in [k.split("/")[-1] for k in keys]:
                if not any(topic["key"] in k for k in keys):
                    continue
            try:
                r = build_topic_note(topic)
                scanned.append(f"{topic['key']}: {r.get('files_matched', 0)} files")
            except Exception as exc:  # noqa: BLE001
                scanned.append(f"{topic['key']}: error {exc}")
    return "; ".join(scanned[:8]) or "context loaded from KB"


def run_development_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "development", "implementing", "development_team")
    outcomes = []
    for agent in _agents_for_team_ids("development", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "development"})
        scan_summary = _run_codebase_topics_for_agent(run_id, agent)
        ctx = get_runtime()
        deploy_cmd = ctx.get("deployCommandTemplate", "sf project deploy start")
        work_order = [
            f"# Work order — {agent['name']}",
            f"**Cursor agent:** `{agent.get('cursor_agent')}`",
            f"**Skills:** {', '.join(agent.get('skills', []))}",
            "",
            f"**Project:** {ctx.get('projectName')} · **Org:** `{ctx.get('targetOrgAlias')}`",
            "",
            f"**Task:** {state['user_input']}",
            "",
            "## Codebase scan",
            scan_summary,
            "",
            "## Implementation checklist",
            "- Read matching patterns in package source",
            "- Bulkified Apex, FLS, tests ≥85%",
            f"- Deploy: `{deploy_cmd}`",
            f"- Skill: `~/.cursor/skills/{agent.get('skills', ['advanced-salesforce-developer'])[0]}/SKILL.md`",
        ]
        path = _write_artifact(run_id, f"work-{agent['id']}.md", "\n".join(work_order))
        update_agent(
            run_id,
            agent["id"],
            {"status": "written", "ended_at": _now(), "summary": f"work order · {scan_summary[:80]}", "note_path": path},
        )
        outcomes.append({"agent": agent["id"], "artifact": path})
    return {"phase": "development_done", "artifacts": outcomes}


def run_admin_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "admin", "metadata & promotion", "admin_team")
    outcomes = []
    for agent in _agents_for_team_ids("admin", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "admin"})
        scan = _run_codebase_topics_for_agent(run_id, agent)
        content = [
            f"# Admin work order — {agent['name']}",
            f"**Task:** {state['user_input']}",
            "",
            f"**Scan:** {scan}",
            "",
            "## Steps",
            "- Retrieve delta metadata (`sfdc-metadata-sync` skill)",
            "- FLS / perm sets / layouts",
            "- Promotion plan (`sfdc-promotion-workflow` skill)",
        ]
        path = _write_artifact(run_id, f"admin-{agent['id']}.md", "\n".join(content))
        update_agent(run_id, agent["id"], {"status": "written", "ended_at": _now(), "summary": path})
        outcomes.append({"agent": agent["id"], "artifact": path})
    return {"phase": "admin_done", "artifacts": outcomes}


def run_qa_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "qa", "testing", "qa_team")
    outcomes = []
    checklist = [
        "## Playwright E2E",
        "- Pantheon bundle quote line view",
        "- NextGen quoting cart → save quote",
        "- Regression: existing CPQ flows",
        "",
        "## Apex / backend",
        "- Run affected test classes (`sf apex run test`)",
        "- Data queries for edge cases (0 lines, max bundles, amendment)",
        "- Governor limit sanity on bulk scenarios",
        "",
        "## Skill",
        "- `playwright-e2e-validation` for browser tests",
        "- `advanced-salesforce-developer` for Apex test gaps",
    ]
    for agent in _agents_for_team_ids("qa", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "qa"})
        path = _write_artifact(run_id, f"qa-{agent['id']}.md", "\n".join([
            f"# QA plan — {agent['name']}",
            f"**Task:** {state['user_input']}",
            "",
            *checklist,
        ]))
        update_agent(run_id, agent["id"], {"status": "written", "ended_at": _now(), "summary": "QA checklist ready"})
        outcomes.append({"agent": agent["id"], "artifact": path})
    return {"phase": "qa_done", "artifacts": outcomes}


def run_documentation_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "documentation", "documenting changes", "documentation_team")
    outcomes = []
    run_path = _run_dir(run_id)
    artifacts = list(run_path.glob("*.md"))
    summary_lines = [
        f"# Delivery summary",
        f"**Request:** {state['user_input']}",
        f"**Run:** {run_id}",
        "",
        "## Pipeline",
        " → ".join(state.get("pipeline", [])),
        "",
        "## Artifacts produced",
    ]
    for p in sorted(artifacts):
        summary_lines.append(f"- `{p.name}`")
    summary_lines.extend([
        "",
        "## Deep dive (Cursor)",
        "Run `codebase-explainer` skill to produce HTML in `docs/explainers/`",
        "",
        "## Changes",
        "_Link PR / deploy ID after implementation agents complete in Cursor._",
    ])
    delivery_path = _write_artifact(run_id, "DELIVERY.md", "\n".join(summary_lines))
    # Also copy to docs for user visibility
    docs_dir = REPO_ROOT / "docs" / "swarm-deliveries"
    docs_dir.mkdir(parents=True, exist_ok=True)
    dest = docs_dir / f"{run_id}-delivery.md"
    dest.write_text("\n".join(summary_lines), encoding="utf-8")

    for agent in _agents_for_team_ids("documentation", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "documentation"})
        update_agent(
            run_id,
            agent["id"],
            {"status": "written", "ended_at": _now(), "summary": str(dest), "note_path": str(dest)},
        )
        outcomes.append({"agent": agent["id"], "artifact": str(dest)})
    return {"phase": "documentation_done", "delivery_path": str(dest), "artifacts": outcomes}


def run_training_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "training", "refreshing agent KB", "training_team")
    topics_to_refresh: List[str] = []
    for aid in state.get("assigned_agents", []):
        agent = next((a for a in AGENTS if a["id"] == aid), None)
        if agent:
            topics_to_refresh.extend(agent.get("training_topics", []))
    outcomes = []
    for agent in _agents_for_team_ids("training", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "training"})
        refreshed = []
        try:
            from skill_refresh import run_skill_refresh

            summary = run_skill_refresh("weekly")
            refreshed.append(f"weekly refresh: {summary.get('tier')}")
        except Exception as exc:  # noqa: BLE001
            refreshed.append(f"refresh skip: {exc}")
        summary = f"training topics: {topics_to_refresh}; {', '.join(refreshed)}"
        update_agent(run_id, agent["id"], {"status": "written", "ended_at": _now(), "summary": summary})
        outcomes.append({"agent": agent["id"], "summary": summary})
    return {"phase": "training_done", "artifacts": outcomes}
