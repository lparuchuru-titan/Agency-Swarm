"""LangGraph orchestration for the Dev Development Swarm (3 teams → codebase KB)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from operator import add
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from codebase_indexer import build_topic_note
from config import CODEBASE_NOTES_DIR, REFRESH_AFTER_DAYS
from fleet_hooks import finalize_run, init_run, mark_team_phase, update_agent
from teams import CODEBASE_TOPICS, TEAMS, team_by_id, topics_for_team


def _now() -> str:
    from datetime import timezone

    return datetime.now(timezone.utc).isoformat()


def _topic_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return age > timedelta(days=REFRESH_AFTER_DAYS)


def process_codebase_topic(
    run_id: str,
    topic: Dict[str, Any],
    force: bool,
    deep: bool,
) -> Dict[str, Any]:
    """Scan force-app + optional LangGraph ReAct deep synthesis."""
    agent_id = topic["key"]
    team = team_by_id(topic.get("team", "")) or {}

    update_agent(
        run_id,
        agent_id,
        {
            "status": "running",
            "started_at": _now(),
            "phase": team.get("name", "Team"),
            "team_id": topic.get("team"),
        },
    )

    note_path = CODEBASE_NOTES_DIR / f"{topic['key']}.md"
    if note_path.exists() and not force and not _topic_stale(note_path):
        outcome = {
            "key": topic["key"],
            "title": topic["title"],
            "team": topic.get("team"),
            "status": "skipped",
            "summary": "note fresh",
            "note_path": str(note_path),
        }
        update_agent(run_id, agent_id, {"status": "skipped", "ended_at": _now(), **outcome})
        return outcome

    try:
        outcome = build_topic_note(topic)
        if deep and os.environ.get("ANTHROPIC_API_KEY"):
            outcome = _deep_synthesize(topic, outcome)
        update_agent(
            run_id,
            agent_id,
            {
                "status": outcome.get("status", "written"),
                "ended_at": _now(),
                "summary": outcome.get("summary", ""),
                "note_path": outcome.get("note_path"),
                "team_id": topic.get("team"),
                "files_matched": outcome.get("files_matched"),
            },
        )
        return outcome
    except Exception as exc:  # noqa: BLE001
        summary = f"{type(exc).__name__}: {exc}"
        update_agent(
            run_id,
            agent_id,
            {"status": "error", "ended_at": _now(), "summary": summary, "team_id": topic.get("team")},
        )
        return {
            "key": topic["key"],
            "title": topic["title"],
            "status": "error",
            "summary": summary,
        }


def _deep_synthesize(topic: Dict[str, Any], scan_outcome: Dict[str, Any]) -> Dict[str, Any]:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage
    from langgraph.prebuilt import create_react_agent

    from config import SWARM_MODEL
    from tools import read_knowledge_note, write_knowledge_note

    note_path = CODEBASE_NOTES_DIR / f"{topic['key']}.md"
    scan_text = note_path.read_text(encoding="utf-8") if note_path.exists() else ""

    model = ChatAnthropic(model=os.environ.get("SWARM_MODEL", SWARM_MODEL), temperature=0, max_tokens=4096)
    agent = create_react_agent(model, [read_knowledge_note, write_knowledge_note])
    prompt = (
        "You are a Salesforce architect on the dev swarm team. Improve this codebase KB note "
        "using ONLY the static scan. Add architecture insights, cross-references, gotchas. "
        f"Write via write_knowledge_note topic_key={topic['key']}.\n\nSTATIC SCAN:\n{scan_text[:14000]}"
    )
    agent.invoke({"messages": [HumanMessage(content=prompt)]})
    scan_outcome["summary"] = (scan_outcome.get("summary", "") + "; langgraph deep synthesis").strip()
    return scan_outcome


class DevSwarmState(TypedDict):
    """LangGraph state for the 3-team dev swarm."""

    run_id: str
    force: bool
    deep: bool
    teams_plan: List[str]
    topics: List[Dict[str, Any]]
    phase: str
    results: Annotated[List[Dict[str, Any]], add]


def _topics_for_team(state: DevSwarmState, team_id: str) -> List[Dict[str, Any]]:
    keys = {t["key"] for t in state["topics"]}
    return [t for t in topics_for_team(team_id) if t["key"] in keys]


def _run_team_node(state: DevSwarmState, team_id: str, graph_node: str) -> Dict[str, Any]:
    if team_id not in state["teams_plan"]:
        return {"phase": f"skip:{team_id}", "results": []}

    team = team_by_id(team_id) or {}
    mark_team_phase(state["run_id"], team_id, "swarm active", graph_node=graph_node)
    topics = _topics_for_team(state, team_id)
    outcomes: List[Dict[str, Any]] = []

    max_workers = min(int(os.environ.get("SWARM_MAX_PARALLEL", "4")), len(topics) or 1)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                process_codebase_topic,
                state["run_id"],
                topic,
                state["force"],
                state["deep"],
            ): topic
            for topic in topics
        }
        for fut in as_completed(futures):
            outcomes.append(fut.result())

    return {"phase": f"complete:{team_id}", "results": outcomes}


def plan_node(state: DevSwarmState) -> Dict[str, Any]:
    from fleet_hooks import set_active_graph_node

    set_active_graph_node(state["run_id"], "plan", "Planning swarm")
    init_run(state["run_id"], state["teams_plan"], state["topics"])
    return {"phase": "planned", "results": []}


def ui_ux_team_node(state: DevSwarmState) -> Dict[str, Any]:
    return _run_team_node(state, "ui-ux", "ui_ux_team")


def salesforce_dev_team_node(state: DevSwarmState) -> Dict[str, Any]:
    return _run_team_node(state, "salesforce-dev", "salesforce_dev_team")


def salesforce_admin_team_node(state: DevSwarmState) -> Dict[str, Any]:
    return _run_team_node(state, "salesforce-admin", "salesforce_admin_team")


def index_node(state: DevSwarmState) -> Dict[str, Any]:
    from dev_swarm import regenerate_dev_index, record_schedule_run
    from fleet_hooks import set_active_graph_node

    set_active_graph_node(state["run_id"], "index", "Building index")
    finalize_run(state["run_id"], state["results"])
    record_schedule_run(state["run_id"], "complete", len(state["results"]))
    return {"phase": "indexed"}


def build_dev_swarm_graph():
    """Compile the LangGraph: plan → 3 teams (sequential) → index."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(DevSwarmState)
    graph.add_node("plan", plan_node)
    graph.add_node("ui_ux_team", ui_ux_team_node)
    graph.add_node("salesforce_dev_team", salesforce_dev_team_node)
    graph.add_node("salesforce_admin_team", salesforce_admin_team_node)
    graph.add_node("index", index_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "ui_ux_team")
    graph.add_edge("ui_ux_team", "salesforce_dev_team")
    graph.add_edge("salesforce_dev_team", "salesforce_admin_team")
    graph.add_edge("salesforce_admin_team", "index")
    graph.add_edge("index", END)

    return graph.compile()


def run_langgraph_dev_swarm(
    team_ids: Optional[List[str]] = None,
    topic_keys: Optional[List[str]] = None,
    force: bool = False,
    deep: bool = False,
) -> Dict[str, Any]:
    """Invoke the compiled LangGraph dev swarm."""
    selected_teams = TEAMS
    if team_ids:
        selected_teams = [t for t in TEAMS if t["id"] in team_ids]

    topics: List[Dict[str, Any]] = []
    for team in selected_teams:
        topics.extend(topics_for_team(team["id"]))
    if topic_keys:
        topics = [t for t in CODEBASE_TOPICS if t["key"] in topic_keys]

    run_id = uuid.uuid4().hex[:12]
    teams_plan = [t["id"] for t in selected_teams]

    app = build_dev_swarm_graph()
    final = app.invoke(
        {
            "run_id": run_id,
            "force": force,
            "deep": deep,
            "teams_plan": teams_plan,
            "topics": topics,
            "phase": "start",
            "results": [],
        }
    )

    return {
        "run_id": run_id,
        "orchestrator": "langgraph",
        "teams": teams_plan,
        "phase": final.get("phase"),
        "results": final.get("results", []),
    }
