"""Development swarm teams — UI/UX, Salesforce Dev, Salesforce Admin."""
from __future__ import annotations

from typing import Any, Dict, List

TEAMS: List[Dict[str, Any]] = [
    {
        "id": "ui-ux",
        "name": "UI/UX Team",
        "description": "LWC, Aura, flexipages, quoting UI, Playwright validation",
        "color": "#a78bfa",
        "agents": ["codebase-explainer", "playwright-e2e-validation"],
        "skills": ["codebase-explainer", "playwright-e2e-validation"],
    },
    {
        "id": "salesforce-dev",
        "name": "Salesforce Team",
        "description": "Apex, triggers, CPQ runtime, Pantheon bundles, Jira dev tasks",
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

CODEBASE_TOPICS: List[Dict[str, Any]] = [
    {
        "key": "lwc-catalog",
        "team": "ui-ux",
        "title": "Lightning Web Components catalog",
        "focus": "LWC inventory, @wire vs imperative, key quoting UI components.",
        "glob": ["force-app/**/lwc/**/*.js", "force-app/**/lwc/**/*.html"],
        "grep": ["nextGen", "pantheon", "bundle", "quote"],
    },
    {
        "key": "aura-flexipages",
        "team": "ui-ux",
        "title": "Aura bundles & Lightning pages",
        "focus": "Aura components, flexipages, record pages for quoting/CPQ.",
        "glob": [
            "force-app/**/aura/**/*",
            "force-app/**/flexipages/*.xml",
            "force-app/**/layouts/*.xml",
        ],
        "grep": ["SBQQ", "Quote", "Pantheon"],
    },
    {
        "key": "pantheon-ui",
        "team": "ui-ux",
        "title": "Pantheon bundle UI surface",
        "focus": "pantheonBundle*, bundle quote line views, CPQ UI integration.",
        "glob": [
            "force-app/**/lwc/pantheon*/**/*",
            "force-app/**/classes/Pantheon*.cls",
        ],
        "grep": ["Pantheon", "Bundle", "pantheonBundle"],
    },
    {
        "key": "apex-services",
        "team": "salesforce-dev",
        "title": "Apex services & controllers",
        "focus": "Service/selector patterns, ProductCatalog*, quoting controllers.",
        "glob": ["force-app/**/classes/*.cls"],
        "grep": ["Service", "Controller", "ProductCatalog", "CartToQuote"],
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
        "grep": ["TriggerHelper", "Recursion", "SBQQ"],
    },
    {
        "key": "nextgen-quoting-runtime",
        "team": "salesforce-dev",
        "title": "NextGen quoting runtime",
        "focus": "ProductCatalogService, LookupData rules, cart→quote transform.",
        "glob": [
            "force-app/**/classes/ProductCatalog*.cls",
            "force-app/**/classes/Cart*.cls",
            "force-app/**/classes/*LookupData*.cls",
            "force-app/**/lwc/nextGen*/**/*",
        ],
        "grep": ["LookupData", "nextGenQuoting", "SBQQ__LookupData"],
    },
    {
        "key": "pantheon-cpq-backend",
        "team": "salesforce-dev",
        "title": "Pantheon CPQ backend",
        "focus": "Bundle definitions, Pantheon Apex, CPQ product/bundle metadata.",
        "glob": [
            "force-app/**/classes/Pantheon*.cls",
            "force-app/**/objects/Bundle_Definition__c/**",
            "force-app/**/objects/Product2/**",
        ],
        "grep": ["Pantheon", "Bundle_Definition", "Bundle_SKU"],
    },
    {
        "key": "metadata-model",
        "team": "salesforce-admin",
        "title": "Custom objects & fields",
        "focus": "Object/field inventory, CPQ objects, Pantheon custom fields.",
        "glob": [
            "force-app/**/objects/**/*.object-meta.xml",
            "force-app/**/objects/**/*.field-meta.xml",
        ],
        "grep": ["SBQQ__", "Bundle_", "Pantheon"],
    },
    {
        "key": "security-fls",
        "team": "salesforce-admin",
        "title": "Permission sets, profiles & FLS",
        "focus": "OSCPQ perm sets, CPQ admin access, field-level security patterns.",
        "glob": [
            "force-app/**/permissionsets/*.xml",
            "force-app/**/profiles/*.xml",
        ],
        "grep": ["OSCPQ", "CPQ", "Pantheon", "SBQQ"],
    },
    {
        "key": "flows-declarative",
        "team": "salesforce-admin",
        "title": "Flows & declarative automation",
        "focus": "Record-triggered flows, CPQ-related flows, subflows.",
        "glob": ["force-app/**/flows/*.flow-meta.xml"],
        "grep": ["SBQQ", "Quote", "Pantheon", "Bundle"],
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
        "grep": ["Pantheon", "Bundle", "package"],
    },
]

NEXTGEN2_TOPICS: List[Dict[str, str]] = [
    {"key": "00-architecture-overview", "team": "salesforce-dev", "title": "Architecture overview"},
    {"key": "nextgen-quoting-runtime", "team": "salesforce-dev", "title": "NextGen quoting runtime"},
    {"key": "lookupdata-rule-engine", "team": "salesforce-dev", "title": "LookupData rule engine"},
    {"key": "stcb-billing-subsystem", "team": "salesforce-dev", "title": "STCB billing"},
    {"key": "amendment-renewal-usage-rating", "team": "salesforce-dev", "title": "Amendment & usage"},
    {"key": "ai-agent-subsystem", "team": "salesforce-dev", "title": "AI agent subsystem"},
    {"key": "pantheon-2026-cpq", "team": "salesforce-dev", "title": "Pantheon 2026 CPQ"},
    {"key": "data-model-and-automation", "team": "salesforce-admin", "title": "Data model & automation"},
]


def team_by_id(team_id: str) -> Dict[str, Any] | None:
    return next((t for t in TEAMS if t["id"] == team_id), None)


def topics_for_team(team_id: str) -> List[Dict[str, Any]]:
    return [t for t in CODEBASE_TOPICS if t.get("team") == team_id]
