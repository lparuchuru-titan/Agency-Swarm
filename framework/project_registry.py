"""Register Salesforce DX projects for multi-project scheduled skill refresh."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REGISTRY_PATH = Path.home() / ".cursor" / "sfdc-knowledge-swarm" / "projects.registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"projects": []}


def _save(data: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_project(ctx: Dict[str, Any]) -> None:
    """Upsert current project in global registry (used by launchd all-projects runner)."""
    root = ctx.get("repoRoot") or ctx.get("projectRoot")
    if not root:
        return
    root = str(Path(root).resolve())
    data = _load()
    projects: List[Dict[str, Any]] = data.get("projects", [])
    entry = {
        "projectRoot": root,
        "projectName": ctx.get("projectName", Path(root).name),
        "targetOrgAlias": ctx.get("targetOrgAlias"),
        "lastSeen": _now(),
    }
    projects = [p for p in projects if p.get("projectRoot") != root]
    projects.insert(0, entry)
    data["projects"] = projects[:50]
    data["updated"] = _now()
    _save(data)


def list_projects() -> List[Dict[str, Any]]:
    return _load().get("projects", [])


def discover_sfdc_projects(search_roots: List[Path] | None = None) -> List[Path]:
    """Shallow discovery of sfdx-project.json under common SFDC folders."""
    roots = search_roots or [
        Path.home() / "SFDC",
        Path.home() / "Projects",
        Path.home() / "Documents",
    ]
    found: List[Path] = []
    seen: set[str] = set()
    for base in roots:
        if not base.is_dir():
            continue
        try:
            for sfdx in base.rglob("sfdx-project.json"):
                root = sfdx.parent.resolve()
                key = str(root)
                if key in seen:
                    continue
                seen.add(key)
                found.append(root)
                if len(found) >= 30:
                    return found
        except OSError:
            continue
    return found
