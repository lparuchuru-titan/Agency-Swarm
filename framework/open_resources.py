"""Static (zero-token) refresh of open Salesforce documentation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import GLOBAL_SFDC_NOTES_DIR, TOPICS, ensure_dirs
from skill_schedule_config import OPEN_DOC_STATIC_MAX_CHARS, REFRESH_AFTER_DAYS
from sources import gather_topic_sources


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return age > timedelta(days=REFRESH_AFTER_DAYS)


def refresh_open_docs_static(
    topic_keys: Optional[List[str]] = None,
    force: bool = False,
    max_topics: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch public doc URLs and write KB notes without LLM.
    Cost: 0 API tokens (HTTP only).
    """
    ensure_dirs()
    keys = topic_keys or [t["key"] for t in TOPICS]
    if max_topics:
        keys = keys[:max_topics]

    results: List[Dict[str, Any]] = []
    for key in keys:
        topic = next((t for t in TOPICS if t["key"] == key), None)
        if not topic:
            results.append({"key": key, "status": "error", "summary": "unknown topic"})
            continue

        note_path = GLOBAL_SFDC_NOTES_DIR / f"{key}.md"
        if note_path.exists() and not force and not _is_stale(note_path):
            results.append({"key": key, "status": "skipped", "summary": "fresh", "note_path": str(note_path)})
            continue

        bundle = gather_topic_sources(key)
        docs_read = int(bundle.get("docs_read", 0))
        context = str(bundle.get("context", ""))[:OPEN_DOC_STATIC_MAX_CHARS]
        body = [
            f"# {topic['title']}",
            f"_Last refreshed (static open resources · no LLM) · {docs_read} docs · {_now()}_",
            "",
            f"**Focus:** {topic.get('focus', '')}",
            "",
            "## Source excerpts",
            "",
            context or "_No fetchable static content (JS-rendered or empty)._",
            "",
            "## Summary",
            "_Auto-generated excerpt index. Run `skill-refresh --tier open_deep` for LLM synthesis when stale._",
            "",
            "## Sources",
        ]
        for url in topic.get("docs", []):
            body.append(f"- {url}")

        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("\n".join(body) + "\n", encoding="utf-8")
        results.append(
            {
                "key": key,
                "status": "written",
                "summary": f"static · {docs_read} docs",
                "note_path": str(note_path),
                "docs_read": docs_read,
            }
        )

    written = sum(1 for r in results if r["status"] == "written")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    return {
        "tier": "open_light",
        "token_cost": 0,
        "written": written,
        "skipped": skipped,
        "results": results,
    }


def stale_open_topic_keys() -> List[str]:
    stale: List[str] = []
    for topic in TOPICS:
        path = GLOBAL_SFDC_NOTES_DIR / f"{topic['key']}.md"
        if _is_stale(path):
            stale.append(topic["key"])
    return stale
