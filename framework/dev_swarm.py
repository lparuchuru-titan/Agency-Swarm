"""Dev swarm catalog, schedule, and LangGraph entrypoint."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from codebase_indexer import kb_topic_status
from config import (
    CODEBASE_NOTES_DIR,
    FLEET_STATE,
    KB_DIR,
    PROJECT_NOTES_DIR,
    SCHEDULE_STATE,
    SFDC_NOTES_DIR,
    SWARM_CRON,
    ensure_dirs,
    get_runtime,
    project_topics,
)
from teams import CODEBASE_TOPICS, TEAMS

_lock = threading.Lock()


def _load_json(path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save_json(path, data: Dict[str, Any]) -> None:
    ensure_dirs()
    with _lock:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def start_dev_swarm(
    team_ids: Optional[List[str]] = None,
    topic_keys: Optional[List[str]] = None,
    force: bool = False,
    deep: bool = False,
) -> Dict[str, Any]:
    """Run dev swarm via LangGraph (static scan; --deep uses ReAct agents if API key set)."""
    ensure_dirs()
    try:
        from langgraph_dev_swarm import run_langgraph_dev_swarm

        return run_langgraph_dev_swarm(
            team_ids=team_ids,
            topic_keys=topic_keys,
            force=force,
            deep=deep,
        )
    except ImportError as exc:
        raise RuntimeError("LangGraph not installed. Run: pip install -r requirements.txt") from exc


def regenerate_dev_index(results: List[Dict[str, Any]]) -> None:
    lines = [
        "# Codebase Knowledge Base — Index",
        "",
        "_Built by Dev Development Swarm (LangGraph)_",
        "",
        "| Team | Topic | Note | Status |",
        "| --- | --- | --- | --- |",
    ]
    status_map = {r["key"]: r.get("status", "present") for r in results}
    for topic in CODEBASE_TOPICS:
        team = topic.get("team", "")
        note = f"codebase/{topic['key']}.md"
        status = status_map.get(topic["key"], "present")
        if (CODEBASE_NOTES_DIR / f"{topic['key']}.md").exists() and status == "present":
            status = "written"
        lines.append(f"| {team} | {topic['title']} | [{topic['key']}]({note}) | {status} |")

    (CODEBASE_NOTES_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_schedule_run(run_id: str, status: str, topics: int) -> None:
    from datetime import timezone

    sched = _load_json(SCHEDULE_STATE)
    sched["last_run"] = datetime.now(timezone.utc).isoformat()
    sched["last_run_id"] = run_id
    sched["last_status"] = status
    sched["last_topics"] = topics
    sched["cron"] = SWARM_CRON
    sched["orchestrator"] = "langgraph"
    _save_json(SCHEDULE_STATE, sched)


def kb_catalog() -> Dict[str, Any]:
    """Full knowledge-base catalog for dashboard."""

    def _cat_status(dir_path, keys: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        rows = []
        for item in keys:
            key = item["key"]
            path = dir_path / f"{key}.md"
            st = "missing"
            mtime, size = None, 0
            if path.exists():
                st = "written"
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
                size = path.stat().st_size
            rows.append(
                {
                    "key": key,
                    "title": item.get("title", key),
                    "team": item.get("team"),
                    "category": category,
                    "status": st,
                    "mtime": mtime,
                    "bytes": size,
                    "note_path": str(path),
                }
            )
        return rows

    from config import TOPICS

    sfdc_keys = [{"key": t["key"], "title": t["title"], "team": "salesforce-dev"} for t in TOPICS]
    codebase = kb_topic_status()
    project_notes = _cat_status(PROJECT_NOTES_DIR, project_topics(), "project")
    sfdc = _cat_status(SFDC_NOTES_DIR, sfdc_keys, "sfdc")

    all_rows = codebase + project_notes + sfdc
    written = sum(1 for r in all_rows if r["status"] == "written")
    return {
        "total": len(all_rows),
        "written": written,
        "missing": len(all_rows) - written,
        "percent": int(100 * written / len(all_rows)) if all_rows else 0,
        "categories": {
            "codebase": _summary(codebase),
            "project": _summary(project_notes),
            "sfdc": _summary(sfdc),
        },
        "topics": all_rows,
    }


def _summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    w = sum(1 for r in rows if r["status"] == "written")
    return {"total": len(rows), "written": w, "percent": int(100 * w / len(rows)) if rows else 0}


def teams_snapshot() -> List[Dict[str, Any]]:
    catalog = kb_catalog()
    topic_rows = catalog["topics"]
    out = []
    for team in TEAMS:
        all_team = [t for t in topic_rows if t.get("team") == team["id"]]
        written = sum(1 for t in all_team if t["status"] == "written")
        total = len(all_team) or 1
        out.append(
            {
                **team,
                "kb_written": written,
                "kb_total": len(all_team),
                "kb_percent": int(100 * written / total),
                "topics": all_team,
            }
        )
    return out


def schedule_info() -> Dict[str, Any]:
    sched = _load_json(SCHEDULE_STATE)
    sched.setdefault("cron", SWARM_CRON)
    sched.setdefault("orchestrator", "langgraph")
    import os

    sched["api_key_configured"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    try:
        from skill_refresh import schedule_info as skill_schedule_info

        sched["skill_refresh"] = skill_schedule_info()
    except ImportError:
        pass
    return sched


def graph_structure() -> Dict[str, Any]:
    """LangGraph topology for dashboard."""
    return {
        "orchestrator": "langgraph",
        "dev_swarm": {
            "nodes": ["plan", "ui_ux_team", "salesforce_dev_team", "salesforce_admin_team", "index"],
            "edges": [
                ["START", "plan"],
                ["plan", "ui_ux_team"],
                ["ui_ux_team", "salesforce_dev_team"],
                ["salesforce_dev_team", "salesforce_admin_team"],
                ["salesforce_admin_team", "index"],
                ["index", "END"],
            ],
            "teams": {
                "ui-ux": "ui_ux_team",
                "salesforce-dev": "salesforce_dev_team",
                "salesforce-admin": "salesforce_admin_team",
            },
        },
        "doc_swarm": {
            "nodes": ["plan", "research", "index"],
            "edges": [
                ["START", "plan"],
                ["plan", "research"],
                ["research", "research|index"],
                ["index", "END"],
            ],
        },
    }
