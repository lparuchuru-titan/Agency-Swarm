# Salesforce Knowledge Base — Index

## `project/` — your org-specific architecture notes

Authored from direct code analysis of your own Salesforce DX repo (`codebase-explainer`, `reverse-engineer`, or manual notes). Empty by default — add Markdown files here, or point `PROJECT_NOTES_DIR` topics at your own architecture docs. Example layout:

| Topic | Note |
|-------|------|
| Architecture overview & domain map | `project/00-architecture-overview.md` |
| Quoting runtime (catalog → cart → save) | `project/quoting-runtime.md` |
| Custom rule engine notes | `project/rule-engine.md` |
| Billing subsystem | `project/billing-subsystem.md` |
| Data model & automation | `project/data-model-and-automation.md` |

See `templates/project/project-topics.example.json` for the topic-registration format.

## `sfdc/` — generic Salesforce topics

Built by the SFDC Knowledge Swarm (Claude Code / Cursor SDK, no API key required for static tiers).

| Topic | Note | Status |
|-------|------|--------|
| Apex Design Patterns & Trigger Frameworks | [sfdc/apex-design-patterns.md](sfdc/apex-design-patterns.md) | partial |
| Salesforce CPQ Fundamentals | [sfdc/cpq-fundamentals.md](sfdc/cpq-fundamentals.md) | partial |
| Flow & Declarative Automation | [sfdc/flows-automation.md](sfdc/flows-automation.md) | partial |
| Governor Limits & Large Data Volumes | [sfdc/governor-limits.md](sfdc/governor-limits.md) | partial |
| Integration Patterns | [sfdc/integration-patterns.md](sfdc/integration-patterns.md) | partial |
| Lightning Web Components | [sfdc/lwc-fundamentals.md](sfdc/lwc-fundamentals.md) | written |
| Security, Sharing & FLS | [sfdc/security-sharing.md](sfdc/security-sharing.md) | partial |
| Testing & Deployment (SFDX/CI) | [sfdc/testing-deployment.md](sfdc/testing-deployment.md) | partial |
