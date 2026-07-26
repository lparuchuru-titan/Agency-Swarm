#!/usr/bin/env python3
"""Prepare SFDC-CRM-SFDX feature branch with sandbox changes."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    changelog_path,
    copy_files,
    load_config,
    load_json,
    promotion_root,
    render_changelog,
    save_json,
    tracker_path,
    utc_now,
)


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, text=True, check=check)


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip())
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")[:60]


def suggest_branch_name(cfg: dict, ticket: str, description: str) -> str:
    desc = slugify(description) if description else slugify(cfg.get("currentEpicTitle", ""))
    ticket_clean = ticket.replace("/", "-")
    if desc:
        return f"{ticket_clean}-{desc}"
    return ticket_clean


def suggest_commit_message(branch: str, version: str = "V1") -> str:
    return f"C-{branch}-{version}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare feature branch in SFDC-CRM-SFDX")
    parser.add_argument("-b", "--branch", help="Feature branch name")
    parser.add_argument("-t", "--ticket", help="Jira ticket")
    parser.add_argument("-d", "--description", help="Short description for branch name")
    parser.add_argument("--base-branch", help="Base branch to pull (default: main)")
    parser.add_argument("--commit-message", help="Commit message (default: C-{branch}-V1)")
    parser.add_argument("--commit", action="store_true", help="Create commit after staging")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without copying")
    args = parser.parse_args()

    cfg = load_config()
    tracker_file = tracker_path(cfg)
    tracker = load_json(tracker_file) if tracker_file.exists() else {"pendingPromotion": []}
    pending = tracker.get("pendingPromotion", [])
    if not pending:
        print("Nothing pending promotion. Track a sandbox deploy first.")
        return 1

    ticket = args.ticket or cfg.get("currentEpic", "PROJ-change")
    description = args.description or cfg.get("currentEpicTitle", "")
    branch = args.branch or suggest_branch_name(cfg, ticket, description)
    base_branch = args.base_branch or cfg.get("defaultBaseBranch", "main")
    commit_message = args.commit_message or suggest_commit_message(branch)
    rel_files = [item["path"] for item in pending]

    repo = Path(cfg["promotionRepoRoot"])
    remote = cfg.get("promotionRemote", "origin")

    print("=== Promotion plan ===")
    print(f"Sandbox project: {cfg['sandboxProjectRoot']}")
    print(f"Promotion repo:  {repo}")
    print(f"Base branch:     {base_branch}")
    print(f"Feature branch:  {branch}")
    print(f"Files:           {len(rel_files)}")
    print(f"Commit message:  {commit_message}")
    print()

    if args.dry_run:
        for rel in rel_files:
            print(f"  would copy: {rel}")
        return 0

    run(["git", "fetch", remote], cwd=repo)
    run(["git", "checkout", base_branch], cwd=repo)
    run(["git", "pull", remote, base_branch], cwd=repo)

    existing = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if existing.returncode == 0:
        run(["git", "checkout", branch], cwd=repo)
        run(["git", "merge", f"{remote}/{base_branch}", "--no-edit"], cwd=repo, check=False)
    else:
        run(["git", "checkout", "-b", branch], cwd=repo)

    copied = copy_files(cfg, rel_files)
    if not copied:
        print("No files copied.")
        return 1

    dst_paths = [str(promotion_root(cfg) / rel) for rel in copied]
    run(["git", "add", "--"] + dst_paths, cwd=repo)
    run(["git", "status", "--short"], cwd=repo)

    promotion_record = {
        "branch": branch,
        "targetBranch": cfg.get("defaultPrTargetBranch", base_branch),
        "ticket": ticket,
        "description": description,
        "promotedAt": utc_now(),
        "commitMessage": commit_message,
        "files": copied,
        "committed": False,
    }

    if args.commit:
        run(["git", "commit", "-m", commit_message], cwd=repo)
        promotion_record["committed"] = True
        print()
        print("Committed. Next steps:")
        print(f"  git push -u {remote} {branch}")
        print(
            f"  gh pr create --repo your-org/your-prod-metadata-repo "
            f"--base {promotion_record['targetBranch']} --head {branch}"
        )
    else:
        print()
        print("Staged and ready to commit. Run:")
        print(f"  git commit -m \"{commit_message}\"")
        print(f"  git push -u {remote} {branch}")

    tracker.setdefault("promotions", []).append(promotion_record)
    tracker["pendingPromotion"] = [item for item in pending if item["path"] not in copied]
    tracker["updatedAt"] = utc_now()
    save_json(tracker_file, tracker)
    changelog_path(cfg).write_text(render_changelog(cfg, tracker), encoding="utf-8")

    summary_path = Path(cfg["_promotionDir"]) / "last-promotion-summary.md"
    summary_path.write_text(
        "\n".join([
            "# Last Promotion Summary",
            "",
            f"- **Branch:** `{branch}`",
            f"- **Base:** `{base_branch}`",
            f"- **PR target:** `{promotion_record['targetBranch']}`",
            f"- **Ticket:** `{ticket}`",
            f"- **Commit message:** `{commit_message}`",
            f"- **Files:** {len(copied)}",
            "",
            "## Files",
            "",
            *[f"- `{rel}`" for rel in copied],
            "",
            "## PR template",
            "",
            f"**Title:** `{ticket}: {description or branch}`",
            "",
            "**Summary**",
            f"- Promotes sandbox-validated metadata from {cfg.get('defaultOrgAlias', 'sandbox')}",
            f"- Ticket: {ticket}",
            "",
            "**Test plan**",
            "- [ ] Validate deploy to target sandbox",
            "- [ ] Run affected Apex tests",
            "",
        ]),
        encoding="utf-8",
    )
    print(f"Summary written: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
