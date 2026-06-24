"""LLM router with rule-based fallback — video-style router node."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple, Optional

from agents_registry import AGENTS, INTENT_TO_TEAMS
from intent_router import classify_intent, summarize_plan

VALID_TEAM_NODES = frozenset(
    {
        "requirements_team",
        "research_team",
        "design_team",
        "development_team",
        "admin_team",
        "qa_team",
        "documentation_team",
        "training_team",
    }
)

_ROUTER_PROMPT = """You are the router for a Salesforce dev agent swarm.
Given the user request, return JSON only:
{
  "intent": "implement|design|test|document|jira_only|full_delivery|kb_refresh",
  "pipeline": ["requirements_team", "research_team", ...],
  "agent_ids": ["jira-analyst", "apex-developer"],
  "reason": "one sentence"
}

Valid pipeline nodes (order matters): requirements_team, research_team, design_team,
development_team, admin_team, qa_team, documentation_team, training_team.

Rules:
- implement/build/fix/code → include research_team before development_team
- design/mockup only → requirements_team, design_team (optional research_team)
- test/qa only → qa_team, documentation_team
- document only → documentation_team
- jira/requirements only → requirements_team, documentation_team
- kb refresh → training_team only
- Pick agent_ids from specialist list when keywords match (apex, lwc, jira, qa, etc.)
"""


def _sanitize_pipeline(pipeline: List[str]) -> List[str]:
    out: List[str] = []
    for node in pipeline:
        if node in VALID_TEAM_NODES and node not in out:
            out.append(node)
    return out


def _sanitize_agent_ids(agent_ids: List[str]) -> List[str]:
    valid = {a["id"] for a in AGENTS}
    return [a for a in agent_ids if a in valid]


def route_with_llm(user_input: str, run_id: Optional[str] = None) -> Tuple[str, List[str], List[str], str, str]:
    """Returns intent, pipeline, agent_ids, plan_extra_line, router_method."""
    from config import SWARM_MODEL

    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        model = ChatAnthropic(model=SWARM_MODEL, temperature=0, max_tokens=1024)
        msg = model.invoke(
            [
                HumanMessage(content=_ROUTER_PROMPT),
                HumanMessage(content=f"User request:\n{user_input}"),
            ]
        )
        from usage_tracker import record_from_message

        record_from_message("llm-router", SWARM_MODEL, msg, run_id=run_id, note="intent routing")
        text = str(msg.content)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("no JSON in router response")
        data = json.loads(match.group())
        intent = str(data.get("intent", "full_delivery"))
        pipeline = _sanitize_pipeline(list(data.get("pipeline", [])))
        agent_ids = _sanitize_agent_ids(list(data.get("agent_ids", [])))
        reason = str(data.get("reason", ""))

        if not pipeline:
            pipeline = list(INTENT_TO_TEAMS.get(intent, INTENT_TO_TEAMS["full_delivery"]))

        if intent in ("implement", "full_delivery", "design") and "training_team" not in pipeline:
            pipeline.append("training_team")

        extra = f"**Router:** LLM · {reason}" if reason else "**Router:** LLM"
        return intent, pipeline, agent_ids, extra, "llm"
    except Exception as exc:  # noqa: BLE001
        intent, pipeline, agent_ids = classify_intent(user_input)
        return intent, pipeline, agent_ids, f"**Router:** rules (LLM fallback: {exc})", "rules"


def route_user_input(user_input: str, run_id: Optional[str] = None) -> Tuple[str, List[str], List[str], str, str]:
    """LLM when ANTHROPIC_API_KEY set; otherwise rule-based."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return route_with_llm(user_input, run_id=run_id)
    intent, pipeline, agent_ids = classify_intent(user_input)
    return intent, pipeline, agent_ids, "**Router:** rules (no API key)", "rules"


def build_plan(user_input: str, intent: str, pipeline: List[str], agent_ids: List[str], router_line: str) -> str:
    base = summarize_plan(user_input, intent, pipeline, agent_ids)
    return base + "\n\n" + router_line
