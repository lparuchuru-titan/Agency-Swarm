"""
LangGraph supervisor orchestrator for the full dev agent swarm.

Pattern: LLM/rule router → research subgraph → sequential team pipeline → finalize.
"""
from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, Any, Dict, List, Literal, TypedDict

from agent_nodes import (
    run_admin_team,
    run_design_team,
    run_development_team,
    run_documentation_team,
    run_qa_team,
    run_requirements_team,
    run_research_team,
    run_review_team,
    run_training_team,
)
from agents_registry import AGENTS, agents_for_team, GRAPH_NODES
from config import FLEET_DIR, ORCHESTRATOR_STEP_DELAY_MS
from fleet_hooks import (
    append_activity,
    finalize_run,
    init_run,
    set_active_graph_node,
    set_run_pipeline,
    update_pipeline_step,
)
from llm_router import build_plan, route_user_input


class OrchestratorState(TypedDict):
    run_id: str
    user_input: str
    intent: str
    pipeline: List[str]
    pipeline_index: int
    assigned_agents: List[str]
    phase: str
    plan_markdown: str
    delivery_path: str
    router_method: str
    results: Annotated[List[Dict[str, Any]], add]


NODE_MAP = {
    "requirements_team": run_requirements_team,
    "research_team": run_research_team,
    "design_team": run_design_team,
    "development_team": run_development_team,
    "admin_team": run_admin_team,
    "review_team": run_review_team,
    "qa_team": run_qa_team,
    "documentation_team": run_documentation_team,
    "training_team": run_training_team,
}

_TEAM_IDS = frozenset(
    {"requirements", "research", "design", "development", "admin", "review", "qa", "documentation", "training"}
)


def _agents_for_pipeline(pipeline: List[str], assigned: List[str]) -> List[Dict[str, Any]]:
    """Register only agents that will actually execute for this pipeline."""
    pipeline_team_ids = [node.replace("_team", "") for node in pipeline]
    assigned_set = set(assigned)
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for tid in pipeline_team_ids:
        team_agents = agents_for_team(tid)
        if assigned_set:
            picked = [a for a in team_agents if a["id"] in assigned_set]
            if not picked:
                picked = [a for a in AGENTS if a["id"] in assigned_set and a.get("team") == tid]
        else:
            picked = team_agents[:1]
        if not picked and team_agents:
            picked = team_agents[:1]
        for a in picked:
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            records.append(
                {
                    "key": a["id"],
                    "title": a["name"],
                    "team": a.get("team"),
                    "focus": a.get("description", ""),
                }
            )
    return records


def plan_node(state: OrchestratorState) -> Dict[str, Any]:
    intent, pipeline, agent_ids, router_line, router_method = route_user_input(state["user_input"], state["run_id"])
    plan = build_plan(state["user_input"], intent, pipeline, agent_ids, router_line)

    agent_records = _agents_for_pipeline(pipeline, agent_ids)

    topics_for_fleet = [{"key": r["key"], "title": r["title"], "team": r.get("team")} for r in agent_records]
    team_ids = []
    for node in pipeline:
        tid = node.replace("_team", "")
        if tid in _TEAM_IDS:
            team_ids.append(tid)

    init_run(
        state["run_id"],
        team_ids or ["development"],
        topics_for_fleet,
        workflow="agent-orchestrator",
        source="langgraph-orchestrator",
    )
    set_run_pipeline(state["run_id"], pipeline, router_method)
    set_active_graph_node(state["run_id"], "plan", "Router / Plan")

    plan_path = FLEET_DIR / "runs" / state["run_id"] / "PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan, encoding="utf-8")

    return {
        "intent": intent,
        "pipeline": pipeline,
        "pipeline_index": 0,
        "assigned_agents": agent_ids,
        "plan_markdown": plan,
        "router_method": router_method,
        "phase": "planned",
    }


def dispatch_node(state: OrchestratorState) -> Dict[str, Any]:
    import time

    idx = state.get("pipeline_index", 0)
    pipeline = state.get("pipeline", [])
    if idx >= len(pipeline):
        return {"phase": "dispatch_complete", "pipeline_index": idx}

    node_name = pipeline[idx]
    set_active_graph_node(state["run_id"], node_name, node_name.replace("_", " "))
    update_pipeline_step(state["run_id"], node_name, "running")
    append_activity(state["run_id"], f"▶ {node_name.replace('_', ' ')}")

    runner = NODE_MAP.get(node_name)
    if not runner:
        update_pipeline_step(state["run_id"], node_name, "skipped")
        append_activity(state["run_id"], f"Skipped unknown node {node_name}", level="warn")
        return {"pipeline_index": idx + 1, "phase": f"skip_{node_name}"}

    if ORCHESTRATOR_STEP_DELAY_MS > 0:
        time.sleep(ORCHESTRATOR_STEP_DELAY_MS / 1000.0)

    outcome = runner(state)
    update_pipeline_step(state["run_id"], node_name, "complete")
    append_activity(state["run_id"], f"✓ {node_name.replace('_', ' ')} — {outcome.get('phase', 'done')}")

    if ORCHESTRATOR_STEP_DELAY_MS > 0:
        time.sleep(ORCHESTRATOR_STEP_DELAY_MS / 1000.0)

    return {
        "pipeline_index": idx + 1,
        "phase": outcome.get("phase", node_name),
        "delivery_path": outcome.get("delivery_path", state.get("delivery_path", "")),
        "results": [outcome],
    }


def route_after_dispatch(state: OrchestratorState) -> Literal["dispatch", "finalize"]:
    if state.get("pipeline_index", 0) < len(state.get("pipeline", [])):
        return "dispatch"
    return "finalize"


def finalize_node(state: OrchestratorState) -> Dict[str, Any]:
    set_active_graph_node(state["run_id"], "finalize", "Complete")
    results_flat = state.get("results", [])
    finalize_run(state["run_id"], results_flat)

    final = {
        "run_id": state["run_id"],
        "intent": state.get("intent"),
        "delivery_path": state.get("delivery_path"),
        "plan": state.get("plan_markdown", "")[:2000],
        "pipeline": state.get("pipeline"),
        "router_method": state.get("router_method"),
    }
    return {"phase": "complete", "results": [final]}


def build_orchestrator_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(OrchestratorState)
    graph.add_node("plan", plan_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "dispatch")
    graph.add_conditional_edges("dispatch", route_after_dispatch, {"dispatch": "dispatch", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    return graph.compile()


def run_orchestrator(user_input: str) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    app = build_orchestrator_graph()
    final = app.invoke(
        {
            "run_id": run_id,
            "user_input": user_input,
            "intent": "",
            "pipeline": [],
            "pipeline_index": 0,
            "assigned_agents": [],
            "phase": "start",
            "plan_markdown": "",
            "delivery_path": "",
            "router_method": "",
            "results": [],
        }
    )
    return {
        "run_id": run_id,
        "orchestrator": "langgraph-supervisor",
        "intent": final.get("intent"),
        "phase": final.get("phase"),
        "delivery_path": final.get("delivery_path"),
        "plan_markdown": final.get("plan_markdown"),
        "pipeline": final.get("pipeline"),
        "router_method": final.get("router_method"),
        "graph_nodes": GRAPH_NODES,
    }


def graph_structure() -> Dict[str, Any]:
    from dev_swarm import graph_structure as dev_graph
    from graph_viz import graph_diagram

    base = dev_graph()
    diagram = graph_diagram()
    base["orchestrator"] = {
        "pattern": "LLM/rule router + research subgraph + team pipeline",
        "nodes": ["plan (router)", "dispatch (loop)", "finalize"],
        "teams": GRAPH_NODES,
        "agents_count": len(AGENTS),
        "mermaid": diagram["mermaid"],
    }
    return base
