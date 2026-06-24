#!/usr/bin/env python3
"""Build a package.xml from sf project retrieve preview JSON output."""

import json
import sys
from collections import defaultdict
from pathlib import Path


def read_api_version(project_root: Path) -> str:
    sfdx_path = project_root / "sfdx-project.json"
    if sfdx_path.exists():
        data = json.loads(sfdx_path.read_text())
        return str(data.get("sourceApiVersion", "66.0"))
    return "66.0"


def build_package_xml(by_type: dict[str, list[str]], api_version: str) -> str:
    lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<Package xmlns=\"http://soap.sforce.com/2006/04/metadata\">",
    ]
    for mtype in sorted(by_type.keys()):
        lines.append("    <types>")
        for name in sorted(by_type[mtype]):
            lines.append(f"        <members>{name}</members>")
        lines.append(f"        <name>{mtype}</name>")
        lines.append("    </types>")
    lines.append(f"    <version>{api_version}</version>")
    lines.append("</Package>")
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: build-delta-package.py <preview-json> <output-package.xml> [project-root]", file=sys.stderr)
        return 1

    preview_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    project_root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.cwd()

    data = json.loads(preview_path.read_text())
    result = data.get("result", {})

    by_type: dict[str, list[str]] = defaultdict(list)
    for item in result.get("toRetrieve", []):
        if item.get("operation") == "retrieve":
            by_type[item["type"]].append(item["fullName"])

    component_count = sum(len(names) for names in by_type.values())

    report = {
        "toRetrieveCount": component_count,
        "toRetrieveByType": {k: len(v) for k, v in sorted(by_type.items())},
        "toDeployCount": len(result.get("toDeploy", [])),
        "toDeleteCount": len(result.get("toDelete", [])),
        "conflictCount": len(result.get("conflicts", [])),
        "toDeploy": result.get("toDeploy", []),
        "toDelete": result.get("toDelete", []),
        "conflicts": result.get("conflicts", []),
    }

    report_path = project_root / "manifest" / "delta-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    if component_count == 0:
        output_path.write_text("")
        print(f"No delta components to retrieve. Report: {report_path}")
        return 0

    api_version = read_api_version(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_package_xml(by_type, api_version))
    print(f"Built {output_path} with {component_count} components. Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
