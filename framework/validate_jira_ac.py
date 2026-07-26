#!/usr/bin/env python3
"""Validate repo metadata against Jira story acceptance criteria (layouts, fields).

Usage:
  python3 tools/sfdc-knowledge-swarm/validate_jira_ac.py PROJ-1001
  python3 tools/sfdc-knowledge-swarm/validate_jira_ac.py PROJ-1001 --target-org MY_SANDBOX

Register story -> metadata AC checks in STORY_CHECKS below for your project.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAYOUTS = REPO / "force-app/main/default/layouts"
FIELDS = REPO / "force-app/main/default/objects"

# Example — replace with your project's story -> metadata AC mapping.
STORY_CHECKS: dict[str, dict] = {
    "PROJ-1001": {
        "title": "Product2 example custom fields",
        "fields": [
            "Product2/fields/Example_Flag__c.field-meta.xml",
            "Product2/fields/Example_Value__c.field-meta.xml",
        ],
        "layout": "docs/reference/layouts/Product2-Product Layout-example-section.layout-meta.xml",
        "layout_member": "Product2-Product Layout",
        "layout_fields": ["Example_Flag__c", "Example_Value__c"],
    },
}


def check_files(paths: list[str]) -> list[str]:
    missing = []
    for rel in paths:
        if not (FIELDS / rel).is_file() and not (REPO / "force-app/main/default/layouts" / rel).is_file():
            if not (FIELDS.parent / rel).exists() and not Path(rel).exists():
                p = FIELDS / rel if "fields" in rel else LAYOUTS / rel
                if not p.is_file():
                    missing.append(str(p))
    return missing


def check_layout(layout_name: str, field_apis: list[str]) -> list[str]:
    # layout_name may be a path under repo (docs/reference) or layouts/*.layout-meta.xml
    if "/" in layout_name or layout_name.startswith("docs/"):
        path = REPO / layout_name
    else:
        path = LAYOUTS / layout_name
    if not path.is_file():
        return [f"Layout file missing: {path}"]
    text = path.read_text()
    gaps = []
    for api in field_apis:
        if f"<field>{api}</field>" not in text:
            gaps.append(f"{api} not on layout {layout_name}")
    return gaps


def org_layout_has_fields(org: str, layout_member: str, field_apis: list[str]) -> list[str]:
    """Retrieve layout from org and verify fields (optional)."""
    tmp = REPO / ".cursor/tmp-retrieve-ac"
    tmp.mkdir(parents=True, exist_ok=True)
    pkg = tmp / "package.xml"
    pkg.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
  <types><members>{layout_member}</members><name>Layout</name></types>
  <version>66.0</version>
</Package>"""
    )
    subprocess.run(
        [
            "sf",
            "project",
            "retrieve",
            "start",
            "--manifest",
            str(pkg),
            "--target-org",
            org,
            "--output-dir",
            str(tmp),
            "--wait",
            "10",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    layout_file = tmp / "layouts" / f"{layout_member}.layout-meta.xml"
    if not layout_file.is_file():
        return [f"Could not retrieve layout {layout_member} from org {org}"]
    text = layout_file.read_text()
    gaps = []
    for api in field_apis:
        if f"<field>{api}</field>" not in text:
            gaps.append(f"Org layout missing field {api}")
    return gaps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("story", help="Jira key e.g. PROJ-1001")
    parser.add_argument("--target-org", help="Optional org alias to verify deployed layout")
    args = parser.parse_args()

    spec = STORY_CHECKS.get(args.story)
    if not spec:
        print(f"No AC rules registered for {args.story}")
        sys.exit(1)

    print(f"# AC validation — {args.story} ({spec['title']})")
    failures: list[str] = []

    for rel in spec["fields"]:
        p = FIELDS / rel
        if not p.is_file():
            failures.append(f"Missing field metadata: {p}")

    failures.extend(check_layout(spec["layout"], spec["layout_fields"]))

    if args.target_org:
        layout_member = spec.get("layout_member") or spec["layout"].replace(".layout-meta.xml", "")
        failures.extend(org_layout_has_fields(args.target_org, layout_member, spec["layout_fields"]))

    if failures:
        print("\n## FAILURES")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)

    print("\nAll registered AC checks passed.")


if __name__ == "__main__":
    main()
