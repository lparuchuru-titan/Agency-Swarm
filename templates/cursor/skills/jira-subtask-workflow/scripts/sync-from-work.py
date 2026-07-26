#!/usr/bin/env python3
"""Sync sandbox/metadata changes into Jira subtask tracker and optionally Jira."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    build_dev_task_body,
    build_pds_body,
    classify_files,
    component_entries,
    find_project_root,
    git_changed_files,
    jira_credentials,
    load_config,
    read_sandbox_tracker,
    save_json,
    tracker_path,
    utc_now,
)
from jira_client import update_description  # noqa: E402


def apex_script_steps(root: Path, files: list[str]) -> list[dict]:
    steps = []
    for f in files:
        if not f.startswith("scripts/apex/") and not f.endswith(".apex"):
            continue
        path = root / f
        if not path.exists():
            continue
        steps.append({
            "title": path.name,
            "script": f"sf apex run --file {f} --target-org <ORG>",
            "notes": f"Source: `{f}` — run in target org (IDs resolved by ProductCode in script).",
        })
    return steps


def sandbox_deploy_steps(tracker: dict | None, org: str) -> list[dict]:
    if not tracker:
        return []
    steps = []
    for dep in tracker.get("deployments", []):
        steps.append({
            "title": f"{dep.get('ticket', 'deploy')} — {dep.get('description', '')}",
            "command": dep.get("deployCommand", ""),
            "notes": f"Files: {len(dep.get('files', []))} | Org: {org} | {dep.get('deployedAt', '')}",
        })
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync work to Jira subtask tracker")
    parser.add_argument("files", nargs="*", help="Optional explicit file paths")
    parser.add_argument("--deploy-command", help="Deploy command used")
    parser.add_argument("--ticket", help="Jira ticket for this batch")
    parser.add_argument("--push", action="store_true", help="Update Jira issue descriptions")
    parser.add_argument("--parent", help="Parent story key override")
    args = parser.parse_args()

    root = find_project_root()
    cfg = load_config(root)
    tracker_file = tracker_path(root)
    if not tracker_file.exists():
        print("Run init-story.py first for the parent story.")
        return 1

    tracker = __import__("json").loads(tracker_file.read_text())
    if args.parent:
        tracker["parentKey"] = args.parent

    source = cfg.get("sourcePath", "force-app/main/default")
    files = args.files or git_changed_files(root, source)

    promo = read_sandbox_tracker(root)
    if promo:
        for item in promo.get("pendingPromotion", []):
            path = item["path"]
            full = f"{source}/{path}"
            if full not in files:
                files.append(full)
        for dep in promo.get("deployments", []):
            for path in dep.get("files", []):
                full = f"{source}/{path}"
                if full not in files:
                    files.append(full)

    buckets = classify_files(files)
    org = cfg.get("defaultSandboxOrg", "")

    # Dev Task components
    dev_files = buckets["dev_task"]
    components = component_entries(dev_files, source)
    tracker["devTaskComponents"] = components

    deploy_cmds = list(tracker.get("deployCommands", []))
    if args.deploy_command:
        deploy_cmds.append(args.deploy_command)
    tracker["deployCommands"] = deploy_cmds

    dev_body = build_dev_task_body(cfg, components, deploy_cmds)

    # PDS Data steps
    data_steps = apex_script_steps(root, buckets["pds_data"] + [f for f in files if f.startswith("scripts/")])
    data_steps.extend(sandbox_deploy_steps(promo, org))
    tracker["pdsSteps"]["pds_data"] = data_steps

    # PDS Permissions & Layout
    perm_files = buckets["pds_permissions_layout"]
    perm_steps = []
    if perm_files:
        perm_steps.append({
            "title": "Deploy permission / layout metadata",
            "command": args.deploy_command or "sf project deploy start --source-dir ... --target-org <ORG>",
            "notes": "Files:\n" + "\n".join(f"* `{p}`" for p in perm_files),
        })
    perm_steps.append({
        "title": "Post-deploy verification",
        "notes": "* [ ] Assign permission set group to test users\n* [ ] Verify tab visibility\n* [ ] Verify FLS on new fields",
    })
    tracker["pdsSteps"]["pds_permissions_layout"] = perm_steps

    # PDS QCP
    qcp_files = buckets["pds_qcp"]
    if qcp_files:
        tracker["pdsSteps"]["pds_qcp"] = [{
            "title": "CPQ / Quote-related changes",
            "notes": "Changed files:\n" + "\n".join(f"* `{p}`" for p in qcp_files),
        }]

    # PDS Manual — preserve manual entries, append ticket note
    if args.ticket:
        tracker["pdsSteps"]["pds_manual"].append({
            "title": f"Related work — {args.ticket}",
            "notes": f"See parent/subtasks for {args.ticket}",
        })

    tracker["updatedAt"] = utc_now()
    save_json(tracker_file, tracker)

    # Write local markdown mirrors (for copy-paste / DevOps)
    jira_dir = Path(cfg["_jiraDir"])
    (jira_dir / "dev-task.md").write_text(dev_body.replace("h2.", "##").replace("{{code}}", "```").replace("{code}", "```"), encoding="utf-8")
    (jira_dir / "pds-data.md").write_text(
        build_pds_body("Data steps", data_steps).replace("h2.", "##").replace("h3.", "###").replace("{code}", "```"),
        encoding="utf-8",
    )
    (jira_dir / "pds-permissions-layout.md").write_text(
        build_pds_body("Permissions & Layout", perm_steps).replace("h2.", "##").replace("h3.", "###").replace("{code}", "```"),
        encoding="utf-8",
    )

    print(f"Synced {len(files)} file(s) → tracker")
    print(f"  Dev Task components: {len(components)}")
    print(f"  PDS Data steps: {len(data_steps)}")
    print(f"  Local markdown: {jira_dir}/dev-task.md")

    if args.push and jira_credentials():
        subtasks = tracker.get("subtasks", {})
        mapping = [
            ("dev_task", dev_body),
            ("pds_data", build_pds_body("Data steps (run per org)", data_steps)),
            ("pds_permissions_layout", build_pds_body("Permissions & Layout", perm_steps)),
            ("pds_qcp", build_pds_body("QCP steps", tracker["pdsSteps"].get("pds_qcp", []))),
            ("pds_manual", build_pds_body("Manual steps", tracker["pdsSteps"].get("pds_manual", []))),
        ]
        for bucket, body in mapping:
            key = subtasks.get(bucket, {}).get("key")
            if key and body.strip():
                update_description(key, body)
                print(f"  Updated Jira {key}")
    elif args.push:
        print("Skipping Jira push — set JIRA_EMAIL and JIRA_API_TOKEN")

    return 0


if __name__ == "__main__":
    sys.exit(main())
