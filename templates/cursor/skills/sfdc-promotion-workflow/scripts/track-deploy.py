#!/usr/bin/env python3
"""Record files deployed to sandbox for later promotion."""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    changelog_path,
    load_config,
    load_json,
    normalize_rel,
    resolve_sandbox_files,
    render_changelog,
    save_json,
    tracker_path,
    utc_now,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Track sandbox deployment files")
    parser.add_argument("files", nargs="*", help="Files or directories relative to sandbox source")
    parser.add_argument("-t", "--ticket", help="Jira ticket (e.g. PROJ-1001)")
    parser.add_argument("-d", "--description", help="Short description of the change")
    parser.add_argument("-c", "--deploy-command", help="Deploy command used")
    parser.add_argument("--from-git", action="store_true", help="Track changed files from git status")
    parser.add_argument("--from-deploy-log", help="Parse file paths from a deploy log")
    args = parser.parse_args()

    cfg = load_config()
    tracker_path_file = tracker_path(cfg)
    if tracker_path_file.exists():
        tracker = load_json(tracker_path_file)
    else:
        tracker = {"deployments": [], "pendingPromotion": [], "promotions": []}

    tracker["updatedAt"] = utc_now()
    tracker["org"] = cfg.get("defaultOrgAlias", "")
    if cfg.get("currentEpic"):
        tracker["epic"] = cfg["currentEpic"]

    files: list[str] = []
    if args.from_git:
        sandbox_root_path = Path(cfg["sandboxProjectRoot"])
        result = subprocess.run(
            ["git", "status", "--porcelain", cfg["sandboxSourcePath"]],
            cwd=sandbox_root_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                path = line[3:].strip()
                if path.startswith(cfg["sandboxSourcePath"]):
                    files.append(normalize_rel(path[len(cfg["sandboxSourcePath"]):].lstrip("/")))
    elif args.from_deploy_log:
        content = Path(args.from_deploy_log).read_text(encoding="utf-8", errors="ignore")
        prefix = cfg["sandboxSourcePath"] + "/"
        for line in content.splitlines():
            if prefix in line:
                idx = line.find(prefix)
                fragment = line[idx + len(prefix):].split()[0].strip("|")
                if fragment:
                    files.append(normalize_rel(fragment))
    else:
        source_root = Path(cfg["sandboxProjectRoot"]) / cfg["sandboxSourcePath"]
        for item in args.files:
            item_path = Path(item)
            if not item_path.is_absolute():
                item_path = Path.cwd() / item_path
            if item_path.is_dir():
                for path in item_path.rglob("*"):
                    if path.is_file():
                        files.append(normalize_rel(str(path.relative_to(source_root))))
            else:
                files.append(item)

    rel_files = resolve_sandbox_files(cfg, files)
    if not rel_files:
        print("No files to track.")
        return 1

    ticket = args.ticket or cfg.get("currentEpic", "sandbox-change")
    deployment = {
        "id": f"deploy-{len(tracker.get('deployments', [])) + 1:03d}",
        "ticket": ticket,
        "description": args.description or "",
        "deployedAt": utc_now(),
        "status": "deployed_to_sandbox",
        "files": rel_files,
        "deployCommand": args.deploy_command or "",
    }
    tracker.setdefault("deployments", []).append(deployment)

    pending = {item["path"]: item for item in tracker.get("pendingPromotion", [])}
    for rel in rel_files:
        pending[rel] = {
            "path": rel,
            "ticket": ticket,
            "description": args.description or "",
            "deployedAt": deployment["deployedAt"],
        }
    tracker["pendingPromotion"] = sorted(pending.values(), key=lambda x: x["path"])

    save_json(tracker_path_file, tracker)
    changelog_path(cfg).write_text(render_changelog(cfg, tracker), encoding="utf-8")

    print(f"Tracked {len(rel_files)} file(s) for ticket {ticket}.")
    for rel in rel_files:
        print(f"  + {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
