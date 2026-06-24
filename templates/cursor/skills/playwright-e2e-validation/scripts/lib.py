#!/usr/bin/env python3
"""Shared helpers for Playwright E2E validation skill."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET


def find_project_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    for directory in [start, *start.parents]:
        if (directory / "sfdx-project.json").exists():
            return directory
        if (directory / "package.json").exists() and (directory / "playwright.config.js").exists():
            return directory
    raise FileNotFoundError("No Salesforce or Playwright project root found.")


def find_config(root: Path) -> Path | None:
    for rel in (
        ".cursor/sfdc-project/config.json",
        ".cursor/playwright-e2e/config.json",
        ".playwright-e2e/config.json",
    ):
        candidate = root / rel
        if candidate.exists():
            return candidate
    return None


def load_config(root: Path | None = None) -> dict:
    root = root or find_project_root()
    shared = Path.home() / ".cursor" / "skills" / "_shared"
    import sys
    sys.path.insert(0, str(shared))
    from sfdc_context import resolve_context  # noqa: WPS433

    ctx = resolve_context(root)
    cfg_path = find_config(root)
    dot = {}
    if cfg_path and cfg_path.exists():
        dot = json.loads(cfg_path.read_text(encoding="utf-8"))

    defaults = {
        "projectRoot": ctx["projectRoot"],
        "e2eDir": dot.get("e2eDir", "e2e"),
        "sourcePath": ctx["sourcePath"],
        "targetOrgAlias": ctx.get("targetOrgAlias"),
        "instanceUrl": ctx.get("instanceUrl"),
        "defaultTabPrefix": "/lightning/n/",
        "runApexTests": dot.get("runApexTests", True),
        "runLwcJest": dot.get("runLwcJest", True),
        "runPlaywright": dot.get("runPlaywright", True),
        "_context": ctx,
    }
    return defaults


def _default_source_path(root: Path) -> str:
    sfdx = root / "sfdx-project.json"
    if sfdx.exists():
        data = json.loads(sfdx.read_text(encoding="utf-8"))
        dirs = data.get("packageDirectories", [])
        if dirs:
            return dirs[0].get("path", "force-app") + "/main/default"
    if (root / "Master/main/default").exists():
        return "Master/main/default"
    if (root / "force-app/main/default").exists():
        return "force-app/main/default"
    return "force-app/main/default"


def git_changed_files(root: Path, source_path: str) -> list[str]:
    patterns = [
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "status", "--porcelain", source_path],
    ]
    files: set[str] = set()
    for cmd in patterns:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if cmd[-1] == source_path and len(line) > 3:
                path = line[3:].strip()
            else:
                path = line
            if path.startswith(source_path) or "/lwc/" in path or "/classes/" in path:
                files.add(path.replace("\\", "/"))
    return sorted(files)


def lwc_name_from_path(path: str) -> str | None:
    match = re.search(r"/lwc/([^/]+)/", path.replace("\\", "/"))
    return match.group(1) if match else None


def apex_class_from_path(path: str) -> str | None:
    match = re.search(r"/classes/([^/]+)\.cls", path.replace("\\", "/"))
    if not match:
        return None
    name = match.group(1)
    if name.endswith("Test"):
        return None
    return name


def apex_test_class(class_name: str) -> str:
    return f"{class_name}Test"


def read_lwc_meta(source_root: Path, lwc_name: str) -> dict:
    meta_path = source_root / "lwc" / lwc_name / f"{lwc_name}.js-meta.xml"
    if not meta_path.exists():
        return {"name": lwc_name, "targets": [], "objects": []}
    root = ET.parse(meta_path).getroot()
    ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
    targets = [el.text for el in root.iter(f"{ns}target") if el.text]
    objects = [el.text for el in root.iter(f"{ns}objects") if el.text]
    # objects are nested under object elements
    objects = [el.text for el in root.iter(f"{ns}object") if el.text]
    label = root.find(f".//{ns}masterLabel")
    return {
        "name": lwc_name,
        "label": label.text if label is not None and label.text else lwc_name,
        "targets": targets,
        "objects": objects,
    }


def find_tab_for_lwc(source_root: Path, lwc_meta: dict) -> str | None:
    tabs_dir = source_root / "tabs"
    if not tabs_dir.exists():
        return None
    lwc_slug = slugify(lwc_meta.get("label", lwc_meta["name"]))
    for tab_file in tabs_dir.glob("*.tab-meta.xml"):
        api = tab_file.stem.replace(".tab-meta", "")
        if slugify(api) in lwc_slug or slugify(lwc_meta["name"]) in slugify(api):
            return api
        try:
            root = ET.parse(tab_file).getroot()
            label_el = root.find(".//{*}label")
            if label_el is not None and label_el.text:
                if slugify(label_el.text) in lwc_slug or slugify(lwc_meta["name"]) in slugify(label_el.text):
                    return api
        except ET.ParseError:
            continue
    return None


def kebab_lwc_tag(lwc_name: str) -> str:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", lwc_name)
    return "c-" + parts.lower().replace("_", "-")


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower())
    return re.sub(r"-{2,}", "-", value).strip("-")
