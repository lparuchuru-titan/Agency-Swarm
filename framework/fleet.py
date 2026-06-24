"""Fleet monitor — reads Claude Code swarm agents from local workflow logs (no API key)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import CLAUDE_HOME, TOPICS, get_runtime

TOPIC_KEY_RE = re.compile(r"Topic key:\s*([a-z0-9-]+)", re.I)
INDEX_PROMPT_RE = re.compile(r"regenerate.*index|knowledge-base index", re.I)


def _topic_title(key: str) -> str:
    for t in TOPICS:
        if t["key"] == key:
            return t["title"]
    return key


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(ts: Optional[str]) -> Optional[int]:
    dt = _parse_ts(ts)
    if not dt:
        return None
    return int((datetime.now(timezone.utc) - dt).total_seconds())


def parse_agent_prompt(path: Path) -> Dict[str, str]:
    """Infer label/title/phase from the first user message in agent jsonl."""
    out: Dict[str, str] = {"phase": "Research"}
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        evt = json.loads(first)
        content = evt.get("message", {}).get("content", "")
    except (IndexError, json.JSONDecodeError, OSError):
        return out

    if INDEX_PROMPT_RE.search(content):
        out.update({"id": "index", "label": "index", "title": "Index builder", "phase": "Index"})
        return out

    m = TOPIC_KEY_RE.search(content)
    if m:
        key = m.group(1)
        out.update(
            {
                "id": key,
                "label": f"research:{key}",
                "title": _topic_title(key),
                "phase": "Research",
            }
        )
    return out


def parse_agent_activity(path: Path) -> Dict[str, Any]:
    """Live activity from agent jsonl tail — tool calls, last action, timestamps."""
    activity: Dict[str, Any] = {
        "message_count": 0,
        "tool_calls": 0,
        "last_ts": None,
        "last_action": "",
        "file_mtime": None,
    }
    try:
        activity["file_mtime"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return activity

    for line in lines:
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        activity["message_count"] += 1
        ts = evt.get("timestamp")
        if ts:
            activity["last_ts"] = ts

        if evt.get("type") != "assistant":
            continue
        msg = evt.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            activity["last_action"] = content.strip()[:120]
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    activity["tool_calls"] += 1
                    name = block.get("name", "tool")
                    activity["last_action"] = f"→ {name}"
                elif block.get("type") == "text" and block.get("text"):
                    activity["last_action"] = block["text"].strip()[:120]

    return activity


def scan_workflow_dir(wf_dir: Path) -> Optional[Dict[str, Any]]:
    journal = wf_dir / "journal.jsonl"
    if not journal.exists():
        return None

    wf_id = wf_dir.name
    hex_to_meta: Dict[str, Dict[str, str]] = {}
    for agent_path in wf_dir.glob("agent-*.jsonl"):
        hex_id = agent_path.stem.replace("agent-", "")
        meta = parse_agent_prompt(agent_path)
        meta["hex_id"] = hex_id
        meta["activity"] = parse_agent_activity(agent_path)
        hex_to_meta[hex_id] = meta

    agents_by_hex: Dict[str, Dict[str, Any]] = {}
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    journal_mtime = datetime.fromtimestamp(journal.stat().st_mtime, tz=timezone.utc).isoformat()

    for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        evt_ts = evt.get("timestamp") or journal_mtime

        if evt.get("type") == "started":
            hex_id = evt.get("agentId", "")
            if not started_at:
                started_at = evt_ts
            meta = hex_to_meta.get(hex_id, {})
            agents_by_hex[hex_id] = {
                "hex_id": hex_id,
                "id": meta.get("id", hex_id),
                "label": meta.get("label", hex_id),
                "title": meta.get("title", hex_id),
                "phase": meta.get("phase", "Research"),
                "status": "running",
                "started_at": evt_ts,
                "activity": meta.get("activity", {}),
            }

        elif evt.get("type") == "result":
            hex_id = evt.get("agentId", "")
            result = evt.get("result") or {}
            if not isinstance(result, dict):
                result = {"summary": str(result), "status": "written", "key": "index", "title": "Index builder"}
            meta = hex_to_meta.get(hex_id, {})
            key = result.get("key", meta.get("id", hex_id))
            agents_by_hex[hex_id] = {
                "hex_id": hex_id,
                "id": key,
                "label": meta.get("label", f"research:{key}" if key != "index" else "index"),
                "title": result.get("title", meta.get("title", _topic_title(key))),
                "phase": meta.get("phase", "Index" if key == "index" else "Research"),
                "status": result.get("status", "complete"),
                "summary": (result.get("summary") or str(result))[:400],
                "note_path": result.get("note_path"),
                "docs_read": result.get("docs_read"),
                "ended_at": evt_ts,
                "activity": meta.get("activity", {}),
            }
            ended_at = evt_ts

    if not agents_by_hex:
        return None

    agents = list(agents_by_hex.values())
    for agent in agents:
        act = agent.get("activity") or {}
        st = agent.get("status", "")
        last_ts = act.get("last_ts") or agent.get("ended_at") or agent.get("started_at")
        age = _age_seconds(last_ts)
        agent["last_seen_seconds"] = age
        if st == "running" and age is not None and age > 120:
            agent["health"] = "stale"
        elif st == "running":
            agent["health"] = "active"
        elif st in ("written", "complete"):
            agent["health"] = "healthy"
        elif st == "partial":
            agent["health"] = "degraded"
        elif st == "error":
            agent["health"] = "unhealthy"
        else:
            agent["health"] = "unknown"

    running = sum(1 for a in agents if a.get("status") == "running")
    status = "running" if running else "complete"

    session_dir = wf_dir.parent.parent.parent
    project_hint = session_dir.parent.name if session_dir.parent else ""

    return {
        "run_id": wf_id,
        "source": "claude-code",
        "workflow": "sfdc-knowledge-swarm",
        "project": project_hint.replace("-Users-", "").replace("-", "/"),
        "started_at": started_at,
        "ended_at": ended_at if not running else None,
        "journal_mtime": journal_mtime,
        "status": status,
        "agents": agents,
        "progress": _run_progress(agents),
    }


def _run_progress(agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(agents)
    done = sum(1 for a in agents if a.get("status") != "running")
    running = sum(1 for a in agents if a.get("status") == "running")
    written = sum(1 for a in agents if a.get("status") == "written")
    partial = sum(1 for a in agents if a.get("status") == "partial")
    error = sum(1 for a in agents if a.get("status") == "error")
    pct = int(100 * done / total) if total else 0
    return {
        "total": total,
        "done": done,
        "running": running,
        "written": written,
        "partial": partial,
        "error": error,
        "percent": pct,
    }


def scan_claude_workflows() -> List[Dict[str, Any]]:
    projects = CLAUDE_HOME / "projects"
    if not projects.exists():
        return []

    runs: List[Dict[str, Any]] = []
    for journal in projects.glob("**/subagents/workflows/*/journal.jsonl"):
        run = scan_workflow_dir(journal.parent)
        if run:
            runs.append(run)

    runs.sort(key=lambda r: r.get("journal_mtime") or "", reverse=True)
    return runs


def compute_health(agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {
        "running": 0,
        "written": 0,
        "partial": 0,
        "error": 0,
        "complete": 0,
        "pending": 0,
        "other": 0,
    }
    for a in agents:
        st = (a.get("status") or "other").lower()
        if st in counts:
            counts[st] += 1
        else:
            counts["other"] += 1

    total = len(agents) or 1
    score = int(100 * (counts["written"] + 0.5 * counts["partial"] + counts["complete"]) / total)
    if counts["running"]:
        overall = "active"
    elif counts["error"] > counts["written"]:
        overall = "unhealthy"
    elif counts["partial"]:
        overall = "degraded"
    else:
        overall = "healthy"

    return {"overall": overall, "score": score, "counts": counts, "total_agents": len(agents)}


def scan_skill_agents() -> List[Dict[str, Any]]:
    """Registered agents from ~/.cursor/agents and ~/.claude/agents."""
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for agents_dir in (CLAUDE_HOME / "agents", Path.home() / ".cursor" / "agents"):
        if not agents_dir.exists():
            continue
        for path in sorted(agents_dir.glob("*.md")):
            if path.stem in seen:
                continue
            seen.add(path.stem)
            text = path.read_text(encoding="utf-8", errors="replace")
            desc = ""
            for line in text.splitlines():
                if line.lower().startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
            items.append({"name": path.stem, "description": desc[:120], "source": agents_dir.parent.name})
    return items


def load_fleet_state_runs() -> List[Dict[str, Any]]:
    from config import FLEET_STATE

    if not FLEET_STATE.exists():
        return []
    try:
        data = json.loads(FLEET_STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    runs = data.get("runs", [])
    for run in runs:
        agents = run.get("agents", [])
        if "progress" not in run:
            run["progress"] = _run_progress(agents)
        for agent in agents:
            if agent.get("status") == "running":
                agent.setdefault("health", "active")
            elif agent.get("status") in ("written", "complete", "skipped"):
                agent.setdefault("health", "healthy")
            elif agent.get("status") == "error":
                agent.setdefault("health", "unhealthy")
    return runs


def unified_snapshot(active_only: bool = False) -> Dict[str, Any]:
    """Merge Claude Code workflow runs + dev/langchain fleet state + teams/KB."""
    from dev_swarm import kb_catalog, schedule_info, teams_snapshot

    claude_runs = scan_claude_workflows()
    state_runs = load_fleet_state_runs()
    all_runs = claude_runs + [r for r in state_runs if r not in claude_runs]
    all_runs.sort(key=lambda r: r.get("started_at") or r.get("journal_mtime") or "", reverse=True)

    active_run = None
    for run in all_runs:
        if run.get("status") == "running":
            active_run = run
            break
    if not active_run and all_runs:
        active_run = all_runs[0]

    if active_only and active_run:
        display_runs = [active_run]
    else:
        display_runs = all_runs[:15]

    agents: List[Dict[str, Any]] = []
    for run in display_runs:
        for agent in run.get("agents", []):
            agents.append({**agent, "run_id": run.get("run_id"), "source": run.get("source")})

    health = compute_health(active_run.get("agents", []) if active_run else agents)
    teams = teams_snapshot()
    kb = kb_catalog()
    schedule = schedule_info()

    try:
        from usage_tracker import usage_summary

        usage = usage_summary()
    except ImportError:
        usage = {"total_usd": 0, "month_usd": 0, "api_key_configured": False}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "langgraph-unified-dev-swarm",
        "api_key_required": False,
        "health": health,
        "active_run": active_run,
        "runs": display_runs,
        "skill_agents": scan_skill_agents(),
        "teams": teams,
        "kb": kb,
        "schedule": schedule,
        "usage": usage,
        "context": {
            "projectName": get_runtime().get("projectName"),
            "targetOrgAlias": get_runtime().get("targetOrgAlias"),
            "fleetStatePath": str(get_runtime().get("fleetDir", "")) + "/state.json",
        },
    }


def fleet_snapshot(active_only: bool = False) -> Dict[str, Any]:
    return unified_snapshot(active_only=active_only)
