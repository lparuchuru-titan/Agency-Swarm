"""
LangGraph team nodes — execute agent work via Cursor SDK (Node.js runner).

Each node invokes cursor_agent_runner.js with the agent's skill + task prompt.
Cursor manages the LLM choice; agents run in the repo context (local runtime).

Requires: CURSOR_API_KEY env var (cursor.com/dashboard/integrations)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents_registry import AGENTS, agents_for_team
from config import FLEET_DIR, GLOBAL_SFDC_NOTES_DIR, KB_DIR, REPO_ROOT, get_runtime
from fleet_hooks import append_activity, mark_team_phase, update_agent

FLEET_RUNS = FLEET_DIR / "runs"
_NODE = shutil.which("node") or "node"
_RUNNER = str(Path(__file__).parent / "cursor_agent_runner.js")
_MODEL = os.environ.get("CURSOR_AGENT_MODEL", "auto")


# ── helpers ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(run_id: str) -> Path:
    d = FLEET_RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_artifact(run_id: str, name: str, content: str) -> str:
    path = _run_dir(run_id) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _agents_for_team_ids(team_id: str, assigned: List[str]) -> List[Dict[str, Any]]:
    team_agents = agents_for_team(team_id)
    if not assigned:
        return team_agents
    ids = set(assigned)
    picked = [a for a in AGENTS if a["id"] in ids and a.get("team") == team_id]
    return picked or team_agents


def _read_skill(skill_name: str, max_chars: int = 3500) -> str:
    for base in [
        Path.home() / ".cursor" / "skills",
        Path.home() / ".claude" / "skills",
        REPO_ROOT / ".cursor" / "skills",
    ]:
        path = base / skill_name / "SKILL.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")[:max_chars]
    return f"You are an expert Salesforce {skill_name.replace('-', ' ')} agent."


def _read_kb(topics: List[str], max_chars: int = 4000) -> str:
    chunks: List[str] = []
    for topic in topics[:5]:
        key = topic.split("/")[-1]
        for base in [GLOBAL_SFDC_NOTES_DIR, KB_DIR / "sfdc", KB_DIR / "connected"]:
            path = base / f"{key}.md"
            if path.is_file():
                chunks.append(f"### {key}\n{path.read_text(encoding='utf-8')[:1500]}")
                break
    return "\n\n".join(chunks)[:max_chars]


def _read_prior_artifacts(run_id: str, names: List[str], max_chars: int = 4000) -> str:
    parts: List[str] = []
    run_path = _run_dir(run_id)
    for name in names:
        p = run_path / name
        if p.exists():
            parts.append(f"### {name}\n{p.read_text(encoding='utf-8')[:2000]}")
    return "\n\n".join(parts)[:max_chars]


def _invoke_cursor_agent(
    run_id: str,
    agent_id: str,
    prompt: str,
    timeout: int = 120,
) -> str:
    """
    Invoke the Cursor SDK agent runner (Node.js) and return the response text.
    Streams each line to the fleet activity feed.
    Falls back gracefully if CURSOR_API_KEY is not set.
    """
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key:
        msg = (
            "⚠️  CURSOR_API_KEY not configured. "
            "Set it in FleetView Settings or: export CURSOR_API_KEY=cursor_... "
            "(get yours at cursor.com/dashboard/integrations)"
        )
        append_activity(run_id, agent_id, msg)
        return msg

    cmd = [
        _NODE, _RUNNER,
        "--api-key", api_key,
        "--model", _MODEL,
        "--cwd", str(REPO_ROOT),
        "--prompt", prompt,
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(REPO_ROOT),
        )
        output_text = ""
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            raw_line = raw_line.rstrip()
            if not raw_line:
                continue
            try:
                ev = json.loads(raw_line)
                if ev.get("type") == "text":
                    chunk = ev.get("text", "")
                    output_text += chunk
                    # Stream first line of each chunk to activity
                    first = chunk.strip().split("\n")[0][:200]
                    if first:
                        append_activity(run_id, agent_id, first)
                elif ev.get("type") == "done":
                    output_text = ev.get("result", output_text)
                elif ev.get("type") == "error":
                    append_activity(run_id, agent_id, "❌ " + ev.get("text", ""))
                    return ev.get("text", "Agent error")
            except json.JSONDecodeError:
                append_activity(run_id, agent_id, raw_line[:200])

        proc.wait(timeout=timeout)
        return output_text.strip() or "_Agent completed with no text output._"

    except subprocess.TimeoutExpired:
        proc.kill()
        return "_Agent timed out_"
    except Exception as exc:  # noqa: BLE001
        return f"_Runner error: {exc}_"


# ── team nodes ─────────────────────────────────────────────────────────────

def run_requirements_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "requirements", "gathering requirements", "requirements_team")
    assigned = state.get("assigned_agents", [])
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []

    for agent in _agents_for_team_ids("requirements", assigned):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "requirements"})
        append_activity(run_id, agent["id"], f"Requirements agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["jira-subtask-workflow"])[0])
        jira_keys = re.findall(r"[A-Z]+-\d+", state["user_input"])
        jira_note = f"\nJira tickets detected: {', '.join(jira_keys)}" if jira_keys else ""

        prompt = f"""You are a Salesforce requirements analyst.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Analyse this Salesforce request and produce clear requirements.{jira_note}

REQUEST: {state['user_input']}

Produce:
1. **Goal** — one sentence what this delivers
2. **Acceptance criteria** — 5-8 specific, user-testable bullet points
3. **Scope** — what is in and out of scope
4. **Salesforce metadata needed** — objects, fields, classes, LWC affected
5. **Dependencies** — packages, Jira tickets, external systems
6. **Open questions** — what needs clarification before dev starts"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"requirements-{agent['id']}.md",
            f"# Requirements — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"],
            {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "status": "done", "artifact": path})

    return {"phase": "requirements_done", "artifacts": outcomes}


def run_research_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "research", "KB + codebase research", "research_team")
    agent_id = "kb-researcher"
    update_agent(run_id, agent_id, {"status": "running", "started_at": _now(), "team_id": "research"})
    append_activity(run_id, agent_id, "Researching Salesforce patterns and KB…")
    ctx = get_runtime()

    skill = _read_skill("codebase-explainer")
    kb_ctx = _read_kb(["apex-design-patterns", "security-sharing", "well-architected", "integration-patterns"])

    conn_parts: List[str] = []
    conn = KB_DIR / "connected"
    if conn.is_dir():
        for p in sorted(conn.glob("*.md")):
            if p.name != "INDEX.md":
                conn_parts.append(f"### {p.name}\n{p.read_text(encoding='utf-8')[:1500]}")
    connected_ctx = "\n\n".join(conn_parts)[:3000] or "No connected indexes — run skill-refresh --tier weekly."

    prompt = f"""You are a Salesforce research specialist.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Research what's needed to implement this request.

REQUEST: {state['user_input']}

Relevant knowledge base:
{kb_ctx}

Connected sources (Jira / Confluence / Drive):
{connected_ctx}

Produce a research brief:
1. **Salesforce platform capabilities** — what standard features cover this (no custom code needed)
2. **Custom work required** — what Apex, LWC, Flow, or metadata must be built
3. **Key patterns to use** — trigger handler, service layer, CPQ rules, LWC @wire pattern, etc.
4. **Risks & governor limits** — what could break at scale
5. **Implementation sequence** — in what order to do the work
6. **Verification queries** — SOQL to confirm it worked"""

    output = _invoke_cursor_agent(run_id, agent_id, prompt)
    path = _write_artifact(run_id, "RESEARCH.md",
        f"# Research Brief\n\n**Request:** {state['user_input']}\n\n{output}")
    update_agent(run_id, agent_id, {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
    return {"phase": "research_done", "delivery_path": path,
            "artifacts": [{"agent": agent_id, "artifact": path}]}


def run_design_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "design", "architecture design", "design_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["RESEARCH.md"])

    for agent in _agents_for_team_ids("design", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "design"})
        append_activity(run_id, agent["id"], f"Architect designing: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["sfdc-cta-mentor"])[0])
        kb = _read_kb(["well-architected", "apex-design-patterns", "data-modelling"])

        prompt = f"""You are a Salesforce Technical Architect.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Produce an architecture design for this Salesforce request.

REQUEST: {state['user_input']}

Research context:
{prior or 'No prior research — design from first principles.'}

Architecture knowledge:
{kb}

Produce:
1. **Chosen approach** — the architecture decision and why
2. **Trade-offs** — alternatives considered and why rejected
3. **Data model** — objects, fields, relationships, any schema changes
4. **Automation design** — triggers vs flows, where to use Apex service layer
5. **Security model** — sharing rules, FLS, permission set changes
6. **Integration points** — any external systems, named credentials, callouts
7. **Scalability** — governor limits, LDV, async patterns if needed"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"design-{agent['id']}.md",
            f"# Architecture Design — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "design_done", "artifacts": outcomes}


def run_development_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "development", "implementing", "development_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["RESEARCH.md", "PLAN.md", "design-technical-architect.md"])

    for agent in _agents_for_team_ids("development", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "development"})
        append_activity(run_id, agent["id"], f"Developer implementing: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["advanced-salesforce-developer"])[0])
        kb = _read_kb(["apex-design-patterns", "security-sharing", "governor-limits"])

        prompt = f"""You are an expert Salesforce developer. Write production-ready, bulkified, secure code.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

Key Salesforce knowledge:
{kb}

---

TASK: Implement this Salesforce feature.

REQUEST: {state['user_input']}

Prior research and design:
{prior or 'No prior context — implement following best practices.'}

Produce the full implementation:
1. **sf retrieve command** — exact command to retrieve the metadata you need first
2. **Implementation code** — actual Apex class/trigger, LWC HTML+JS, Flow design, or metadata XML
   - Apex: handler pattern, explicit `with sharing`, CRUD/FLS via stripInaccessible, no SOQL/DML in loops
   - LWC: error handling on all wire calls, no hardcoded IDs
   - Tests: @TestSetup, positive + negative + bulk scenario, assertions with messages
3. **Deploy command** — exact `sf project deploy start` command (user will review and run)
4. **Verification SOQL** — queries to confirm the change worked after deploy

Write actual working code. The developer will copy this directly."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"work-{agent['id']}.md",
            f"# Implementation — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "development_done", "artifacts": outcomes}


def run_admin_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "admin", "metadata & deployment", "admin_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["work-apex-developer.md", "work-codebase-worker.md"])

    for agent in _agents_for_team_ids("admin", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "admin"})
        append_activity(run_id, agent["id"], f"Admin agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["sfdc-metadata-sync"])[0])

        prompt = f"""You are a Salesforce admin and deployment specialist.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Produce metadata and deployment plan for this change.

REQUEST: {state['user_input']}

Implementation produced:
{prior or 'No implementation yet — provide general deployment guidance.'}

Produce:
1. **Metadata to retrieve** — exact `sf project retrieve start --metadata "Type:Name"` commands
2. **FLS updates** — which permission sets need field permissions and the exact `<fieldPermissions>` XML
3. **package.xml** — the deployment manifest entries
4. **Deploy command** — exact `sf project deploy start` command
5. **Manual steps** — what cannot be deployed (data records, Connected App settings, etc.)
6. **Rollback** — how to revert this change if it fails"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"admin-{agent['id']}.md",
            f"# Admin / Deployment Plan — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "admin_done", "artifacts": outcomes}


def run_qa_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "qa", "testing", "qa_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["work-apex-developer.md", "RESEARCH.md"])

    for agent in _agents_for_team_ids("qa", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "qa"})
        append_activity(run_id, agent["id"], f"QA agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["playwright-e2e-validation"])[0])

        prompt = f"""You are a Salesforce QA engineer specialising in Apex tests and E2E testing.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Write a concrete test plan for this Salesforce change.

REQUEST: {state['user_input']}

Implementation context:
{prior or 'No implementation context — write general test approach.'}

Produce:
1. **Apex test class** — complete skeleton with @TestSetup, positive test, negative test, bulk (200-record) test
   Each assert: `System.assertEquals(expected, actual, 'descriptive message')`
2. **SOQL verification** — queries to run post-deploy to confirm data state
3. **Manual UI test steps** — numbered step-by-step in the sandbox
4. **Edge cases** — 5 specific scenarios to test (nulls, zero quantities, max records, etc.)
5. **Playwright stub** — `test('scenario', async ({{page}}) => {{...}})` skeleton if the UI is involved

Write actual code stubs."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"qa-{agent['id']}.md",
            f"# QA Plan — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "qa_done", "artifacts": outcomes}


def run_documentation_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "documentation", "documenting", "documentation_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    run_path = _run_dir(run_id)

    # Gather all work produced
    artifacts = [p for p in sorted(run_path.glob("*.md")) if p.name != "DELIVERY.md"]
    artifact_content = ""
    for p in artifacts:
        artifact_content += f"\n\n### {p.name}\n{p.read_text(encoding='utf-8')[:1500]}"

    for agent in _agents_for_team_ids("documentation", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "documentation"})
        append_activity(run_id, agent["id"], "Writing delivery summary…")

        skill = _read_skill("codebase-explainer")

        prompt = f"""You are a Salesforce technical writer.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Write a concise delivery summary for this completed work.

ORIGINAL REQUEST: {state['user_input']}

Agent outputs produced:
{artifact_content[:5000] or 'No agent output available.'}

Write a delivery document covering:
1. **What was done** — 2-3 sentences summary
2. **Files created/changed** — list of artifacts
3. **How to deploy** — quick step-by-step (retrieve → deploy command → verify)
4. **How to test** — quick smoke test steps
5. **Notes** — any caveats, manual steps, or follow-up required

Keep it to 1 page. This is what the developer reads to know what to do next."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)

        delivery_lines = [
            "# Delivery Summary",
            f"**Request:** {state['user_input']}",
            f"**Run:** {run_id}",
            f"**Org:** {ctx.get('targetOrgAlias','—')}",
            "",
            output,
            "",
            "## Work order files",
        ]
        for p in artifacts:
            delivery_lines.append(f"- `.cursor/swarm/.fleet/runs/{run_id}/{p.name}`")

        delivery_content = "\n".join(delivery_lines)
        delivery_path = _write_artifact(run_id, "DELIVERY.md", delivery_content)

        docs_dir = REPO_ROOT / "docs" / "swarm-deliveries"
        docs_dir.mkdir(parents=True, exist_ok=True)
        dest = docs_dir / f"{run_id}-delivery.md"
        dest.write_text(delivery_content, encoding="utf-8")

        update_agent(run_id, agent["id"],
            {"status": "done", "ended_at": _now(), "summary": str(dest), "note_path": str(dest)})
        outcomes.append({"agent": agent["id"], "artifact": str(dest)})

    return {"phase": "documentation_done", "delivery_path": str(dest), "artifacts": outcomes}


def run_training_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "training", "refreshing skill manifest", "training_team")
    outcomes = []
    for agent in _agents_for_team_ids("training", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "training"})
        try:
            from skill_refresh import run_skill_refresh
            run_skill_refresh("manifest")
            summary = "manifest refreshed"
        except Exception as exc:  # noqa: BLE001
            summary = f"skip: {exc}"
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": summary})
        outcomes.append({"agent": agent["id"], "summary": summary})
    return {"phase": "training_done", "artifacts": outcomes}
