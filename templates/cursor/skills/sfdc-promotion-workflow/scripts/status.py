#!/usr/bin/env python3
"""Show sandbox tracking and promotion status."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import changelog_path, load_config, load_json, render_changelog, tracker_path  # noqa: E402


def main() -> int:
    cfg = load_config()
    tracker_file = tracker_path(cfg)
    if tracker_file.exists():
        tracker = load_json(tracker_file)
    else:
        tracker = {"pendingPromotion": [], "promotions": [], "deployments": []}

    changelog_path(cfg).write_text(render_changelog(cfg, tracker), encoding="utf-8")

    pending = tracker.get("pendingPromotion", [])
    promoted = tracker.get("promotions", [])

    print(f"Config: {cfg['_configPath']}")
    print(f"Org: {tracker.get('org', cfg.get('defaultOrgAlias'))}")
    print(f"Epic: {tracker.get('epic', cfg.get('currentEpic', ''))}")
    print(f"Pending promotion: {len(pending)} file(s)")
    print(f"Promotion history: {len(promoted)} record(s)")
    print(f"Changelog: {changelog_path(cfg)}")
    print()

    if pending:
        print("Pending files:")
        for item in pending:
            print(f"  [{item.get('ticket', '')}] {item['path']}")
    else:
        print("No files pending promotion.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
