"""LangChain tools used by swarm research agents."""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from config import CODEBASE_NOTES_DIR, SFDC_NOTES_DIR, TOPICS


@tool
def list_topics() -> str:
    """List all knowledge-base topic keys and titles."""
    return "\n".join(f"{t['key']}: {t['title']}" for t in TOPICS)


@tool
def write_knowledge_note(topic_key: str, markdown: str) -> str:
    """Write a Markdown knowledge note for a topic key to the knowledge base."""
    from teams import CODEBASE_TOPICS

    codebase = next((t for t in CODEBASE_TOPICS if t["key"] == topic_key), None)
    if codebase:
        path = CODEBASE_NOTES_DIR / f"{topic_key}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return f"written: {path}"

    topic = next((t for t in TOPICS if t["key"] == topic_key), None)
    if not topic:
        return f"error: unknown topic {topic_key}"
    path = SFDC_NOTES_DIR / f"{topic_key}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return f"written: {path}"


@tool
def read_knowledge_note(topic_key: str) -> str:
    """Read an existing knowledge note if present."""
    path = CODEBASE_NOTES_DIR / f"{topic_key}.md"
    if not path.exists():
        path = SFDC_NOTES_DIR / f"{topic_key}.md"
    if not path.exists():
        return f"missing: {topic_key}"
    return path.read_text(encoding="utf-8")[:8000]


def note_template(title: str, docs_read: int) -> str:
    return (
        f"# {title}\n"
        f"_Last refreshed via SFDC Knowledge Swarm (LangChain) · Sources: {docs_read} docs_\n"
        "## Summary\n"
        "## Key concepts\n"
        "## Best practices / guardrails\n"
        "## Gotchas & limits\n"
        "## Code / config patterns\n"
        "## Sources\n"
    )
