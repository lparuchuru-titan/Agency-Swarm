"""Bridge swarm runtime to ~/.cursor/skills/_shared/sfdc_context.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_SHARED = Path.home() / ".cursor" / "skills" / "_shared"


def _import_sfdc_context():
    if str(_SHARED) not in sys.path:
        sys.path.insert(0, str(_SHARED))
    from sfdc_context import resolve_context  # noqa: WPS433

    return resolve_context


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
        swarm_home = Path(__file__).resolve().parent

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


def adapt_glob_pattern(pattern: str, ctx: Dict[str, Any]) -> str:
    """Rewrite force-app/* globs for Master/ or other package roots."""
    pkg = ctx.get("sourcePackageRoot", "force-app")
    if pattern.startswith("force-app/"):
        return pattern.replace("force-app/", f"{pkg}/", 1)
    return pattern


def _project_name(root: Path) -> str:
    try:
        data = json.loads((root / "sfdx-project.json").read_text(encoding="utf-8"))
        return data.get("name") or root.name
    except (OSError, json.JSONDecodeError):
        return root.name


if __name__ == "__main__":
    print(json.dumps(resolve_swarm_context(), indent=2))
