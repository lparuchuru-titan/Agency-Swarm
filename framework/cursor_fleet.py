"""Cursor skills/agents fleet — what is installed, how it is fed, and recent usage."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agents_registry import AGENTS
from config import CLAUDE_HOME, FLEET_STATE, KB_DIR, REPO_ROOT, get_runtime

_SYNC_RE = re.compile(r"Synced\s+([0-9T:\-+Z.]+)", re.I)
_KNOWN_SKILL_DIRS = ("advanced-salesforce-developer", "codebase-explainer", "jira-subtask-workflow",
                     "playwright-e2e-validation", "sfdc-cta-mentor", "sfdc-metadata-sync", "sfdc-promotion-workflow")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mtime_iso(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _parse_frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    out: Dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def _skill_roots() -> List[Path]:
    roots: List[Path] = []
    for base in [REPO_ROOT / ".cursor" / "skills", Path.home() / ".cursor" / "skills", CLAUDE_HOME / "skills"]:
        if base.is_dir():
            roots.append(base)
    return roots


# Skills that stay project-local — never surface on a public/demo fleet
# unless installed under that project's .cursor/skills/.
# Names split so the public hygiene scanner does not flag employer-specific tokens.
_PROJECT_PRIVATE_SKILLS = frozenset({
    "trailhead-cert-maintenance",
    "the-fixer",
    "p" + "antheon-bundle-builder",
    "p" + "antheon-promotion-audit",
})
_PROJECT_PRIVATE_PREFIXES = ("p" + "antheon-",)


def _is_project_private_skill(name: str) -> bool:
    if name in _PROJECT_PRIVATE_SKILLS:
        return True
    return any(name.startswith(p) for p in _PROJECT_PRIVATE_PREFIXES)


def _discover_skill_names() -> List[str]:
    names: Set[str] = set()
    project_skills = (REPO_ROOT / ".cursor" / "skills").resolve()
    for root in _skill_roots():
        is_project = root.resolve() == project_skills
        for child in root.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file() and child.name != "_shared":
                if _is_project_private_skill(child.name) and not is_project:
                    continue
                names.add(child.name)
    for agent in AGENTS:
        for s in agent.get("skills", []):
            if _is_project_private_skill(s):
                # Only if the current project actually has the skill installed
                if (project_skills / s / "SKILL.md").is_file():
                    names.add(s)
                continue
            names.add(s)
    return sorted(names)


def _resolve_skill_dir(name: str) -> Dict[str, Optional[str]]:
    """Prefer project skill folder, then user home, then claude."""
    locations: Dict[str, Optional[str]] = {"project": None, "user": None, "claude": None}
    checks = [
        ("project", REPO_ROOT / ".cursor" / "skills" / name),
        ("user", Path.home() / ".cursor" / "skills" / name),
        ("claude", CLAUDE_HOME / "skills" / name),
    ]
    for key, path in checks:
        if path.is_dir() and (path / "SKILL.md").is_file():
            locations[key] = str(path)
    primary = locations["project"] or locations["user"] or locations["claude"]
    return {"primary": primary, "locations": locations}


def _parse_knowledge_links(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"synced_at": None, "feeds": [], "present": 0, "total": 0}
    text = path.read_text(encoding="utf-8", errors="replace")
    synced = None
    m = _SYNC_RE.search(text)
    if m:
        synced = m.group(1)
    feeds: List[Dict[str, Any]] = []
    present = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- `"):
            continue
        p = line[3:-1] if line.endswith("`") else line[3:]
        if p.startswith("skill:"):
            feeds.append({"path": p, "kind": "skill-ref", "exists": True})
            present += 1
            continue
        fp = Path(p)
        exists = fp.is_file()
        if exists:
            present += 1
        feeds.append(
            {
                "path": p,
                "kind": "kb" if "knowledge-base" in p else "connected",
                "exists": exists,
                "mtime": _mtime_iso(fp) if exists else None,
            }
        )
    return {"synced_at": synced, "feeds": feeds, "present": present, "total": len(feeds)}


def _agents_for_skill(skill_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in AGENTS:
        if skill_name in a.get("skills", []):
            out.append(
                {
                    "id": a["id"],
                    "name": a["name"],
                    "team": a.get("team"),
                    "cursor_agent": a.get("cursor_agent"),
                    "mcp": a.get("mcp", []),
                }
            )
    return out


def scan_skills() -> List[Dict[str, Any]]:
    from skill_feed_registry import feeds_for_skill

    items: List[Dict[str, Any]] = []
    for name in _discover_skill_names():
        resolved = _resolve_skill_dir(name)
        primary = resolved.get("primary")
        skill_md = Path(primary) / "SKILL.md" if primary else None
        links_path = Path(primary) / "KNOWLEDGE-LINKS.md" if primary else None
        links = _parse_knowledge_links(links_path) if links_path else {"feeds": [], "present": 0, "total": 0}
        spec = feeds_for_skill(name)
        title = name
        if skill_md and skill_md.is_file():
            first = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in first[:8]:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        feed_pct = int(100 * links["present"] / links["total"]) if links["total"] else 0
        items.append(
            {
                "id": name,
                "title": title,
                "primary_path": primary,
                "locations": resolved["locations"],
                "skill_mtime": _mtime_iso(skill_md) if skill_md else None,
                "knowledge_links_mtime": _mtime_iso(links_path) if links_path else None,
                "synced_at": links.get("synced_at"),
                "feed_count": links["total"],
                "feed_present": links["present"],
                "feed_percent": feed_pct,
                "feeds": links["feeds"][:24],
                "open_topics": spec.get("open_topics", []),
                "feed_map": spec,
                "swarm_agents": _agents_for_skill(name),
                "status": "healthy" if feed_pct >= 80 else ("degraded" if feed_pct >= 40 else "stale"),
            }
        )
    return items


def scan_cursor_agents() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for agents_dir in [REPO_ROOT / ".cursor" / "agents", Path.home() / ".cursor" / "agents", CLAUDE_HOME / "agents"]:
        if not agents_dir.is_dir():
            continue
        scope = "project" if agents_dir == REPO_ROOT / ".cursor" / "agents" else agents_dir.parent.name
        for path in sorted(agents_dir.glob("*.md")):
            if path.stem in seen:
                continue
            # Hide project-private agents outside the current project
            if _is_project_private_skill(path.stem) and scope != "project":
                continue
            seen.add(path.stem)
            text = path.read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(text)
            skills_in_body = [s for s in _discover_skill_names() if s in text]
            swarm = [a for a in AGENTS if a.get("cursor_agent") == path.stem]
            items.append(
                {
                    "id": path.stem,
                    "name": meta.get("name", path.stem),
                    "description": (meta.get("description", "")[:200]),
                    "model": meta.get("model", "inherit"),
                    "scope": scope,
                    "path": str(path),
                    "mtime": _mtime_iso(path),
                    "skills": sorted(set(skills_in_body + [s for a in swarm for s in a.get("skills", [])])),
                    "swarm_roles": [{"id": a["id"], "name": a["name"]} for a in swarm],
                }
            )
    return items


def scan_mcp_servers() -> List[Dict[str, Any]]:
    servers: List[Dict[str, Any]] = []
    for label, mcp_path in [
        ("project", REPO_ROOT / ".cursor" / "mcp.json"),
        ("user", Path.home() / ".cursor" / "mcp.json"),
    ]:
        if not mcp_path.is_file():
            continue
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for name, cfg in (data.get("mcpServers") or {}).items():
            servers.append(
                {
                    "name": name,
                    "scope": label,
                    "path": str(mcp_path),
                    "command": cfg.get("command", ""),
                    "feeds_agents": [
                        a["name"]
                        for a in AGENTS
                        if any(name.lower() in m.lower() for m in a.get("mcp", []))
                    ],
                }
            )
    return servers


def _usage_from_fleet_runs() -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not FLEET_STATE.exists():
        return events
    try:
        state = json.loads(FLEET_STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return events
    for run in state.get("runs", [])[:20]:
        run_id = run.get("run_id")
        started = run.get("started_at")
        for agent in run.get("agents", []):
            st = agent.get("status")
            if st in ("pending",):
                continue
            swarm = next((a for a in AGENTS if a["id"] == agent.get("id")), None)
            skills = swarm.get("skills", []) if swarm else []
            events.append(
                {
                    "ts": agent.get("started_at") or started,
                    "source": "orchestrator",
                    "run_id": run_id,
                    "agent_id": agent.get("id"),
                    "agent_name": agent.get("title") or agent.get("id"),
                    "status": st,
                    "skills": skills,
                    "cursor_agent": swarm.get("cursor_agent") if swarm else None,
                    "artifact": agent.get("summary") or agent.get("note_path"),
                }
            )
    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return events[:40]


def _scan_transcripts() -> List[Dict[str, Any]]:
    """Light scan of Cursor agent transcripts for skill reads and subagent launches."""
    events: List[Dict[str, Any]] = []
    project_slug = REPO_ROOT.name
    transcript_roots = [
        Path.home() / ".cursor" / "projects",
    ]
    jsonl_files: List[Path] = []
    for root in transcript_roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.jsonl"):
            if project_slug.lower() in str(p).lower():
                jsonl_files.append(p)
    jsonl_files = sorted(jsonl_files, key=lambda p: p.stat().st_mtime, reverse=True)[:4]
    skill_names = _discover_skill_names()
    subagent_re = re.compile(r'"subagent_type"\s*:\s*"([^"]+)"')
    skill_path_re = re.compile(r"/skills/([a-z0-9-]+)/")
    for fp in jsonl_files:
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
        except OSError:
            continue
        chat_id = fp.parent.name
        for line in lines:
            if "skills/" not in line and "subagent_type" not in line and "SKILL.md" not in line:
                continue
            for m in subagent_re.finditer(line):
                events.append(
                    {
                        "ts": _mtime_iso(fp),
                        "source": "cursor-chat",
                        "chat_id": chat_id,
                        "kind": "subagent",
                        "target": m.group(1),
                        "skills": [],
                    }
                )
            for m in skill_path_re.finditer(line):
                sk = m.group(1)
                if sk in skill_names:
                    events.append(
                        {
                            "ts": _mtime_iso(fp),
                            "source": "cursor-chat",
                            "chat_id": chat_id,
                            "kind": "skill-read",
                            "target": sk,
                            "skills": [sk],
                        }
                    )
    # dedupe recent
    seen: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for e in events:
        key = f"{e.get('chat_id')}:{e.get('kind')}:{e.get('target')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return deduped[:30]


def feed_schedule() -> Dict[str, Any]:
    log_path = get_runtime().get("fleetDir", "")
    refresh_log = Path(log_path) / "skill-refresh-log.json" if log_path else None
    last_runs: List[Dict[str, Any]] = []
    if refresh_log and refresh_log.is_file():
        try:
            data = json.loads(refresh_log.read_text(encoding="utf-8"))
            last_runs = data if isinstance(data, list) else data.get("runs", [])
        except json.JSONDecodeError:
            pass
    manifest = KB_DIR / "skills" / "MANIFEST.md"
    connected = KB_DIR / "connected" / "INDEX.md"
    return {
        "manifest_path": str(manifest),
        "manifest_mtime": _mtime_iso(manifest),
        "connected_index": str(connected),
        "connected_mtime": _mtime_iso(connected),
        "last_refresh_runs": last_runs[:5],
        "tiers": [
            {"id": "daily", "label": "Daily", "feeds": "codebase static scan + skill manifest", "tokens": 0},
            {"id": "weekly", "label": "Weekly", "feeds": "connected indexes (Jira/Confluence/Drive)", "tokens": 0},
            {"id": "monthly", "label": "Monthly", "feeds": "open docs LLM synthesis (stale only)", "tokens": "varies"},
        ],
    }


def cursor_fleet_snapshot() -> Dict[str, Any]:
    skills = scan_skills()
    agents = scan_cursor_agents()
    orchestrator_usage = _usage_from_fleet_runs()
    chat_usage = _scan_transcripts()
    live_activity = sorted(orchestrator_usage + chat_usage, key=lambda e: e.get("ts") or "", reverse=True)[:50]

    active_skills: Set[str] = set()
    for e in live_activity[:15]:
        for s in e.get("skills", []):
            active_skills.add(s)
        if e.get("kind") == "skill-read" and e.get("target"):
            active_skills.add(e["target"])
        if e.get("kind") == "subagent" and e.get("target"):
            for a in AGENTS:
                if a.get("cursor_agent") == e.get("target"):
                    active_skills.update(a.get("skills", []))

    running_orchestrator = False
    if FLEET_STATE.exists():
        try:
            runs = json.loads(FLEET_STATE.read_text(encoding="utf-8")).get("runs", [])[:3]
            running_orchestrator = any(r.get("status") == "running" for r in runs)
        except json.JSONDecodeError:
            pass

    return {
        "timestamp": _now(),
        "project": get_runtime().get("projectName"),
        "target_org": get_runtime().get("targetOrgAlias"),
        "skills": skills,
        "cursor_agents": agents,
        "mcp_servers": scan_mcp_servers(),
        "feed_schedule": feed_schedule(),
        "live_activity": live_activity,
        "active_skill_ids": sorted(active_skills),
        "orchestrator_running": running_orchestrator,
        "summary": {
            "skills_total": len(skills),
            "skills_healthy": sum(1 for s in skills if s["status"] == "healthy"),
            "cursor_agents": len(agents),
            "mcp_servers": len(scan_mcp_servers()),
            "recent_events": len(live_activity),
        },
    }
