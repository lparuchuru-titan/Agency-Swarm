#!/usr/bin/env python3
"""
Shared Salesforce project context for all global Cursor/Claude skills.

Resolves from the current working directory (walk up to sfdx-project.json):
- project root
- default package source path (force-app/... or Master/...)
- target org alias (project sf config > optional .cursor config)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def find_sfdx_project_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    for directory in [start, *start.parents]:
        if (directory / "sfdx-project.json").exists():
            return directory.resolve()
    raise FileNotFoundError(
        "No sfdx-project.json found. Open or cd into a Salesforce DX project folder."
    )


def read_sfdx_project(root: Path) -> dict:
    return json.loads((root / "sfdx-project.json").read_text(encoding="utf-8"))


def default_source_path(root: Path) -> str:
    data = read_sfdx_project(root)
    dirs = data.get("packageDirectories", [])
    if not dirs:
        if (root / "force-app/main/default").exists():
            return "force-app/main/default"
        if (root / "Master/main/default").exists():
            return "Master/main/default"
        return "force-app/main/default"
    default = next((d for d in dirs if d.get("default")), dirs[0])
    pkg_path = default.get("path", "force-app")
    if pkg_path == "force-app":
        return "force-app/main/default"
    if pkg_path == "Master":
        return "Master/main/default"
    candidate = root / pkg_path / "main" / "default"
    if candidate.exists():
        return f"{pkg_path}/main/default"
    return pkg_path


def _read_json_if_exists(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_dot_cursor_configs(root: Path) -> dict:
    merged: dict[str, Any] = {}
    for rel in (
        ".cursor/sfdc-project/config.json",
        ".cursor/sfdc-promotion/config.json",
        ".cursor/jira-subtasks/config.json",
        ".cursor/playwright-e2e/config.json",
    ):
        data = _read_json_if_exists(root / rel)
        for k, v in data.items():
            if not str(k).startswith("_") and v is not None and v != "":
                merged[k] = v
    return merged


def read_project_target_org(root: Path) -> tuple[str | None, str]:
    """Read project-local default org from .sf/config.json (set when you open/configure the project)."""
    sf_config = root / ".sf" / "config.json"
    data = _read_json_if_exists(sf_config)
    alias = data.get("target-org") or data.get("targetOrg")
    if alias:
        return str(alias).strip(), "project.sf.config"
    return None, ""


def sf_target_org_alias(project_root: Path) -> tuple[str | None, str]:
    """Fallback: sf config get with cwd=project (returns Local config when set)."""
    try:
        result = subprocess.run(
            ["sf", "config", "get", "target-org", "--json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            entries = data.get("result", [])
            if entries and entries[0].get("value"):
                location = entries[0].get("location", "sf.cli")
                return str(entries[0]["value"]).strip(), f"sf.cli.{location.lower()}"
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return None, ""


def resolve_target_org(
    root: Path,
    dot: dict[str, Any],
    target_org_override: str | None = None,
) -> tuple[str | None, str]:
    """
    Pick target org for the opened project.

    Priority:
    1. Explicit CLI/API override
    2. Project .sf/config.json (default org for this folder — use on project open)
    3. Optional .cursor/sfdc-project/config.json override (non-null)
    4. sf config get scoped to project directory
    """
    if target_org_override:
        return target_org_override.strip(), "cli.override"

    alias, source = read_project_target_org(root)
    if alias:
        return alias, source

    for key in ("targetOrgAlias", "defaultOrgAlias", "defaultSandboxOrg"):
        val = dot.get(key)
        if val is not None and str(val).strip():
            return str(val).strip(), f"cursor.{key}"

    alias, source = sf_target_org_alias(root)
    if alias:
        return alias, source

    return None, "none"


def sf_org_display(project_root: Path, alias: str) -> dict:
    try:
        result = subprocess.run(
            ["sf", "org", "display", "--target-org", alias, "--json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout).get("result", {})
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        pass
    return {}


def find_promotion_repo(sandbox_root: Path) -> Path | None:
    env = os.environ.get("SFDC_PROMOTION_REPO") or os.environ.get("SFDC_PROMOTION_REPO_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p
    for parent in [sandbox_root.parent, *sandbox_root.parents]:
        for name in ("SFDC-CRM-SFDX", "sfdc-crm-sfdx"):
            candidate = parent / name
            if (candidate / "sfdx-project.json").exists():
                return candidate.resolve()
        if parent == parent.parent:
            break
    return None


def promotion_source_path(promotion_root: Path) -> str:
    if (promotion_root / "Master/main/default").exists():
        return "Master/main/default"
    return default_source_path(promotion_root)


def resolve_context(
    start: Path | None = None,
    target_org_override: str | None = None,
) -> dict[str, Any]:
    """Build full execution context for skills from cwd + sf CLI."""
    root = find_sfdx_project_root(start)
    dot = load_dot_cursor_configs(root)

    source_path = dot.get("sourcePath") or dot.get("sandboxSourcePath") or default_source_path(root)

    org_alias, org_source = resolve_target_org(root, dot, target_org_override)

    promotion_root = dot.get("promotionRepoRoot")
    if promotion_root:
        promotion_root = str(Path(promotion_root).expanduser().resolve())
    else:
        found = find_promotion_repo(root)
        promotion_root = str(found) if found else None

    promo_source = dot.get("promotionSourcePath")
    if not promo_source and promotion_root:
        promo_source = promotion_source_path(Path(promotion_root))

    org_info = sf_org_display(root, org_alias) if org_alias else {}

    ctx = {
        "projectRoot": str(root),
        "sourcePath": source_path,
        "targetOrgAlias": org_alias,
        "targetOrgSource": org_source,
        "instanceUrl": org_info.get("instanceUrl"),
        "username": org_info.get("username"),
        "promotionRepoRoot": promotion_root,
        "promotionSourcePath": promo_source or "Master/main/default",
        "promotionRemote": dot.get("promotionRemote", "origin"),
        "defaultBaseBranch": dot.get("defaultBaseBranch", "NextGenDev"),
        "defaultPrTargetBranch": dot.get("defaultPrTargetBranch", dot.get("defaultBaseBranch", "NextGenDev")),
        "jiraBaseUrl": dot.get("jiraBaseUrl", "https://servicetitan.atlassian.net"),
        "jiraProjectKey": dot.get("jiraProjectKey") or dot.get("projectKey", "SFDCLQ"),
        "parentStoryKey": dot.get("parentStoryKey", ""),
        "currentEpic": dot.get("currentEpic", ""),
        "currentEpicTitle": dot.get("currentEpicTitle", "") or dot.get("epicTitle", ""),
        "jiraPrefix": dot.get("jiraPrefix", "SFDCLQ"),
        "e2eDir": dot.get("e2eDir", "e2e"),
        "_dotCursor": str(root / ".cursor"),
    }
    return ctx


def inject_shared_path() -> Path:
    shared = Path.home() / ".cursor" / "skills" / "_shared"
    return shared


if __name__ == "__main__":
    import sys

    override = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(resolve_context(target_org_override=override), indent=2))
