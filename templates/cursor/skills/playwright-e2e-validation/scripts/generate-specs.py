#!/usr/bin/env python3
"""Generate Playwright spec files from changed Salesforce/web source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    apex_class_from_path,
    apex_test_class,
    find_project_root,
    find_tab_for_lwc,
    git_changed_files,
    kebab_lwc_tag,
    load_config,
    lwc_name_from_path,
    read_lwc_meta,
    slugify,
)


def render_lwc_tab_spec(lwc: dict, tab_api: str | None, cfg: dict) -> str:
    tag = kebab_lwc_tag(lwc["name"])
    path = f"{cfg.get('defaultTabPrefix', '/lightning/n/')}{tab_api or lwc['name']}"
    return f"""const {{ test, expect }} = require('@playwright/test');

test.describe('{lwc["label"]}', () => {{
  test('loads Lightning tab and component is visible', async ({{ page }}) => {{
    await page.goto('{path}');
    await expect(page.locator('{tag}')).toBeVisible({{ timeout: 90_000 }});
  }});

  test('renders primary content without fatal errors', async ({{ page }}) => {{
    await page.goto('{path}');
    const component = page.locator('{tag}');
    await expect(component).toBeVisible({{ timeout: 90_000 }});
    await expect(component).not.toContainText('Unhandled error');
  }});
}});
"""


def render_lwc_record_spec(lwc: dict, object_api: str) -> str:
    tag = kebab_lwc_tag(lwc["name"])
    # Placeholder record URL — replace RECORD_ID or set E2E_QUOTE_ID env in config
    path = f"/lightning/r/{object_api}/{{{{E2E_RECORD_ID}}}}/view"
    return f"""const {{ test, expect }} = require('@playwright/test');

const recordId = process.env.E2E_RECORD_ID;
test.describe('{lwc["label"]} on record page', () => {{
  test.beforeEach(({{}}, testInfo) => {{
    if (!recordId) {{
      testInfo.skip(true, 'Set E2E_RECORD_ID for record-page validation');
    }}
  }});

  test('loads record page with component', async ({{ page }}) => {{
    await page.goto(`/lightning/r/{object_api}/${{recordId}}/view`);
    await expect(page.locator('{tag}')).toBeVisible({{ timeout: 90_000 }});
  }});
}});
"""


def render_generic_lwc_spec(lwc: dict) -> str:
    tag = kebab_lwc_tag(lwc["name"])
    return f"""const {{ test, expect }} = require('@playwright/test');

test.describe('{lwc["label"]}', () => {{
  test('component tag exists after Lightning shell loads', async ({{ page }}) => {{
    await page.goto('/lightning/page/home');
    await expect(page.locator('body')).toBeVisible();
    // TODO: navigate to the app page or tab where {lwc["name"]} is hosted
    // await page.goto('/lightning/n/<TabApiName>');
    // await expect(page.locator('{tag}')).toBeVisible({{ timeout: 90_000 }});
  }});
}});
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Playwright specs from changes")
    parser.add_argument("files", nargs="*", help="Optional explicit file paths")
    parser.add_argument("--write", action="store_true", help="Write spec files to e2e/generated")
    parser.add_argument("--json", action="store_true", help="Print generation plan as JSON")
    args = parser.parse_args()

    root = find_project_root()
    cfg = load_config(root)
    source_root = Path(cfg["projectRoot"]) / cfg["sourcePath"]
    e2e_dir = Path(cfg["projectRoot"]) / cfg.get("e2eDir", "e2e")
    generated_dir = e2e_dir / "generated"

    files = args.files or git_changed_files(Path(cfg["projectRoot"]), cfg["sourcePath"])
    lwcs: set[str] = set()
    apex_classes: set[str] = set()
    tabs: list[str] = []

    for f in files:
        lwc = lwc_name_from_path(f)
        if lwc:
            lwcs.add(lwc)
        apex = apex_class_from_path(f)
        if apex:
            apex_classes.add(apex)
        if "/tabs/" in f.replace("\\", "/") and f.endswith(".tab-meta.xml"):
            tabs.append(f)

    plan = {
        "projectRoot": cfg["projectRoot"],
        "e2eDir": str(e2e_dir),
        "lwcs": [],
        "apexTests": sorted({apex_test_class(c) for c in apex_classes}),
        "generatedSpecs": [],
    }

    specs: dict[str, str] = {}

    for lwc_name in sorted(lwcs):
        meta = read_lwc_meta(source_root, lwc_name)
        tab_api = find_tab_for_lwc(source_root, meta) if "lightning__Tab" in meta["targets"] else None
        if "lightning__Tab" in meta["targets"] and tab_api:
            content = render_lwc_tab_spec(meta, tab_api, cfg)
        elif "lightning__RecordPage" in meta["targets"] and meta["objects"]:
            content = render_lwc_record_spec(meta, meta["objects"][0])
        else:
            content = render_generic_lwc_spec(meta)
        spec_name = f"{slugify(lwc_name)}.spec.js"
        specs[spec_name] = content
        plan["lwcs"].append({"name": lwc_name, "spec": f"generated/{spec_name}"})

    if args.json:
        plan["generatedSpecs"] = list(specs.keys())
        print(json.dumps(plan, indent=2))
        return 0

    if not specs:
        print("No LWC or Apex UI changes detected for Playwright generation.")
        print("Changed files:", len(files))
        return 0

    print("Generation plan:")
    for name in specs:
        print(f"  e2e/generated/{name}")

    if args.write:
        generated_dir.mkdir(parents=True, exist_ok=True)
        for name, content in specs.items():
            out = generated_dir / name
            out.write_text(content, encoding="utf-8")
            print(f"Wrote {out}")
        manifest = generated_dir / "manifest.json"
        manifest.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
