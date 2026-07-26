#!/usr/bin/env python3
"""Shared helpers for SFDC promotion workflow scripts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def find_config(start: Path | None = None) -> Path:
    if start is None:
        start = Path.cwd()
    for directory in [start, *start.parents]:
        for rel in (
            ".cursor/sfdc-project/config.json",
            ".cursor/sfdc-promotion/config.json",
        ):
            candidate = directory / rel
            if candidate.exists():
                return candidate
    # Create default location under sfdc-project
    shared = Path.home() / ".cursor" / "skills" / "_shared"
    import sys
    sys.path.insert(0, str(shared))
    from sfdc_context import find_sfdx_project_root  # noqa: WPS433
    root = find_sfdx_project_root(start)
    return root / ".cursor" / "sfdc-project" / "config.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_config(config_path: Path | None = None) -> dict:
    shared = Path.home() / ".cursor" / "skills" / "_shared"
    import sys
    sys.path.insert(0, str(shared))
    from sfdc_context import find_sfdx_project_root, resolve_context  # noqa: WPS433

    if config_path:
        path = config_path
        root = find_sfdx_project_root()
    else:
        root = find_sfdx_project_root()
        path = find_config()

    file_cfg = load_json(path) if path.exists() else {}
    ctx = resolve_context(root)

    cfg = {
        "sandboxProjectRoot": ctx["projectRoot"],
        "sandboxSourcePath": ctx["sourcePath"],
        "promotionRepoRoot": ctx.get("promotionRepoRoot") or file_cfg.get("promotionRepoRoot"),
        "promotionSourcePath": ctx.get("promotionSourcePath") or file_cfg.get("promotionSourcePath", "Master/main/default"),
        "promotionRemote": file_cfg.get("promotionRemote", ctx.get("promotionRemote", "origin")),
        "defaultBaseBranch": file_cfg.get("defaultBaseBranch", ctx.get("defaultBaseBranch", "main")),
        "defaultPrTargetBranch": file_cfg.get("defaultPrTargetBranch", ctx.get("defaultPrTargetBranch", "main")),
        "defaultOrgAlias": ctx.get("targetOrgAlias"),
        "jiraPrefix": file_cfg.get("jiraPrefix", ctx.get("jiraPrefix", "PROJ")),
        "developerTag": file_cfg.get("developerTag", ""),
        "currentEpic": file_cfg.get("currentEpic", ctx.get("currentEpic", "")),
        "currentEpicTitle": file_cfg.get("currentEpicTitle", ctx.get("currentEpicTitle", "")),
        "instanceUrl": ctx.get("instanceUrl"),
        "username": ctx.get("username"),
    }
    cfg["_configPath"] = str(path) if path.exists() else str(root / ".cursor" / "sfdc-project" / "config.json")
    cfg["_promotionDir"] = str(Path(ctx["projectRoot"]) / ".cursor" / "sfdc-promotion")
    cfg["_context"] = ctx
    if not cfg.get("promotionRepoRoot"):
        raise FileNotFoundError(
            "promotionRepoRoot not found. Set SFDC_PROMOTION_REPO env var, "
            "add promotionRepoRoot to .cursor/sfdc-project/config.json, "
            "or place SFDC-CRM-SFDX as a sibling repo."
        )
    return cfg


def tracker_path(cfg: dict) -> Path:
    return Path(cfg["_promotionDir"]) / "sandbox-tracker.json"


def changelog_path(cfg: dict) -> Path:
    return Path(cfg["_promotionDir"]) / "sandbox-changelog.md"


def sandbox_root(cfg: dict) -> Path:
    return Path(cfg["sandboxProjectRoot"]) / cfg["sandboxSourcePath"]


def promotion_root(cfg: dict) -> Path:
    return Path(cfg["promotionRepoRoot"]) / cfg["promotionSourcePath"]


def normalize_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def resolve_sandbox_files(cfg: dict, paths: list[str]) -> list[str]:
    root = sandbox_root(cfg)
    resolved: list[str] = []
    for raw in paths:
        rel = normalize_rel(raw)
        candidate = Path(raw)
        if candidate.is_absolute() and candidate.exists():
            resolved.append(normalize_rel(str(candidate.relative_to(root))))
        elif (root / rel).exists():
            resolved.append(rel)
        elif (Path(cfg["sandboxProjectRoot"]) / rel).exists():
            resolved.append(
                normalize_rel(str((Path(cfg["sandboxProjectRoot"]) / rel).relative_to(root)))
            )
        else:
            print(f"Warning: file not found, skipping: {raw}", file=sys.stderr)
    return sorted(set(resolved))


def copy_files(cfg: dict, rel_paths: list[str]) -> list[str]:
    src_root = sandbox_root(cfg)
    dst_root = promotion_root(cfg)
    copied: list[str] = []
    for rel in rel_paths:
        src = src_root / rel
        dst = dst_root / rel
        if not src.exists():
            print(f"Warning: source missing, skipping: {src}", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        copied.append(rel)
    return copied


def render_changelog(cfg: dict, tracker: dict) -> str:
    lines = [
        "# Sandbox Deployment Changelog",
        "",
        f"**Org:** {tracker.get('org', cfg.get('defaultOrgAlias', ''))}",
        f"**Epic:** {tracker.get('epic', cfg.get('currentEpic', ''))}",
        f"**Updated:** {tracker.get('updatedAt', '')}",
        "",
    ]

    pending = tracker.get("pendingPromotion", [])
    if pending:
        lines.extend([
            "## Pending promotion to SFDC-CRM-SFDX",
            "",
            "| File | Ticket | Deployed |",
            "| --- | --- | --- |",
        ])
        for item in pending:
            lines.append(
                f"| `{item['path']}` | {item.get('ticket', '')} | {item.get('deployedAt', '')} |"
            )
        lines.append("")

    deployments = tracker.get("deployments", [])
    if deployments:
        lines.append("## Deployment history")
        lines.append("")
        for dep in reversed(deployments):
            lines.extend([
                f"### {dep.get('ticket', 'deploy')} — {dep.get('description', '')}",
                f"- **When:** {dep.get('deployedAt', '')}",
                f"- **Status:** {dep.get('status', '')}",
                f"- **Files:** {len(dep.get('files', []))}",
                "",
            ])
            if dep.get("deployCommand"):
                lines.append(f"```bash\n{dep['deployCommand']}\n```\n")

    promoted = tracker.get("promotions", [])
    if promoted:
        lines.append("## Promotions to SFDC-CRM-SFDX")
        lines.append("")
        for promo in reversed(promoted):
            lines.extend([
                f"### {promo.get('branch', '')} → {promo.get('targetBranch', '')}",
                f"- **When:** {promo.get('promotedAt', '')}",
                f"- **Commit:** {promo.get('commitMessage', '')}",
                f"- **Files:** {len(promo.get('files', []))}",
                "",
            ])

    return "\n".join(lines).strip() + "\n"
