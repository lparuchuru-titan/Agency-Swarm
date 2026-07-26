"""Development swarm teams — UI/UX, Salesforce Dev, Salesforce Admin."""
from __future__ import annotations

from typing import Any, Dict, List

TEAMS: List[Dict[str, Any]] = [
    {
        "id": "ui-ux",
        "name": "UI/UX Team",
        "description": "LWC, Aura, flexipages, custom UI, Playwright validation",
        "color": "#a78bfa",
        "agents": ["codebase-explainer", "playwright-e2e-validation"],
        "skills": ["codebase-explainer", "playwright-e2e-validation"],
    },
    {
        "id": "salesforce-dev",
        "name": "Salesforce Team",
        "description": "Apex, triggers, CPQ runtime, custom bundles, Jira dev tasks",
        "color": "#60a5fa",
        "agents": [
            "advanced-salesforce-developer",
            "jira-subtask-workflow",
            "codebase-explainer",
            "sfdc-cta-mentor",
        ],
        "skills": [
            "advanced-salesforce-developer",
            "jira-subtask-workflow",
            "codebase-explainer",
            "sfdc-cta-mentor",
        ],
    },
    {
        "id": "salesforce-admin",
        "name": "Salesforce Admin Team",
        "description": "Metadata sync, promotion, FLS, flows, layouts, package manifests",
        "color": "#34d399",
        "agents": [
            "sfdc-metadata-sync",
            "sfdc-promotion-workflow",
            "jira-subtask-workflow",
        ],
        "skills": [
            "sfdc-metadata-sync",
            "sfdc-promotion-workflow",
            "jira-subtask-workflow",
        ],
    },
]

# Example codebase topics — adjust globs/grep terms to match your own force-app layout.
CODEBASE_TOPICS: List[Dict[str, Any]] = [
    {
        "key": "lwc-catalog",
        "team": "ui-ux",
        "title": "Lightning Web Components catalog",
        "focus": "LWC inventory, @wire vs imperative, key UI components.",
        "glob": ["force-app/**/lwc/**/*.js", "force-app/**/lwc/**/*.html"],
        "grep": ["export default class", "@wire", "@api"],
    },
    {
        "key": "aura-flexipages",
        "team": "ui-ux",
        "title": "Aura bundles & Lightning pages",
        "focus": "Aura components, flexipages, record pages.",
        "glob": [
            "force-app/**/aura/**/*",
            "force-app/**/flexipages/*.xml",
            "force-app/**/layouts/*.xml",
        ],
        "grep": ["aura:component", "flexipage", "layout"],
    },
    {
        "key": "cpq-ui",
        "team": "ui-ux",
        "title": "CPQ quote line UI surface",
        "focus": "Quote line editor customizations, bundle UI, CPQ front-end integration.",
        "glob": [
            "force-app/**/lwc/*quote*/**/*",
            "force-app/**/classes/*Quote*.cls",
        ],
        "grep": ["SBQQ", "Quote", "Bundle"],
    },
    {
        "key": "apex-services",
        "team": "salesforce-dev",
        "title": "Apex services & controllers",
        "focus": "Service/selector patterns, catalog and quoting controllers.",
        "glob": ["force-app/**/classes/*.cls"],
        "grep": ["Service", "Controller", "Selector"],
    },
    {
        "key": "triggers-automation",
        "team": "salesforce-dev",
        "title": "Triggers & Apex automation",
        "focus": "Trigger handlers, recursion control, batch/queueable jobs.",
        "glob": [
            "force-app/**/triggers/*.trigger",
            "force-app/**/classes/*Trigger*.cls",
            "force-app/**/classes/*Batch*.cls",
            "force-app/**/classes/*Queueable*.cls",
        ],
        "grep": ["TriggerHandler", "Recursion", "Batchable", "Queueable"],
    },
    {
        "key": "cpq-backend",
        "team": "salesforce-dev",
        "title": "CPQ backend (optional)",
        "focus": "Bundle definitions, CPQ Apex, product/bundle metadata (Salesforce CPQ / SBQQ).",
        "glob": [
            "force-app/**/classes/*CPQ*.cls",
            "force-app/**/objects/SBQQ__*/**",
            "force-app/**/objects/Product2/**",
        ],
        "grep": ["SBQQ", "Bundle", "QuoteLine"],
    },
    {
        "key": "metadata-model",
        "team": "salesforce-admin",
        "title": "Custom objects & fields",
        "focus": "Object/field inventory, custom object relationships.",
        "glob": [
            "force-app/**/objects/**/*.object-meta.xml",
            "force-app/**/objects/**/*.field-meta.xml",
        ],
        "grep": ["__c", "customField", "relationshipName"],
    },
    {
        "key": "security-fls",
        "team": "salesforce-admin",
        "title": "Permission sets, profiles & FLS",
        "focus": "Permission sets, admin access, field-level security patterns.",
        "glob": [
            "force-app/**/permissionsets/*.xml",
            "force-app/**/profiles/*.xml",
        ],
        "grep": ["fieldPermissions", "objectPermissions", "PermissionSet"],
    },
    {
        "key": "flows-declarative",
        "team": "salesforce-admin",
        "title": "Flows & declarative automation",
        "focus": "Record-triggered flows, subflows, before/after-save automation.",
        "glob": ["force-app/**/flows/*.flow-meta.xml"],
        "grep": ["recordTriggerType", "subflow", "decisions"],
    },
    {
        "key": "promotion-manifest",
        "team": "salesforce-admin",
        "title": "Promotion & package manifests",
        "focus": "manifest/package.xml batches, promotion tracker, sandbox changelog.",
        "glob": [
            "manifest/**/*.xml",
            ".cursor/sfdc-promotion/**",
            "manifest/package.xml",
        ],
        "grep": ["members", "package", "version"],
    },
]

# Example project-specific KB topics for a per-project knowledge-base/project/ folder.
# Copy and adapt this list into your own project (see templates/project/project-topics.example.json).
PROJECT_TOPICS_EXAMPLE: List[Dict[str, str]] = [
    {"key": "00-architecture-overview", "team": "salesforce-dev", "title": "Architecture overview"},
    {"key": "quoting-runtime", "team": "salesforce-dev", "title": "Quoting runtime"},
    {"key": "data-model-and-automation", "team": "salesforce-admin", "title": "Data model & automation"},
]


def team_by_id(team_id: str) -> Dict[str, Any] | None:
    return next((t for t in TEAMS if t["id"] == team_id), None)


def topics_for_team(team_id: str) -> List[Dict[str, Any]]:
    return [t for t in CODEBASE_TOPICS if t.get("team") == team_id]
