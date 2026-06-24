#!/usr/bin/env python3
"""Jira REST client (API v2) for subtask create/update."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

from lib import jira_credentials  # noqa: E402


def _request(method: str, url: str, data: dict | None = None) -> Any:
    creds = jira_credentials()
    if not creds:
        raise RuntimeError(
            "Jira credentials missing. Set JIRA_EMAIL and JIRA_API_TOKEN environment variables."
        )
    base, email, token = creds
    full_url = f"{base}{url}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(full_url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    import base64

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API {method} {url} failed ({e.code}): {err}") from e


def get_issue(key: str) -> dict:
    return _request("GET", f"/rest/api/2/issue/{key}")


def find_subtasks(parent_key: str) -> list[dict]:
    issue = get_issue(parent_key)
    subtasks = issue.get("fields", {}).get("subtasks", [])
    results = []
    for st in subtasks:
        results.append({
            "key": st["key"],
            "summary": st.get("fields", {}).get("summary", ""),
        })
    return results


def create_subtask(
    project_key: str,
    parent_key: str,
    summary: str,
    description: str,
    issue_type: str = "Sub-task",
) -> str:
    payload = {
        "fields": {
            "project": {"key": project_key},
            "parent": {"key": parent_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
    }
    result = _request("POST", "/rest/api/2/issue", payload)
    return result.get("key", "")


def update_description(issue_key: str, description: str) -> None:
    payload = {"fields": {"description": description}}
    _request("PUT", f"/rest/api/2/issue/{issue_key}", payload)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: jira_client.py <issue-key>")
        sys.exit(1)
    print(json.dumps(get_issue(sys.argv[1]), indent=2)[:2000])
