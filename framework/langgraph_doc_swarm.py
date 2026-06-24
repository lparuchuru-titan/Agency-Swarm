"""LangGraph orchestration for public Salesforce docs research swarm."""
from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from config import GLOBAL_SFDC_NOTES_DIR, SWARM_MODEL, TOPICS, ensure_dirs
from fleet_hooks import finalize_run, init_run, update_agent
from sources import gather_topic_sources
from tools import list_topics, note_template, read_knowledge_note, write_knowledge_note


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class DocSwarmState(TypedDict):
    run_id: str
    force: bool
    topic_keys: List[str]
    pending: List[str]
    phase: str
    results: Annotated[List[Dict[str, Any]], add]


def _research_prompt(topic: Dict[str, Any], source_bundle: Dict[str, Any]) -> str:
    template = note_template(topic["title"], int(source_bundle.get("docs_read", 0)))
    return (
        "You are a Salesforce technical-architect researcher. "
        "Ground answers ONLY in the provided source excerpts.\n\n"
        f"Topic key: {topic['key']}\nTitle: {topic['title']}\nFocus: {topic['focus']}\n\n"
        f"Sources:\n{source_bundle.get('context', '(none)')}\n\n"
        f"Write Markdown via write_knowledge_note:\n{template}\n"
        "Reply JSON: {\"status\":\"written|partial|error\",\"summary\":\"...\"}"
    )


def plan_docs(state: DocSwarmState) -> Dict[str, Any]:
    keys = state["topic_keys"] or [t["key"] for t in TOPICS]
    topics = [t for t in TOPICS if t["key"] in keys]
    init_run(
        state["run_id"],
        ["salesforce-dev"],
        [{"key": t["key"], "title": t["title"], "team": "salesforce-dev"} for t in topics],
        workflow="sfdc-knowledge-swarm",
        source="langgraph-doc-swarm",
    )
    return {"pending": keys, "phase": "planned", "results": []}


def research_next(state: DocSwarmState) -> Dict[str, Any]:
    if not state["pending"]:
        return {"results": []}

    topic_key = state["pending"][0]
    remaining = state["pending"][1:]
    topic = next((t for t in TOPICS if t["key"] == topic_key), None)
    if not topic:
        return {"pending": remaining, "results": [{"key": topic_key, "status": "error", "summary": "unknown"}]}

    note_path = GLOBAL_SFDC_NOTES_DIR / f"{topic_key}.md"
    if note_path.exists() and not state["force"]:
        outcome = {
            "key": topic_key,
            "title": topic["title"],
            "status": "skipped",
            "note_path": str(note_path),
            "summary": "exists",
        }
        update_agent(state["run_id"], topic_key, {"status": "skipped", "ended_at": _now()})
        return {"pending": remaining, "results": [outcome]}

    update_agent(state["run_id"], topic_key, {"status": "running", "started_at": _now(), "phase": "Research"})

    try:
        sources = gather_topic_sources(topic_key)
        model = ChatAnthropic(model=SWARM_MODEL, temperature=0, max_tokens=4096)
        agent = create_react_agent(model, [list_topics, write_knowledge_note, read_knowledge_note])
        result = agent.invoke({"messages": [HumanMessage(content=_research_prompt(topic, sources))]})
        text = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and msg.content:
                text = str(msg.content)
                break
        status = "written"
        if "partial" in text.lower():
            status = "partial"
        if "error" in text.lower() and "written" not in text.lower():
            status = "error"
        outcome = {
            "key": topic_key,
            "title": topic["title"],
            "status": status,
            "note_path": str(note_path),
            "docs_read": sources.get("docs_read", 0),
            "summary": text[:500],
        }
        update_agent(
            state["run_id"],
            topic_key,
            {"status": status, "ended_at": _now(), "summary": outcome["summary"], "note_path": str(note_path)},
        )
    except Exception as exc:  # noqa: BLE001
        outcome = {"key": topic_key, "title": topic["title"], "status": "error", "summary": str(exc)}
        update_agent(state["run_id"], topic_key, {"status": "error", "ended_at": _now(), "summary": str(exc)})

    return {"pending": remaining, "results": [outcome]}


def route_research(state: DocSwarmState) -> str:
    return "research" if state.get("pending") else "index"


def index_docs(state: DocSwarmState) -> Dict[str, Any]:
    from swarm import regenerate_index

    regenerate_index(state["results"])
    finalize_run(state["run_id"], state["results"])
    return {"phase": "complete"}


def build_doc_swarm_graph():
    graph = StateGraph(DocSwarmState)
    graph.add_node("plan", plan_docs)
    graph.add_node("research", research_next)
    graph.add_node("index", index_docs)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_conditional_edges("research", route_research, {"research": "research", "index": "index"})
    graph.add_edge("index", END)
    return graph.compile()


def run_langgraph_doc_swarm(
    topic_keys: Optional[List[str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    ensure_dirs()
    keys = topic_keys or [t["key"] for t in TOPICS]
    run_id = uuid.uuid4().hex[:12]
    app = build_doc_swarm_graph()
    final = app.invoke(
        {
            "run_id": run_id,
            "force": force,
            "topic_keys": keys,
            "pending": keys,
            "phase": "start",
            "results": [],
        }
    )
    return {"run_id": run_id, "orchestrator": "langgraph", "results": final.get("results", [])}
