"""LangGraph doc swarm — public Salesforce docs research."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import GLOBAL_SFDC_NOTES_DIR, KB_DIR, SFDC_NOTES_DIR, TOPICS, ensure_dirs


def start_run(topic_keys: Optional[List[str]] = None, force: bool = False) -> Dict[str, Any]:
    """Run public-docs swarm via LangGraph (requires ANTHROPIC_API_KEY)."""
    ensure_dirs()
    from langgraph_doc_swarm import run_langgraph_doc_swarm

    return run_langgraph_doc_swarm(topic_keys=topic_keys, force=force)


def regenerate_index(results: List[Dict[str, Any]]) -> None:
    from config import KB_DIR

    lines = [
        "# Salesforce Knowledge Base — Index",
        "",
        "_Built by SFDC Knowledge Swarm (LangChain)_",
        "",
        "| Topic | Note | Status |",
        "| --- | --- | --- |",
    ]
    status_map = {r["key"]: r.get("status", "present") for r in results}
    for t in TOPICS:
        note = f"sfdc/{t['key']}.md"
        status = status_map.get(t["key"], "present")
        if (GLOBAL_SFDC_NOTES_DIR / f"{t['key']}.md").exists() and status == "present":
            status = "present"
        lines.append(f"| {t['title']} | [{t['key']}]({note}) | {status} |")

    (KB_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
