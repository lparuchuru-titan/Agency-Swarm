#!/usr/bin/env python3
"""Show Jira subtask tracker status."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import find_project_root, load_json, tracker_path  # noqa: E402


def main() -> int:
    root = find_project_root()
    tf = tracker_path(root)
    if not tf.exists():
        print("No tracker. Run init-story.py PROJ-xxxx")
        return 1
    t = load_json(tf)
    print(f"Parent: {t.get('parentKey')} — {t.get('parentSummary', '')}")
    print(f"Updated: {t.get('updatedAt')}")
    print()
    for bucket, info in t.get("subtasks", {}).items():
        print(f"  [{bucket}] {info.get('key', 'local')} — {info.get('summary', '')}")
    print(f"\nDev components: {len(t.get('devTaskComponents', []))}")
    for bucket, steps in t.get("pdsSteps", {}).items():
        if steps:
            print(f"PDS {bucket}: {len(steps)} step(s)")
    print(f"\nLocal files: {Path(t.get('parentKey', '')).parent}/.cursor/jira-subtasks/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
