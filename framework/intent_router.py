"""Rule-based intent routing for orchestrator (works without API key)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from agents_registry import AGENTS, INTENT_TO_TEAMS

_JIRA_KEY = re.compile(r"SFDCLQ-\d+", re.I)


def classify_intent(user_input: str) -> Tuple[str, List[str], List[str]]:
    """
    Returns (intent_key, team_pipeline, agent_ids).
    team_pipeline = ordered LangGraph nodes to run.
    """
    text = user_input.lower()
    agent_ids: List[str] = []

    # Score agents by keyword hits
    for agent in AGENTS:
        if agent["id"] == "orchestrator":
            continue
        for kw in agent.get("intents", []):
            if kw == "*":
                continue
            if kw in text:
                agent_ids.append(agent["id"])
                break

    if _JIRA_KEY.search(user_input):
        if "jira-analyst" not in agent_ids:
            agent_ids.insert(0, "jira-analyst")

    # Determine pipeline
    if any(w in text for w in ("train", "refresh kb", "update knowledge", "swarm kb")):
        intent = "kb_refresh"
    elif any(w in text for w in ("test", "qa", "playwright", "regression", "e2e")):
        intent = "test"
    elif any(w in text for w in ("document", "explain", "deep dive", "html")):
        intent = "document"
    elif any(w in text for w in ("design", "mockup", "architecture", "blueprint", "framework")):
        intent = "design"
    elif any(w in text for w in ("jira", "story", "epic", "requirements")) and not any(
        w in text for w in ("implement", "build", "code", "deploy", "develop", "dev work", "dev ")
    ):
        intent = "jira_only"
    elif any(
        w in text
        for w in (
            "implement",
            "build",
            "develop",
            "fix",
            "add",
            "create",
            "pantheon",
            "bundle",
            "cpq",
            "apex",
            "lwc",
        )
    ):
        intent = "implement"
    else:
        intent = "full_delivery"

    pipeline = list(INTENT_TO_TEAMS.get(intent, INTENT_TO_TEAMS["full_delivery"]))

  # Always end with finalize path through training on full runs
    if intent in ("implement", "full_delivery", "design") and "training_team" not in pipeline:
        pipeline.append("training_team")

    return intent, pipeline, list(dict.fromkeys(agent_ids))


def summarize_plan(user_input: str, intent: str, pipeline: List[str], agent_ids: List[str]) -> str:
    lines = [
        f"**User request:** {user_input[:500]}",
        f"**Intent:** {intent}",
        f"**Pipeline:** {' → '.join(pipeline)}",
        "",
        "**Assigned agents:**",
    ]
    for aid in agent_ids:
        agent = next((a for a in AGENTS if a["id"] == aid), None)
        if agent:
            lines.append(f"- {agent['name']} (`{agent.get('cursor_agent', 'local')}`) — {agent['description']}")
    if not agent_ids:
        lines.append("- Orchestrator will use default team agents for pipeline")
    return "\n".join(lines)
