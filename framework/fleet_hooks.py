"""Fleet state hooks for LangGraph swarm nodes."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import FLEET_STATE, ensure_dirs
from teams import TEAMS, team_by_id

_lock = threading.Lock()


def _team_lookup(team_id: str) -> Dict[str, Any]:
    """Resolve team metadata from legacy KB teams or agent orchestrator teams."""
    t = team_by_id(team_id)
    if t:
        return t
    try:
        from agents_registry import team_by_id as orch_team_by_id

        return orch_team_by_id(team_id) or {}
    except ImportError:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> Dict[str, Any]:
    if FLEET_STATE.exists():
        try:
            return json.loads(FLEET_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"runs": []}


def _save_state(state: Dict[str, Any]) -> None:
    ensure_dirs()
    with _lock:
        FLEET_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def append_activity(run_id: str, message: str, level: str = "info") -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        activity = run.setdefault("activity", [])
        activity.insert(0, {"ts": _now(), "message": message, "level": level})
        run["activity"] = activity[:100]
        _save_state(state)
        return


def init_pipeline_steps(run_id: str, pipeline: List[str]) -> None:
    steps = [
        {"id": node, "label": node.replace("_team", "").replace("_", " "), "status": "pending"}
        for node in pipeline
    ]
    steps.append({"id": "finalize", "label": "Complete", "status": "pending"})
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") == run_id:
            run["pipeline_steps"] = steps
            _save_state(state)
            return


def update_pipeline_step(run_id: str, step_id: str, status: str) -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        for step in run.get("pipeline_steps", []):
            if step.get("id") == step_id:
                step["status"] = status
                if status == "running":
                    step["started_at"] = _now()
                elif status in ("complete", "skipped", "error"):
                    step["ended_at"] = _now()
        _save_state(state)
        return


def init_run(
    run_id: str,
    team_ids: List[str],
    topics: List[Dict[str, Any]],
    workflow: str = "dev-development-swarm",
    source: str = "langgraph-dev-swarm",
) -> None:
    agents = []
    for topic in topics:
        team = _team_lookup(topic.get("team", ""))
        agents.append(
            {
                "id": topic["key"],
                "label": f"{team.get('id', 'team')}:{topic['key']}",
                "title": topic["title"],
                "phase": team.get("name", "Team"),
                "team_id": topic.get("team"),
                "status": "pending",
            }
        )

    run = {
        "run_id": run_id,
        "source": source,
        "workflow": workflow,
        "orchestrator": "langgraph",
        "started_at": _now(),
        "status": "running",
        "teams": team_ids,
        "agents": agents,
    }
    state = _load_state()
    state.setdefault("runs", []).insert(0, run)
    _save_state(state)
    append_activity(run_id, f"Run started — {len(topics)} agents across {len(team_ids)} teams")


def update_agent(run_id: str, agent_id: str, patch: Dict[str, Any]) -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        for agent in run.get("agents", []):
            if agent.get("id") == agent_id:
                agent.update(patch)
                break
        _save_state(state)
        return


def mark_run_failed(run_id: str, error: str) -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        run["status"] = "error"
        run["ended_at"] = _now()
        run["error"] = error
        run["active_graph_node"] = "error"
        run["active_graph_label"] = "Error"
        activity = run.setdefault("activity", [])
        activity.insert(0, {"ts": _now(), "message": f"Run failed: {error}", "level": "error"})
        run["activity"] = activity[:100]
        _save_state(state)
        return


def finalize_run(run_id: str, results: List[Dict[str, Any]]) -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        agents = run.get("agents", [])
        total = len(agents)
        done = sum(1 for a in agents if a.get("status") not in ("running", "pending"))
        running = sum(1 for a in agents if a.get("status") == "running")
        written = sum(1 for a in agents if a.get("status") == "written")
        skipped = sum(1 for a in agents if a.get("status") == "skipped")
        error = sum(1 for a in agents if a.get("status") == "error")
        pct = int(100 * done / total) if total else 0
        run["progress"] = {
            "total": total,
            "done": done,
            "running": running,
            "written": written,
            "skipped": skipped,
            "error": error,
            "percent": pct,
        }
        run["status"] = "complete"
        run["ended_at"] = _now()
        run["active_graph_node"] = "complete"
        run["active_graph_label"] = "Complete"
        for step in run.get("pipeline_steps", []):
            if step.get("id") == "finalize":
                step["status"] = "complete"
                step["ended_at"] = _now()
        activity = run.setdefault("activity", [])
        activity.insert(
            0,
            {
                "ts": _now(),
                "message": "Run complete — open delivery artifacts in docs/swarm-deliveries or .cursor/swarm/.fleet/runs/",
                "level": "info",
            },
        )
        run["activity"] = activity[:100]
        try:
            from usage_tracker import usage_for_run

            run["usage"] = usage_for_run(run_id)
        except ImportError:
            pass
        _save_state(state)
        return


def mark_team_phase(run_id: str, team_id: str, phase: str, graph_node: Optional[str] = None) -> None:
    team = _team_lookup(team_id)
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        run["current_team"] = team_id
        run["current_phase"] = phase
        if graph_node:
            run["active_graph_node"] = graph_node
        for agent in run.get("agents", []):
            if agent.get("team_id") == team_id and agent.get("status") == "pending":
                agent["phase"] = f"{team.get('name', team_id)} · {phase}"
        _save_state(state)
        return


def set_run_pipeline(run_id: str, pipeline: List[str], router_method: str = "") -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") == run_id:
            run["pipeline"] = pipeline
            run["router_method"] = router_method
            steps = [
                {"id": node, "label": node.replace("_team", "").replace("_", " "), "status": "pending"}
                for node in pipeline
            ]
            steps.append({"id": "finalize", "label": "Complete", "status": "pending"})
            run["pipeline_steps"] = steps
            activity = run.setdefault("activity", [])
            activity.insert(
                0,
                {
                    "ts": _now(),
                    "message": f"Pipeline: {' → '.join(p.replace('_team', '') for p in pipeline)} ({router_method or 'router'})",
                    "level": "info",
                },
            )
            run["activity"] = activity[:100]
            _save_state(state)
            return


def set_active_graph_node(run_id: str, node: str, label: str = "") -> None:
    state = _load_state()
    for run in state.get("runs", []):
        if run.get("run_id") != run_id:
            continue
        run["active_graph_node"] = node
        run["active_graph_label"] = label or node
        _save_state(state)
        return


def is_run_active() -> bool:
    state = _load_state()
    for run in state.get("runs", [])[:3]:
        if run.get("status") == "running":
            return True
    return False
