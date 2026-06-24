#!/usr/bin/env python3
"""Scaffold Playwright E2E setup in a Salesforce project."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES = SKILL_DIR / "templates"

sys.path.insert(0, str(SCRIPT_DIR))
from lib import find_project_root, load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold Playwright in project")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files")
    args = parser.parse_args()

    root = find_project_root()
    cfg = load_config(root)
    e2e = Path(cfg["projectRoot"]) / cfg.get("e2eDir", "e2e")

    copies = {
        "playwright.config.js": root / "playwright.config.js",
        "auth.setup.js": e2e / "auth.setup.js",
        "home.spec.js": e2e / "home.spec.js",
    }

    for src_name, dst in copies.items():
        src = TEMPLATES / src_name
        if dst.exists() and not args.force:
            print(f"Skip existing: {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"Created {dst}")

    pkg = Path(cfg["projectRoot"]) / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8")
        if "@playwright/test" not in text:
            print("Add @playwright/test to package.json devDependencies and npm scripts:")
            print("  npm install -D @playwright/test")
            print("  npm run test:e2e  -> playwright test")
    else:
        print("No package.json — install Playwright manually in project root.")

    print()
    print("Set credentials before running E2E:")
    print("  export SF_USERNAME=...")
    print("  export SF_PASSWORD=...")
    print("  export SF_LOGIN_URL=https://test.salesforce.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
