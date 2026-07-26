"""Agent registry — roles, skills, MCP tools, and training topics for the dev swarm."""
from __future__ import annotations

from typing import Any, Dict, List

# Teams group agents for LangGraph supervisor routing and FleetView columns.
TEAMS: List[Dict[str, Any]] = [
    {
        "id": "orchestrator",
        "name": "Orchestrator",
        "description": "Routes user input to the right agent teams and synthesizes final result",
        "color": "#22d3ee",
    },
    {
        "id": "requirements",
        "name": "Requirements & Research",
        "description": "Jira, Confluence, Drive/Sheets requirement gathering",
        "color": "#f9a8d4",
    },
    {
        "id": "research",
        "name": "Research & RAG",
        "description": "KB, Jira/Confluence indexes, codebase context before implementation",
        "color": "#f472b6",
    },
    {
        "id": "design",
        "name": "Design & Architecture",
        "description": "Technical Architect, UX mockups, framework blueprints",
        "color": "#a78bfa",
    },
    {
        "id": "development",
        "name": "Development Workers",
        "description": "Apex, LWC/UI, codebase-aware implementers",
        "color": "#60a5fa",
    },
    {
        "id": "admin",
        "name": "Salesforce Admin",
        "description": "Metadata, FLS, flows, manifests, promotion",
        "color": "#34d399",
    },
    {
        "id": "review",
        "name": "Code Review",
        "description": "PR/diff review gate before promotion",
        "color": "#f43f5e",
    },
    {
        "id": "qa",
        "name": "QA & Regression",
        "description": "Playwright E2E, Apex tests, data queries, edge cases",
        "color": "#fb923c",
    },
    {
        "id": "documentation",
        "name": "Documentation",
        "description": "Deep-dive change docs, explainers, runbooks",
        "color": "#eab308",
    },
    {
        "id": "training",
        "name": "Agent Training",
        "description": "Refresh knowledge base and agent skills from swarm runs",
        "color": "#94a3b8",
    },
]

AGENTS: List[Dict[str, Any]] = [
    # --- Orchestrator ---
    {
        "id": "orchestrator",
        "name": "Swarm Orchestrator",
        "team": "orchestrator",
        "role": "supervisor",
        "skills": [],
        "cursor_agent": None,
        "intents": ["*"],
        "description": "Analyzes user input and delegates to specialist teams",
    },
    {
        "id": "org-scout",
        "name": "Org Scout",
        "team": "research",
        "role": "research",
        "skills": ["codebase-explainer"],
        "cursor_agent": "codebase-explainer",
        "intents": ["research", "context", "rag", "lookup", "scout", "scan"],
        "kb_topics": ["codebase/*", "project/*"],
        "description": "Scouts the org before the team starts: full metadata scan (22 types), source retrieval, and context packaging for downstream agents",
    },
    {
        "id": "apex-space-reclaimer",
        "name": "Apex Space Reclaimer",
        "team": "research",
        "role": "research",
        "skills": ["apex-space-reclaimer"],
        "cursor_agent": "apex-space-reclaimer",
        "intents": [
            "unused apex",
            "apex space",
            "code size",
            "reclaim apex",
            "dead code",
            "apex limit",
            "free apex",
        ],
        "kb_topics": ["sfdc/governor-limits"],
        "training_topics": ["apex-space-reclaimer"],
        "description": "Read-only analysis of unused/stale Apex to reclaim character-limit capacity (target ≤75% usage)",
    },

    {
        "id": "org-analyst",
        "name": "Org Analyst",
        "team": "research",
        "role": "research",
        "skills": ["org-analyst"],
        "cursor_agent": "org-analyst",
        "intents": ["audit", "org health", "security audit", "technical debt", "release readiness", "health score"],
        "kb_topics": ["sfdc/security-sharing", "sfdc/governor-limits", "sfdc/testing-deployment"],
        "training_topics": ["org-analyst"],
        "description": "Read-only org health, security posture, technical debt, and release-readiness assessments",
    },
    {
        "id": "reverse-engineer",
        "name": "Reverse Engineer",
        "team": "research",
        "role": "research",
        "skills": ["reverse-engineer"],
        "cursor_agent": "reverse-engineer",
        "intents": ["reverse engineer", "brd", "data dictionary", "erd", "onboarding guide", "document org"],
        "kb_topics": ["sfdc/metadata-model", "sfdc/data-modelling", "sfdc/flows-automation"],
        "training_topics": ["reverse-engineer"],
        "description": "Read-only BRD, data dictionary, ERD, automation inventory, and onboarding docs from metadata",
    },
    # --- Requirements ---
    {
        "id": "jira-analyst",
        "name": "Jira Analyst",
        "team": "requirements",
        "role": "requirements",
        "skills": ["jira-subtask-workflow"],
        "cursor_agent": "jira-subtask-workflow",
        "mcp": ["atlassian:getJiraIssue", "atlassian:searchJiraIssuesUsingJql"],
        "intents": ["jira", "story", "epic", "ticket", "subtask", "acceptance"],
        "kb_topics": [],
        "training_topics": ["jira-subtask-workflow"],
        "description": "Reads Jira epics/stories, acceptance criteria, subtasks",
    },
    {
        "id": "confluence-analyst",
        "name": "Confluence Analyst",
        "team": "requirements",
        "role": "requirements",
        "skills": ["codebase-explainer"],
        "cursor_agent": "codebase-explainer",
        "mcp": ["atlassian:searchConfluenceUsingCql", "atlassian:getConfluencePage"],
        "intents": ["confluence", "design doc", "runbook", "wiki"],
        "description": "Pulls Confluence design docs and runbooks",
    },
    {
        "id": "gdrive-analyst",
        "name": "Google Drive Analyst",
        "team": "requirements",
        "role": "requirements",
        "skills": ["codebase-explainer"],
        "cursor_agent": "codebase-explainer",
        "mcp": ["Google Workspace:drive_search", "Google Workspace:drive_read"],
        "intents": ["drive", "google doc", "sheet", "deck", "requirements doc"],
        "description": "Searches Drive for specs, decks, requirement spreadsheets",
    },
    {
        "id": "gsheets-analyst",
        "name": "Google Sheets Analyst",
        "team": "requirements",
        "role": "requirements",
        "skills": ["codebase-explainer"],
        "cursor_agent": "codebase-explainer",
        "mcp": ["Google Workspace:sheets_read", "Google Workspace:sheets_search"],
        "intents": ["sheet", "matrix", "tracker", "field list", "gsheet"],
        "description": "Reads field matrices and CPQ trackers in Sheets",
    },
    # --- Design ---
    {
        "id": "technical-architect",
        "name": "Technical Architect",
        "team": "design",
        "role": "design",
        "skills": ["sfdc-cta-mentor"],
        "cursor_agent": "sfdc-cta-mentor",
        "intents": ["architecture", "design", "framework", "trade-off", "blueprint", "ldv"],
        "kb_topics": ["sfdc/well-architected", "sfdc/integration-patterns"],
        "training_topics": ["sfdc-cta-mentor"],
        "description": "Enterprise architecture, patterns, trade-offs, HTML blueprints — works on any Salesforce org",
    },
    {
        "id": "ux-designer",
        "name": "UI/UX Designer",
        "team": "design",
        "role": "design",
        "skills": ["codebase-explainer", "playwright-e2e-validation"],
        "cursor_agent": "codebase-explainer",
        "intents": ["mockup", "ux", "ui", "wireframe", "lwc layout", "flexipage"],
        "kb_topics": ["sfdc/lwc-fundamentals"],
        "description": "UX flows, LWC/Aura surface, mockup notes — connects to org to read components live",
    },
    # --- Development ---
    {
        "id": "apex-developer",
        "name": "Apex Developer",
        "team": "development",
        "role": "implement",
        "skills": ["advanced-salesforce-developer"],
        "cursor_agent": "advanced-salesforce-developer",
        "intents": ["apex", "trigger", "service", "controller", "batch", "queueable", "cpq"],
        "kb_topics": ["sfdc/apex-design-patterns", "sfdc/governor-limits"],
        "training_topics": ["advanced-salesforce-developer"],
        "description": "Bulkified Apex, triggers, service classes — retrieves existing code from connected org first",
    },
    {
        "id": "ui-developer",
        "name": "UI/UX Developer (LWC)",
        "team": "development",
        "role": "implement",
        "skills": ["advanced-salesforce-developer", "playwright-e2e-validation"],
        "cursor_agent": "advanced-salesforce-developer",
        "intents": ["lwc", "lightning", "component", "aura", "ui", "frontend"],
        "kb_topics": ["sfdc/lwc-fundamentals"],
        "training_topics": ["advanced-salesforce-developer", "playwright-e2e-validation"],
        "description": "LWC/Aura implementation — reads existing components from connected org before building",
    },
    {
        "id": "codebase-worker",
        "name": "Codebase Developer",
        "team": "development",
        "role": "implement",
        "skills": ["advanced-salesforce-developer", "codebase-explainer"],
        "cursor_agent": "advanced-salesforce-developer",
        "intents": ["repo", "codebase", "implement", "fix", "refactor", "build"],
        "kb_topics": ["sfdc/apex-design-patterns", "sfdc/security-sharing"],
        "description": "Repo-aware changes across force-app — retrieves from org and follows existing patterns",
    },
    # --- Admin ---
    {
        "id": "salesforce-admin",
        "name": "Salesforce Admin",
        "team": "admin",
        "role": "implement",
        "skills": ["sfdc-metadata-sync", "sfdc-promotion-workflow"],
        "cursor_agent": "sfdc-metadata-sync",
        "intents": ["metadata", "field", "fls", "permission", "layout", "flow", "profile"],
        "kb_topics": ["codebase/metadata-model", "codebase/security-fls", "codebase/flows-declarative"],
        "training_topics": ["sfdc-metadata-sync", "sfdc-promotion-workflow"],
        "description": "Objects, fields, FLS, flows, layouts, package manifests",
    },
    {
        "id": "promotion-engineer",
        "name": "Promotion Engineer",
        "team": "admin",
        "role": "implement",
        "skills": ["sfdc-promotion-workflow"],
        "cursor_agent": "sfdc-promotion-workflow",
        "intents": ["promote", "deploy", "uat", "release", "promotion"],
        "kb_topics": ["codebase/promotion-manifest"],
        "description": "Sandbox → higher-environment promotion, runbooks, manual steps",
    },
    # --- Review ---
    {
        "id": "pr-reviewer",
        "name": "PR Reviewer",
        "team": "review",
        "role": "review",
        "skills": ["pr-reviewer"],
        "cursor_agent": "pr-reviewer",
        "intents": ["review", "pr", "diff", "approve", "request changes", "code review"],
        "kb_topics": ["sfdc/security-sharing", "sfdc/governor-limits", "sfdc/testing-deployment"],
        "training_topics": ["pr-reviewer"],
        "description": "Structured review of Apex, LWC, Flow, and metadata changes with a clear deploy decision",
    },
    # --- QA ---
    {
        "id": "qa-playwright",
        "name": "QA — Playwright E2E",
        "team": "qa",
        "role": "qa",
        "skills": ["playwright-e2e-validation"],
        "cursor_agent": None,
        "intents": ["e2e", "playwright", "ui test", "regression ui"],
        "description": "Browser E2E validation for quoting and bundle flows",
    },
    {
        "id": "qa-apex-backend",
        "name": "QA — Apex & Data",
        "team": "qa",
        "role": "qa",
        "skills": ["advanced-salesforce-developer", "playwright-e2e-validation"],
        "cursor_agent": "advanced-salesforce-developer",
        "intents": ["test", "apex test", "query", "edge case", "regression", "coverage"],
        "kb_topics": ["sfdc/testing-deployment"],
        "description": "Apex tests, sf data queries, governor-limit edge cases",
    },
    # --- Documentation ---
    {
        "id": "change-documenter",
        "name": "Change Documenter",
        "team": "documentation",
        "role": "document",
        "skills": ["codebase-explainer"],
        "cursor_agent": "codebase-explainer",
        "intents": ["document", "explain", "deep dive", "html doc", "what changed"],
        "description": "HTML deep-dive docs of changes, architecture explainers",
    },
    # --- Training ---
    {
        "id": "skill-trainer",
        "name": "Skill Trainer",
        "team": "training",
        "role": "train",
        "skills": ["sfdc-metadata-sync"],
        "cursor_agent": None,
        "intents": ["train", "refresh kb", "update skills"],
        "description": "Runs codebase KB refresh and doc swarm for agents used in run",
    },
]

# LangGraph supervisor routing targets (graph node names)
GRAPH_NODES: List[Dict[str, Any]] = [
    {"id": "orchestrator", "label": "Orchestrator", "phase": "Route"},
    {"id": "requirements_team", "label": "Requirements", "phase": "Gather"},
    {"id": "research_team", "label": "Research", "phase": "KB + RAG"},
    {"id": "design_team", "label": "Design", "phase": "Architect"},
    {"id": "development_team", "label": "Development", "phase": "Implement"},
    {"id": "admin_team", "label": "Admin", "phase": "Metadata"},
    {"id": "review_team", "label": "Review", "phase": "Review"},
    {"id": "qa_team", "label": "QA", "phase": "Test"},
    {"id": "documentation_team", "label": "Documentation", "phase": "Document"},
    {"id": "training_team", "label": "Training", "phase": "Train KB"},
    {"id": "finalize", "label": "Finalize", "phase": "Deliver"},
]

INTENT_TO_TEAMS: Dict[str, List[str]] = {
    # Read-only analysis — live org scan + document findings. No dev, no QA.
    "discover": ["research_team", "documentation_team"],
    # PR / code review gate only. No building.
    "review": ["review_team"],
    # Architecture and blueprints. No building, no QA.
    "design": ["requirements_team", "research_team", "design_team"],
    # Full feature implementation — includes dev, QA, docs.
    "implement": [
        "requirements_team",
        "research_team",
        "development_team",
        "admin_team",
        "qa_team",
        "documentation_team",
        "training_team",
    ],
    # Jira requirements only. No building, no QA.
    "jira_only": ["requirements_team", "documentation_team"],
    # QA/test only.
    "test": ["qa_team", "documentation_team"],
    # Documentation / explanation only. No building, no QA.
    "document": ["documentation_team"],
    # Full lifecycle.
    "full_delivery": [
        "requirements_team",
        "research_team",
        "design_team",
        "development_team",
        "admin_team",
        "review_team",
        "qa_team",
        "documentation_team",
        "training_team",
    ],
    "kb_refresh": ["training_team"],
}


def agent_by_id(agent_id: str) -> Dict[str, Any] | None:
    return next((a for a in AGENTS if a["id"] == agent_id), None)


def agents_for_team(team_id: str) -> List[Dict[str, Any]]:
    return [a for a in AGENTS if a.get("team") == team_id]


def team_by_id(team_id: str) -> Dict[str, Any] | None:
    return next((t for t in TEAMS if t["id"] == team_id), None)
