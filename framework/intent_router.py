"""Rule-based intent routing for orchestrator (works without API key)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from agents_registry import AGENTS, INTENT_TO_TEAMS

_JIRA_KEY = re.compile(r"[A-Z]+-\d+", re.I)

# ── Intent word lists ──────────────────────────────────────────────────────
# IMPORTANT: checked IN ORDER — first match wins.
# Read/understand/discover words must come BEFORE build/implement words
# so "analyze the CPQ" → discover, NOT implement.

_DISCOVER_WORDS = (
    "analyze", "analyse", "audit", "scan", "assess", "understand",
    "health check", "security check", "technical debt", "org health",
    "reverse engineer", "document this org", "what exists",
)
_DOCUMENT_WORDS = (
    "document", "explain", "deep dive", "how does", "what is",
    "walk me through", "describe", "teach", "overview", "architecture overview",
    "write docs", "html", "give me docs", "give me documentation",
)
_DESIGN_WORDS = (
    "design", "mockup", "blueprint", "trade-off", "architect", "framework",
)
_TEST_WORDS = (
    "test", "playwright", "regression", "e2e", "qa only",
)
_REVIEW_WORDS = (
    "review", "pr review", "code review", "approve", "ready to deploy",
)
_KB_WORDS = (
    "refresh kb", "update knowledge", "swarm kb", "skill refresh",
)
_JIRA_ONLY_WORDS = (
    "jira", "story", "epic", "requirements", "acceptance criteria",
)
# Only triggers implement when these stand ALONE — NOT "analyze the cpq"
_IMPLEMENT_WORDS = (
    "implement", "build", "develop", "create",
    "write apex", "write lwc", "write a trigger", "write a class",
    "add a trigger", "add a field", "add a class",
    "fix the bug", "scaffold", "refactor",
    # Note: "deploy", "code", "make" removed — too generic, cause false positives
)
# Action-verbs that cancel out technology mentions for implement
_ANALYSIS_VERBS = (
    "analyze", "analyse", "explain", "describe", "document", "audit",
    "scan", "understand", "review", "what is", "how does", "show me",
    "give me", "walk", "teach", "overview", "deep dive",
)


def _has(text: str, words: tuple) -> bool:
    return any(w in text for w in words)


def classify_intent(user_input: str) -> Tuple[str, List[str], List[str]]:
    """
    Returns (intent_key, team_pipeline, agent_ids).
    Checks READ/UNDERSTAND intents first so 'analyze the CPQ'
    never triggers a full implementation pipeline.
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

    # ── Intent classification (order matters) ──────────────────────────────
    if _has(text, _KB_WORDS):
        intent = "kb_refresh"

    # 1. Discover / audit (read-only analysis — no code, no QA)
    elif _has(text, _DISCOVER_WORDS):
        intent = "discover"

    # 2. Pure QA/test request
    elif _has(text, _TEST_WORDS) and not _has(text, _IMPLEMENT_WORDS):
        intent = "test"

    # 3. PR / code review
    elif _has(text, _REVIEW_WORDS) and not _has(text, _IMPLEMENT_WORDS):
        intent = "review"

    # 4. Documentation / explanation — no building, no QA
    elif _has(text, _DOCUMENT_WORDS):
        intent = "document"

    # 5. Architecture / design only
    elif _has(text, _DESIGN_WORDS) and not _has(text, _IMPLEMENT_WORDS):
        intent = "design"

    # 6. Jira/requirements only (no build keywords)
    elif _has(text, _JIRA_ONLY_WORDS) and not _has(text, _IMPLEMENT_WORDS):
        intent = "jira_only"

    # 7. Explicit implement/build request
    elif _has(text, _IMPLEMENT_WORDS):
        intent = "implement"

    # 7b. "write" + technology = implement
    elif "write" in text and any(
        t in text for t in ("apex", "lwc", "trigger", "class", "component", "flow")
    ):
        intent = "implement"

    # 8. Technology mentioned but with an analysis verb → document, not implement
    elif _has(text, _ANALYSIS_VERBS) and any(
        t in text for t in ("cpq", "apex", "lwc", "bundle", "billing", "flow", "trigger", "org")
    ):
        intent = "document"

    # 9. Technology mentioned with no clear verb → design (research first)
    elif any(t in text for t in ("cpq", "apex", "lwc", "bundle", "billing", "flow")):
        intent = "design"

    else:
        intent = "full_delivery"

    pipeline = list(INTENT_TO_TEAMS.get(intent, INTENT_TO_TEAMS["full_delivery"]))

    # Training only on full build runs, not on read-only intents
    if intent in ("implement", "full_delivery") and "training_team" not in pipeline:
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
