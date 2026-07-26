"""Connected resource indexes — Jira, Confluence, Drive, Sheets (minimal token footprint)."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from config import KB_DIR, ensure_dirs, get_runtime
from skill_schedule_config import CONNECTED_MAX_ITEMS

CONNECTED_DIR = KB_DIR / "connected"
TIMEOUT = 25.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_catalog(name: str, lines: List[str]) -> str:
    ensure_dirs()
    CONNECTED_DIR.mkdir(parents=True, exist_ok=True)
    path = CONNECTED_DIR / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _jira_rest_search(jql: str, max_results: int) -> List[Dict[str, Any]]:
    base = os.environ.get("JIRA_URL", os.environ.get("ATLASSIAN_SITE_URL", "")).rstrip("/")
    email = os.environ.get("JIRA_EMAIL", os.environ.get("ATLASSIAN_EMAIL", ""))
    token = os.environ.get("JIRA_API_TOKEN", os.environ.get("ATLASSIAN_API_TOKEN", ""))
    if not base or not email or not token:
        return []

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"{base}/rest/api/3/search"
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    params = {"jql": jql, "maxResults": max_results, "fields": "summary,status,updated,issuetype"}

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, headers=headers, params=params)
        if resp.status_code >= 400:
            return []
        data = resp.json()
        return data.get("issues", [])
    except Exception:  # noqa: BLE001
        return []


def refresh_jira_index() -> Dict[str, Any]:
    """Index recent Jira issues by project — REST only, no LLM."""
    ctx = get_runtime()
    projects = [ctx.get("jiraProjectKey") or ctx.get("jiraPrefix") or "PROJ"]
    projects = [p.strip() for p in projects if p and str(p).strip()]
    jql = " OR ".join(f"project = {p}" for p in projects) if projects else "updated >= -30d"
    if projects:
        jql = f"({jql}) AND updated >= -30d ORDER BY updated DESC"

    issues = _jira_rest_search(jql, CONNECTED_MAX_ITEMS)
    lines = [
        "# Jira index (connected)",
        f"_Updated {_now()} · token-free REST catalog · use MCP in Cursor for full bodies_",
        "",
        "| Key | Type | Status | Summary |",
        "| --- | --- | --- | --- |",
    ]
    if issues:
        for issue in issues:
            key = issue.get("key", "")
            fields = issue.get("fields", {})
            summary = (fields.get("summary") or "").replace("|", "\\|")[:120]
            status = fields.get("status", {}).get("name", "")
            itype = fields.get("issuetype", {}).get("name", "")
            lines.append(f"| {key} | {itype} | {status} | {summary} |")
    else:
        lines.extend(
            [
                "_No REST results._",
                "",
                "**MCP refresh (Cursor):** `atlassian:searchJiraIssuesUsingJql`",
                f"JQL: `{jql}`",
                "",
                "Set `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` for scheduled REST index.",
            ]
        )

    path = _write_catalog("jira-index.md", lines)
    return {"resource": "jira", "items": len(issues), "path": path, "token_cost": 0}


def refresh_confluence_index() -> Dict[str, Any]:
    """Confluence catalog stub or CQL search when Atlassian credentials exist."""
    base = os.environ.get("ATLASSIAN_SITE_URL", os.environ.get("JIRA_URL", "")).rstrip("/")
    email = os.environ.get("ATLASSIAN_EMAIL", os.environ.get("JIRA_EMAIL", ""))
    token = os.environ.get("ATLASSIAN_API_TOKEN", os.environ.get("JIRA_API_TOKEN", ""))

    pages: List[Dict[str, Any]] = []
    if base and email and token:
        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        cql = os.environ.get(
            "CONFLUENCE_CQL",
            "type=page AND lastModified >= now(\"-30d\") ORDER BY lastModified DESC",
        )
        url = f"{base}/wiki/rest/api/content/search"
        headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
        params = {"cql": cql, "limit": CONNECTED_MAX_ITEMS}
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.get(url, headers=headers, params=params)
            if resp.status_code < 400:
                pages = resp.json().get("results", [])
        except Exception:  # noqa: BLE001
            pages = []

    lines = [
        "# Confluence index (connected)",
        f"_Updated {_now()} · titles only · full pages via MCP_",
        "",
        "| Title | Space | Last modified |",
        "| --- | --- | --- |",
    ]
    if pages:
        for p in pages:
            title = (p.get("title") or "").replace("|", "\\|")[:100]
            space = p.get("resultGlobalContainer", {}).get("displayUrl", "")[:40]
            when = p.get("lastModified", "")[:10]
            lines.append(f"| {title} | {space} | {when} |")
    else:
        lines.extend(
            [
                "_No REST results._",
                "",
                "**MCP refresh:** `atlassian:searchConfluenceUsingCql` / `getConfluencePage`",
                "Authenticate Google Workspace MCP for Drive/Sheets in Cursor settings.",
            ]
        )

    path = _write_catalog("confluence-index.md", lines)
    return {"resource": "confluence", "items": len(pages), "path": path, "token_cost": 0}


def refresh_gdrive_gsheets_index() -> Dict[str, Any]:
    """
    Drive/Sheets cannot be scheduled without Google OAuth in Python.
    Write MCP checklist + optional local export folder scan.
    """
    export_dir = Path(os.environ.get("GDRIVE_EXPORT_DIR", KB_DIR / "connected" / "exports"))
    local_files: List[Path] = []
    if export_dir.is_dir():
        local_files = sorted(export_dir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        local_files = [p for p in local_files if p.is_file()][:CONNECTED_MAX_ITEMS]

    lines = [
        "# Google Drive & Sheets index (connected)",
        f"_Updated {_now()} · MCP-first · scheduled Python uses local exports if present_",
        "",
        "## MCP refresh (Cursor — zero scheduled tokens)",
        "- `Google Workspace:drive_search` — specs, decks, requirement docs",
        "- `Google Workspace:sheets_read` — field matrices, CPQ trackers",
        "",
        "## Local exports (optional)",
    ]
    if local_files:
        lines.append("")
        lines.append("| File | Modified |")
        lines.append("| --- | --- |")
        for p in local_files:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            lines.append(f"| `{p.name}` | {mtime} |")
        lines.append("")
        lines.append(f"_Export folder: `{export_dir}`_")
    else:
        lines.extend(
            [
                "_No local exports._",
                "",
                "Optional: export Drive/Sheets to",
                f"`{export_dir}` for offline scheduled index (0 tokens).",
            ]
        )

    path = _write_catalog("gdrive-gsheets-index.md", lines)
    return {"resource": "gdrive_gsheets", "items": len(local_files), "path": path, "token_cost": 0}


def refresh_all_connected() -> Dict[str, Any]:
    results = [
        refresh_jira_index(),
        refresh_confluence_index(),
        refresh_gdrive_gsheets_index(),
    ]
    index_lines = [
        "# Connected resources — master index",
        f"_Updated {_now()}_",
        "",
        "| Resource | Items | Catalog |",
        "| --- | --- | --- |",
    ]
    for r in results:
        index_lines.append(f"| {r['resource']} | {r['items']} | [{r['resource']}]({Path(r['path']).name}) |")

    master = _write_catalog("INDEX.md", index_lines)
    return {"tier": "connected", "token_cost": 0, "master_index": master, "results": results}
