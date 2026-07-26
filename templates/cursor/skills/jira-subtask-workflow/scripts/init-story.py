#!/usr/bin/env python3
"""Initialize Jira subtask tracker for a parent story."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    find_project_root,
    jira_credentials,
    load_config,
    save_json,
    subtask_templates,
    tracker_path,
    utc_now,
)
from jira_client import create_subtask, find_subtasks, get_issue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Init Jira subtasks for a story")
    parser.add_argument("parent_key", help="Parent Jira key e.g. PROJ-1001")
    parser.add_argument("--title", help="Parent story title for subtask summaries")
    parser.add_argument("--push", action="store_true", help="Create missing subtasks in Jira")
    parser.add_argument("--types", nargs="*", default=["dev_task", "pds_data", "pds_permissions_layout", "pds_manual"],
                        help="Subtask buckets to initialize")
    args = parser.parse_args()

    root = find_project_root()
    cfg = load_config(root)
    cfg["parentStoryKey"] = args.parent_key
    save_json(Path(cfg["_configPath"]), cfg)

    parent_summary = args.title or args.parent_key
    if jira_credentials():
        try:
            issue = get_issue(args.parent_key)
            parent_summary = issue.get("fields", {}).get("summary", parent_summary)
        except Exception as e:
            print(f"Warning: could not fetch parent issue: {e}")

    templates = subtask_templates(args.parent_key, parent_summary)
    tracker_file = tracker_path(root)
    tracker = {
        "parentKey": args.parent_key,
        "parentSummary": parent_summary,
        "updatedAt": utc_now(),
        "subtasks": {},
        "devTaskComponents": [],
        "pdsSteps": {
            "pds_data": [],
            "pds_permissions_layout": [],
            "pds_qcp": [],
            "pds_manual": [],
        },
        "deployCommands": [],
    }

    existing_jira: dict[str, str] = {}
    if jira_credentials() and args.push:
        for st in find_subtasks(args.parent_key):
            summary = st["summary"].lower()
            if summary.startswith("dev task"):
                existing_jira["dev_task"] = st["key"]
            elif "pds (data)" in summary:
                existing_jira["pds_data"] = st["key"]
            elif "pds (permission" in summary or "pds (permissions" in summary:
                existing_jira["pds_permissions_layout"] = st["key"]
            elif "pds (qcp)" in summary:
                existing_jira["pds_qcp"] = st["key"]
            elif "pds (manual" in summary:
                existing_jira["pds_manual"] = st["key"]

    for bucket in args.types:
        summary = templates.get(bucket, f"PDS — {parent_summary}")
        key = existing_jira.get(bucket, "")
        if args.push and jira_credentials() and not key:
            placeholder = f"Subtask for {bucket}. Will be updated as work is deployed to sandbox."
            key = create_subtask(
                cfg["projectKey"],
                args.parent_key,
                summary,
                placeholder,
                cfg.get("subtaskIssueType", "Sub-task"),
            )
            print(f"Created {key}: {summary}")
        tracker["subtasks"][bucket] = {"key": key, "summary": summary}

    save_json(tracker_file, tracker)
    print(f"Tracker: {tracker_file}")
    for bucket, info in tracker["subtasks"].items():
        print(f"  {bucket}: {info.get('key') or '(local only)'} — {info['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
