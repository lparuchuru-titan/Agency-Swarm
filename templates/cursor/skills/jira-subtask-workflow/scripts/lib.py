#!/usr/bin/env python3
"""Shared helpers for Jira subtask workflow."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METADATA_SUFFIXES = (
    ".cls-meta.xml",
    ".cls",
    ".trigger-meta.xml",
    ".trigger",
    ".js-meta.xml",
    ".js",
    ".html",
    ".css",
    ".xml",
    ".page-meta.xml",
    ".page",
    ".component-meta.xml",
    ".app-meta.xml",
    ".tab-meta.xml",
    ".layout-meta.xml",
    ".permissionset-meta.xml",
    ".profile-meta.xml",
    ".flow-meta.xml",
    ".md-meta.xml",
)

DATA_PATH_HINTS = (
    "scripts/apex/",
    "scripts/soql/",
    "SBQQ__LookupData__c",
    "Bundle_Definition__c",
    "Product2",
)

QCP_HINTS = (
    "SBQQ__Quote",
    "CPQ",
    "QCP",
    "QuoteCalculator",
    "ProductRule",
    "PriceRule",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def find_project_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    for directory in [start, *start.parents]:
        if (directory / "sfdx-project.json").exists():
            return directory
    raise FileNotFoundError("No sfdx-project.json found.")


def jira_config_path(root: Path) -> Path:
    return root / ".cursor" / "jira-subtasks" / "config.json"


def tracker_path(root: Path) -> Path:
    return root / ".cursor" / "jira-subtasks" / "tracker.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_dot_cursor(root: Path) -> dict:
    merged: dict = {}
    for rel in (
        ".cursor/sfdc-project/config.json",
        ".cursor/jira-subtasks/config.json",
    ):
        p = root / rel
        if p.exists():
            merged.update(load_json(p))
    return merged


def load_config(root: Path | None = None) -> dict:
    root = root or find_project_root()
    shared = Path.home() / ".cursor" / "skills" / "_shared"
    import sys
    sys.path.insert(0, str(shared))
    from sfdc_context import resolve_context  # noqa: WPS433

    ctx = resolve_context(root)
    dot = _read_dot_cursor(root)
    cfg_path = jira_config_path(root)

    defaults = {
        "projectRoot": ctx["projectRoot"],
        "jiraBaseUrl": dot.get("jiraBaseUrl", ctx.get("jiraBaseUrl", "https://yourcompany.atlassian.net")),
        "projectKey": dot.get("projectKey", dot.get("jiraProjectKey", ctx.get("jiraProjectKey", "PROJ"))),
        "defaultSandboxOrg": ctx.get("targetOrgAlias"),
        "parentStoryKey": dot.get("parentStoryKey", ctx.get("parentStoryKey", "")),
        "subtaskIssueType": dot.get("subtaskIssueType", "Sub-task"),
        "devTaskSummaryPrefix": "Dev Task",
        "pdsSummaryPrefix": "PDS",
        "sourcePath": ctx["sourcePath"],
        "instanceUrl": ctx.get("instanceUrl"),
        "username": ctx.get("username"),
    }
    if cfg_path.exists():
        defaults.update(load_json(cfg_path))
    defaults["_configPath"] = str(cfg_path)
    defaults["_jiraDir"] = str(cfg_path.parent)
    defaults["_context"] = ctx
    return defaults


def git_changed_files(root: Path, source_path: str) -> list[str]:
    files: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "status", "--porcelain", source_path],
    ):
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if cmd[-1] == source_path and len(line) > 3:
                path = line[3:].strip()
            else:
                path = line
            files.add(path.replace("\\", "/"))
    return sorted(files)


def metadata_type_from_path(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if "/classes/" in rel and rel.endswith(".cls"):
        return "ApexClass"
    if "/classes/" in rel and rel.endswith("Test.cls"):
        return "ApexClass (Test)"
    if "/triggers/" in rel:
        return "ApexTrigger"
    if "/lwc/" in rel:
        return "LightningComponentBundle"
    if "/aura/" in rel:
        return "AuraDefinitionBundle"
    if "/objects/" in rel and rel.endswith(".object-meta.xml"):
        return "CustomObject"
    if "/objects/" in rel and "/fields/" in rel:
        return "CustomField"
    if "/permissionsets/" in rel:
        return "PermissionSet"
    if "/profiles/" in rel:
        return "Profile"
    if "/layouts/" in rel:
        return "Layout"
    if "/tabs/" in rel:
        return "CustomTab"
    if "/flexipages/" in rel:
        return "FlexiPage"
    if "/flows/" in rel:
        return "Flow"
    if "/customMetadata/" in rel:
        return "CustomMetadata"
    return "Metadata"


def classify_file(path: str) -> set[str]:
    """Return bucket tags: dev_task, pds_data, pds_permissions_layout, pds_qcp, pds_manual."""
    p = path.replace("\\", "/").lower()
    buckets: set[str] = set()

    if p.startswith("scripts/apex/") or p.endswith(".apex"):
        buckets.add("pds_data")
        return buckets

    if any(h.lower() in p for h in DATA_PATH_HINTS) and "objects/" not in p and "/fields/" not in p:
        if p.startswith("scripts/"):
            buckets.add("pds_data")

    under_source = "force-app/" in p or "master/" in p
    if under_source or any(p.endswith(s.replace("-meta.xml", "")) or p.endswith(s) for s in METADATA_SUFFIXES):
        if "/profiles/" in p or "/layouts/" in p:
            buckets.add("dev_task")
            buckets.add("pds_permissions_layout")
        elif any(h.lower() in p for h in QCP_HINTS):
            buckets.add("dev_task")
            buckets.add("pds_qcp")
        else:
            buckets.add("dev_task")

    return buckets or {"pds_manual"}


def classify_files(files: list[str]) -> dict[str, list[str]]:
    result = {
        "dev_task": [],
        "pds_data": [],
        "pds_permissions_layout": [],
        "pds_qcp": [],
        "pds_manual": [],
    }
    for f in files:
        for bucket in classify_file(f):
            result[bucket].append(f)
    for key in result:
        result[key] = sorted(set(result[key]))
    return result


def read_sandbox_tracker(root: Path) -> dict | None:
    promo = root / ".cursor" / "sfdc-promotion" / "sandbox-tracker.json"
    if promo.exists():
        return load_json(promo)
    return None


def build_dev_task_body(cfg: dict, components: list[dict], deploy_commands: list[str]) -> str:
    org = cfg.get("defaultSandboxOrg", "sandbox")
    lines = [
        f"h2. Metadata deployed / changed ({org})",
        "",
        "|| Component || Type || Path ||",
    ]
    for c in components:
        lines.append(f"| {c['name']} | {c['type']} | {c['path']} |")
    lines.extend(["", "h2. Deploy command(s)", ""])
    for cmd in deploy_commands:
        lines.append(f"{{code}}\n{cmd}\n{{code}}")
    lines.extend([
        "",
        "h2. Validation checklist",
        "* [ ] Check-only deploy succeeded (0 errors)",
        "* [ ] Apex tests for changed classes passed",
        "* [ ] Smoke test in sandbox UI",
        "",
        f"_Auto-updated: {utc_now()}_",
    ])
    return "\n".join(lines)


def build_pds_body(title: str, steps: list[dict]) -> str:
    lines = [f"h2. {title}", "", "_Run in each target org. Record IDs differ — use ProductCode/scripts, not copy/paste of IDs._", ""]
    for i, step in enumerate(steps, 1):
        lines.append(f"h3. Step {i} — {step.get('title', 'Step')}")
        if step.get("ticket"):
            lines.append(f"*Jira:* {step['ticket']}")
        if step.get("script"):
            lines.append(f"{{code}}\n{step['script']}\n{{code}}")
        if step.get("command"):
            lines.append(f"{{code}}\n{step['command']}\n{{code}}")
        if step.get("notes"):
            lines.append(step["notes"])
        lines.append("")
    lines.append(f"_Auto-updated: {utc_now()}_")
    return "\n".join(lines)


def component_entries(files: list[str], source_path: str) -> list[dict]:
    entries = []
    for f in files:
        rel = f.replace("\\", "/")
        name = Path(rel).name
        if name.endswith("-meta.xml"):
            name = name[:-10]
        entries.append({
            "name": name,
            "type": metadata_type_from_path(rel),
            "path": rel,
        })
    return entries


def jira_credentials() -> tuple[str, str, str] | None:
    base = os.environ.get("JIRA_BASE_URL", "https://yourcompany.atlassian.net").rstrip("/")
    email = os.environ.get("JIRA_EMAIL") or os.environ.get("ATLASSIAN_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN") or os.environ.get("ATLASSIAN_API_TOKEN")
    if email and token:
        return base, email, token
    return None


def subtask_templates(parent_key: str, parent_summary: str) -> dict[str, str]:
    short = parent_summary[:80] if parent_summary else parent_key
    return {
        "dev_task": f"Dev Task — {short}",
        "pds_data": f"PDS (Data) — {short}",
        "pds_permissions_layout": f"PDS (Permissions & Layout) — {short}",
        "pds_qcp": f"PDS (QCP) — {short}",
        "pds_manual": f"PDS (Manual Steps) — {short}",
    }
