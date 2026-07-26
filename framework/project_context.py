"""Bridge swarm runtime to shared sfdc_context (global skills or vendored copy)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_FRAMEWORK_DIR = Path(__file__).resolve().parent
_SHARED_CANDIDATES = [
    Path.home() / ".cursor" / "skills" / "_shared",
    _FRAMEWORK_DIR / "vendor" / "_shared",
    _FRAMEWORK_DIR.parent / "templates" / "cursor" / "skills" / "_shared",
]


def _import_sfdc_context():
    last_err: Optional[Exception] = None
    for shared in _SHARED_CANDIDATES:
        if not (shared / "sfdc_context.py").is_file():
            continue
        path = str(shared)
        if path not in sys.path:
            sys.path.insert(0, path)
        try:
            from sfdc_context import resolve_context  # noqa: WPS433

            return resolve_context
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise ImportError(
        "Cannot import sfdc_context. Install skills via scripts/install-skills.sh "
        f"or keep framework/vendor/_shared. Last error: {last_err}"
    )


def find_project_root(start: Optional[Path] = None) -> Path:
    resolve_context = _import_sfdc_context()
    ctx = resolve_context(start=start or Path.cwd())
    return Path(ctx["projectRoot"]).resolve()


def resolve_swarm_context(
    start: Optional[Path] = None,
    target_org_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Full swarm context: SFDC project + org + paths."""
    env_root = __import__("os").environ.get("SFDC_SWARM_PROJECT_ROOT")
    if env_root and not start:
        start = Path(env_root).expanduser()
    start = start or Path.cwd()
    resolve_context = _import_sfdc_context()
    ctx = resolve_context(start=start, target_org_override=target_org_override)
    root = Path(ctx["projectRoot"]).resolve()

    swarm_home = Path(__import__("os").environ.get("SFDC_SWARM_HOME", "")).expanduser()
    if not swarm_home or not swarm_home.is_dir():
        swarm_home = Path.home() / ".cursor" / "sfdc-knowledge-swarm"
    if not swarm_home.is_dir():
        swarm_home = _FRAMEWORK_DIR

    source_path = ctx.get("sourcePath", "force-app/main/default")
    pkg_root = source_path.split("/")[0] if "/" in source_path else "force-app"

    kb_dir = Path(__import__("os").environ.get("KB_DIR", str(root / "knowledge-base"))).expanduser()
    global_kb = swarm_home / "knowledge-base"
    fleet_dir = root / ".cursor" / "swarm" / ".fleet"
    swarm_cursor_dir = root / ".cursor" / "swarm"

    project_topics_path = swarm_cursor_dir / "project-topics.json"
    project_topics: list = []
    if project_topics_path.exists():
        try:
            project_topics = json.loads(project_topics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            project_topics = []

    return {
        **ctx,
        "swarmHome": str(swarm_home),
        "repoRoot": str(root),
        "projectName": _project_name(root),
        "kbDir": str(kb_dir),
        "globalKbDir": str(global_kb),
        "fleetDir": str(fleet_dir),
        "swarmCursorDir": str(swarm_cursor_dir),
        "sourcePackageRoot": pkg_root,
        "sourcePath": source_path,
        "projectTopicsPath": str(project_topics_path),
        "projectTopics": project_topics,
        "deployCommandTemplate": (
            f"sf project deploy start --target-org {ctx.get('targetOrgAlias') or '<target-org>'}"
        ),
        "retrieveCommandTemplate": (
            f"sf project retrieve start --target-org {ctx.get('targetOrgAlias') or '<target-org>'}"
        ),
    }


def _project_name(root: Path) -> str:
    try:
        data = json.loads((root / "sfdx-project.json").read_text(encoding="utf-8"))
        if data.get("name"):
            return str(data["name"])
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return root.name


def adapt_glob_pattern(pattern: str, ctx: Dict[str, Any]) -> str:
    """Rewrite force-app/... globs to the project's actual package root (e.g. Master/)."""
    pkg = ctx.get("sourcePackageRoot") or "force-app"
    if pattern.startswith("force-app/") and pkg != "force-app":
        return pkg + pattern[len("force-app") :]
    return pattern

