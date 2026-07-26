"""
Intelligent intent router — builds its prompt dynamically from the agent
registry and skill files, then calls the Cursor SDK to make a genuine
routing decision based on what the swarm actually knows how to do.

No hardcoded keyword lists. The router reads its own capabilities and
reasons from them — the same way a senior developer would assign work.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents_registry import AGENTS, INTENT_TO_TEAMS

_JIRA_KEY = re.compile(r"[A-Z]+-\d+", re.I)
_NODE = shutil.which("node") or "node"
_RUNNER = str(Path(__file__).parent / "cursor_agent_runner.js")


# ── Build dynamic routing context from the registry ────────────────────────

def _build_agent_menu() -> str:
    """Summarise every agent — id, team, description, intents — for the router."""
    lines = ["Available agents and what they do:\n"]
    seen_teams: Dict[str, List[str]] = {}
    for a in AGENTS:
        tid = a.get("team", "other")
        if tid not in seen_teams:
            seen_teams[tid] = []
        seen_teams[tid].append(
            f"  - **{a['id']}** ({a.get('name', a['id'])}): {a.get('description', '')}"
        )
    for team, items in seen_teams.items():
        lines.append(f"\nTeam **{team}**:")
        lines.extend(items)
    return "\n".join(lines)


def _build_pipeline_menu() -> str:
    """List every pipeline option with what it runs and when to use it."""
    desc = {
        "discover":      "research + documentation. Use when: analyze/audit/understand/scan/review what already exists. NO building. NO QA.",
        "document":      "documentation only. Use when: explain/walk through/teach/describe how something works. NO building. NO QA.",
        "design":        "requirements + research + design. Use when: architecture, blueprints, 'improve X', 'how should we build Y', 'contest to find the best approach'. NO building. NO QA.",
        "review":        "code review gate only. Use when: 'review this PR/diff/change', 'is this ready to deploy?'. NO building.",
        "test":          "QA only. Use when: 'run tests', 'write test cases', 'playwright E2E'. NO building.",
        "jira_only":     "requirements + documentation. Use when: reading a Jira story or extracting acceptance criteria. NO building.",
        "implement":     "requirements + research + development + admin + QA + docs. Use ONLY when explicitly building new code/metadata: 'implement', 'build', 'create', 'write Apex/LWC', 'add a trigger'.",
        "full_delivery": "all teams. Use ONLY when the request explicitly covers requirements, design, implementation, testing, and promotion together.",
        "kb_refresh":    "training only. Use when: 'refresh KB', 'update skills', 'retrain agent'.",
    }
    lines = ["\nAvailable pipelines:\n"]
    for key, d in desc.items():
        lines.append(f"- **{key}**: {d}")
    return "\n".join(lines)


def _read_skill_summaries(max_chars: int = 2000) -> str:
    """Read the first 8 lines of each SKILL.md to give the router context."""
    summaries: List[str] = []
    for base in [
        Path.home() / ".cursor" / "skills",
        Path.home() / ".claude" / "skills",
    ]:
        if not base.is_dir():
            continue
        for skill_dir in sorted(base.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()[:8]
                text = " ".join(l.strip() for l in lines if l.strip())[:200]
                summaries.append(f"  - **{skill_dir.name}**: {text}")
        break  # only read first base that exists
    return "Skill summaries:\n" + "\n".join(summaries[:12]) if summaries else ""


def _router_prompt(user_input: str) -> str:
    """Build the full routing prompt from live registry data."""
    agent_menu = _build_agent_menu()
    pipeline_menu = _build_pipeline_menu()
    skill_summaries = _read_skill_summaries()

    return f"""You are the routing brain of a Salesforce AI agent swarm.
Your job: read the user's request, understand what TYPE of work it is,
and select the MINIMUM pipeline of teams needed to do it well.

Golden rules:
1. Never add QA unless the user explicitly asks for tests or deploying code.
2. Never add development unless the user explicitly asks to build/create/implement.
3. 'analyze', 'audit', 'explain', 'improve', 'review', 'contest', 'understand' → discover or design.
4. The more specific the implementation request, the more teams. Generic exploration = fewer teams.
5. Pick the NARROWEST correct pipeline, not the broadest.

{agent_menu}

{pipeline_menu}

{skill_summaries}

User request:
\"\"\"{user_input}\"\"\"

Return ONLY a JSON object (no other text):
{{
  "intent": "<one of the pipeline keys above>",
  "pipeline": ["<team_id>_team", ...],
  "agent_ids": ["<agent-id>", ...],
  "reason": "<one sentence explaining why you chose this pipeline and NOT a broader one>"
}}

Valid pipeline team IDs: requirements_team, research_team, design_team,
development_team, admin_team, review_team, qa_team, documentation_team, training_team."""


# ── Routing via Cursor SDK ─────────────────────────────────────────────────

def _route_with_cursor_sdk(user_input: str) -> Optional[Tuple[str, List[str], List[str], str, str]]:
    """
    Build a dynamic prompt from the live registry, call Cursor SDK to route.
    Returns None on failure so caller falls back to rules.
    """
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key:
        return None

    prompt = _router_prompt(user_input)

    try:
        result = subprocess.run(
            [_NODE, _RUNNER,
             "--api-key", api_key,
             "--model", "auto",
             "--cwd", str(Path(__file__).parent),
             "--agent-id", "intent-router",
             "--prompt", prompt],
            capture_output=True, text=True, timeout=45,
        )
        output_text = ""
        for line in result.stdout.splitlines():
            try:
                ev = json.loads(line)
                if ev.get("type") == "text":
                    output_text += ev.get("text", "")
                elif ev.get("type") == "done":
                    output_text = ev.get("result", output_text)
            except Exception:  # noqa: BLE001
                pass

        match = re.search(r"\{[\s\S]*?\}", output_text)
        if not match:
            return None
        data = json.loads(match.group())

        intent = str(data.get("intent", "full_delivery"))
        reason = str(data.get("reason", ""))

        # Sanitise pipeline — only accept known team nodes
        valid_nodes = {
            "requirements_team", "research_team", "design_team",
            "development_team", "admin_team", "review_team",
            "qa_team", "documentation_team", "training_team",
        }
        pipeline = [n for n in data.get("pipeline", []) if n in valid_nodes]
        if not pipeline:
            pipeline = list(INTENT_TO_TEAMS.get(intent, INTENT_TO_TEAMS["full_delivery"]))

        valid_agent_ids = {a["id"] for a in AGENTS}
        agent_ids = [a for a in data.get("agent_ids", []) if a in valid_agent_ids]

        extra = f"**Router:** Cursor LLM · {reason}" if reason else "**Router:** Cursor LLM"
        return intent, pipeline, agent_ids, extra, "llm"

    except Exception:  # noqa: BLE001
        return None


# ── Simple fallback rules (no regex fragility) ─────────────────────────────

_FALLBACK_RULES = [
    # (pattern, intent) — checked in order, first match wins
    (r"refresh.?kb|update.?knowledge|skill.?refresh",           "kb_refresh"),
    (r"\baudit\b|\bscan\b|\bassess\b|\banalyze\b|\banalyse\b",  "discover"),
    (r"\btest\b|\bplaywright\b|\be2e\b|regression.?test",       "test"),
    (r"\breview\b.*(pr|code|diff|change)",                      "review"),
    (r"\bexplain\b|\bdescribe\b|\boverview\b|\bwhat.?is\b",     "document"),
    (r"\bimprove\b|\benhance\b|\bcontest\b|\bmake.*better\b",   "design"),
    (r"\bdesign\b|\barchitect\b|\bblueprint\b|\bframework\b",   "design"),
    (r"\bimplement\b|\bbuild\b|\bdevelop\b|\bcreate\b",         "implement"),
    (r"write.*apex|write.*lwc|add.*trigger|add.*field",         "implement"),
    (r"\bjira\b|[A-Z][A-Z0-9]+-\d+",                             "jira_only"),
]


def _fallback_classify(user_input: str) -> Tuple[str, List[str], List[str]]:
    text = user_input.lower()
    intent = "full_delivery"
    for pattern, mapped_intent in _FALLBACK_RULES:
        if re.search(pattern, text):
            intent = mapped_intent
            break

    if _JIRA_KEY.search(user_input) and intent == "full_delivery":
        intent = "jira_only"

    pipeline = list(INTENT_TO_TEAMS.get(intent, INTENT_TO_TEAMS["full_delivery"]))

    # Score agents by keyword overlap
    agent_ids: List[str] = []
    for agent in AGENTS:
        if agent["id"] == "orchestrator":
            continue
        for kw in agent.get("intents", []):
            if kw != "*" and kw in text:
                agent_ids.append(agent["id"])
                break

    return intent, pipeline, list(dict.fromkeys(agent_ids))


# ── Public interface ────────────────────────────────────────────────────────

def classify_intent(user_input: str) -> Tuple[str, List[str], List[str]]:
    """Fallback rules (no API key path)."""
    return _fallback_classify(user_input)


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
        lines.append("- Orchestrator will use default team agents for this pipeline")
    return "\n".join(lines)
