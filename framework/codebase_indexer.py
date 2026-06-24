"""Static codebase scanner — builds knowledge-base notes from force-app (no API key)."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from config import CODEBASE_NOTES_DIR, FLEET_DIR, REPO_ROOT, ensure_dirs, get_runtime
from project_context import adapt_glob_pattern
from teams import CODEBASE_TOPICS

MAX_LIST = 80
MAX_GREP_HITS = 40
CLASS_RE = re.compile(r"^\s*(?:public|global|private|protected)\s+(?:with\s+sharing\s+)?class\s+(\w+)", re.M)
TRIGGER_RE = re.compile(r"^\s*trigger\s+(\w+)\s+on\s+(\w+)", re.M | re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _glob_files(patterns: List[str]) -> List[Path]:
    ctx = get_runtime()
    seen: Set[Path] = set()
    for pattern in patterns:
        adapted = adapt_glob_pattern(pattern, ctx)
        for path in REPO_ROOT.glob(adapted):
            if path.is_file() and path not in seen:
                seen.add(path)
    return sorted(seen, key=lambda p: str(p).lower())


def _grep_in_files(files: List[Path], terms: List[str]) -> List[Tuple[str, int, str]]:
    hits: List[Tuple[str, int, str]] = []
    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(t.lower() in line.lower() for t in terms):
                hits.append((str(fpath.relative_to(REPO_ROOT)), i, line.strip()[:140]))
                if len(hits) >= MAX_GREP_HITS:
                    return hits
    return hits


def _summarize_apex(files: List[Path]) -> Dict[str, Any]:
    classes: List[str] = []
    for fpath in files:
        if fpath.suffix != ".cls":
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in CLASS_RE.finditer(text):
            classes.append(m.group(1))
    prefixes = Counter()
    for name in classes:
        if "_" in name:
            prefixes[name.split("_")[0]] += 1
        else:
            prefixes[name[:3]] += 1
    top_prefixes = prefixes.most_common(12)
    return {"class_count": len(classes), "top_prefixes": top_prefixes, "sample_classes": classes[:30]}


def _summarize_triggers(files: List[Path]) -> List[str]:
    rows: List[str] = []
    for fpath in files:
        if fpath.suffix != ".trigger":
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in TRIGGER_RE.finditer(text):
            rows.append(f"{m.group(2)} → {m.group(1)}")
    return rows[:MAX_LIST]


def build_topic_note(topic: Dict[str, Any]) -> Dict[str, Any]:
    ensure_dirs()
    files = _glob_files(topic.get("glob", []))
    grep_terms = topic.get("grep", [])
    grep_hits = _grep_in_files(files, grep_terms) if grep_terms else []

    rel_paths = [str(p.relative_to(REPO_ROOT)) for p in files[:MAX_LIST]]
    extra = len(files) - len(rel_paths)

    apex_summary = _summarize_apex(files) if any(p.suffix == ".cls" for p in files) else None
    trigger_rows = _summarize_triggers(files) if any(p.suffix == ".trigger" for p in files) else []

    ctx = get_runtime()
    lines = [
        f"# {topic['title']}",
        f"_Codebase scan · team: {topic.get('team', '')} · {_now()}_",
        "",
        "## Salesforce context",
        f"- **Project:** `{ctx.get('projectName')}`",
        f"- **Target org:** `{ctx.get('targetOrgAlias')}` ({ctx.get('targetOrgSource')})",
        f"- **Source path:** `{ctx.get('sourcePath')}`",
        f"- **Deploy:** `{ctx.get('deployCommandTemplate')}`",
        "",
        "## Focus",
        topic.get("focus", ""),
        "",
        "## Inventory",
        f"- **Files matched:** {len(files)}",
        f"- **Repo root:** `{REPO_ROOT}`",
        "",
        "## File sample",
    ]
    for rp in rel_paths:
        lines.append(f"- `{rp}`")
    if extra > 0:
        lines.append(f"- _…and {extra} more_")

    if apex_summary:
        lines.extend(["", "## Apex summary", f"- Classes in sample: {apex_summary['class_count']}"])
        if apex_summary["top_prefixes"]:
            lines.append("- Top prefixes:")
            for pref, cnt in apex_summary["top_prefixes"]:
                lines.append(f"  - `{pref}_*` — {cnt}")

    if trigger_rows:
        lines.extend(["", "## Triggers", "| Object | Trigger |", "| --- | --- |"])
        for row in trigger_rows[:25]:
            obj, trig = row.split(" → ", 1)
            lines.append(f"| {obj} | {trig} |")

    if grep_hits:
        lines.extend(["", "## Keyword hits", "| File | Line | Snippet |", "| --- | --- | --- |"])
        for path, line_no, snippet in grep_hits[:25]:
            esc = snippet.replace("|", "\\|")
            lines.append(f"| `{path}` | {line_no} | {esc} |")

    lines.extend(
        [
            "",
            "## Agent routing",
            f"- **Team:** `{topic.get('team')}`",
            "- Re-run: `python3 run.py dev-once --topics " + topic["key"] + "`",
            "",
            "## Sources",
            "- Local package static scan (no API key)",
        ]
    )

    markdown = "\n".join(lines) + "\n"
    out_path = CODEBASE_NOTES_DIR / f"{topic['key']}.md"
    out_path.write_text(markdown, encoding="utf-8")

    return {
        "key": topic["key"],
        "title": topic["title"],
        "team": topic.get("team"),
        "status": "written",
        "note_path": str(out_path),
        "files_matched": len(files),
        "grep_hits": len(grep_hits),
        "summary": f"{len(files)} files indexed",
    }


def scan_all_topics(topic_keys: List[str] | None = None) -> List[Dict[str, Any]]:
    selected = CODEBASE_TOPICS
    if topic_keys:
        selected = [t for t in CODEBASE_TOPICS if t["key"] in topic_keys]
    return [build_topic_note(t) for t in selected]


def kb_topic_status() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for topic in CODEBASE_TOPICS:
        path = CODEBASE_NOTES_DIR / f"{topic['key']}.md"
        status = "missing"
        mtime = None
        size = 0
        if path.exists():
            status = "written"
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            size = path.stat().st_size
        rows.append(
            {
                "key": topic["key"],
                "title": topic["title"],
                "team": topic.get("team"),
                "category": "codebase",
                "status": status,
                "note_path": str(path),
                "mtime": mtime,
                "bytes": size,
            }
        )
    return rows
