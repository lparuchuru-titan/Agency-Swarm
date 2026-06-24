#!/usr/bin/env python3
"""Add a manual PDS step to the tracker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import find_project_root, load_json, save_json, tracker_path, utc_now  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Add PDS manual step")
    parser.add_argument("--bucket", default="pds_manual",
                        choices=["pds_data", "pds_permissions_layout", "pds_qcp", "pds_manual"])
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-n", "--notes", default="")
    parser.add_argument("-c", "--command", default="")
    parser.add_argument("-s", "--script", default="")
    args = parser.parse_args()

    root = find_project_root()
    tracker_file = tracker_path(root)
    if not tracker_file.exists():
        print("Run init-story.py first.")
        return 1

    tracker = load_json(tracker_file)
    step = {"title": args.title, "notes": args.notes}
    if args.command:
        step["command"] = args.command
    if args.script:
        step["script"] = args.script
    tracker.setdefault("pdsSteps", {}).setdefault(args.bucket, []).append(step)
    tracker["updatedAt"] = utc_now()
    save_json(tracker_file, tracker)
    print(f"Added step to {args.bucket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
