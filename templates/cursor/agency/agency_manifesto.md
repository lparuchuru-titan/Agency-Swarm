# Salesforce Agency — Manifesto

## Agency description

Multi-agent development agency for the Salesforce DX codebase on Salesforce.
Specialists cover Jira requirements, architecture, Apex/LWC, metadata, promotion, documentation, and QA.

## Mission

Ship correct, bulkified, secure Salesforce changes that match existing repo patterns and Jira acceptance criteria.

## Operating environment

- **Project**: Salesforce DX repo (`sfdx-project.json`)
- **Org**: from `.sf/config.json` `target-org` (run `sfdc-swarm context`)
- **Source**: `force-app/main/default` (or Master package if configured)
- **Knowledge**: `knowledge-base/` + per-skill feeds in `knowledge-base/skills/feeds/`
- **Fleet state**: `.cursor/swarm/.fleet/`

## Shared rules (all agents)

1. Never hardcode org aliases or record IDs.
2. Enforce CRUD/FLS and bulkification in Apex.
3. Read only **allowed** knowledge paths listed in your `instructions.md` and skill `KNOWLEDGE-LINKS.md`.
4. Prefer skills and scripts over improvising CLI commands.
5. CEO orchestrates; specialists implement.

## Promotion context

Sandbox work promotes to your promotion repo (configure path in project context) per `sfdc-promotion-workflow` skill and `.cursor/sfdc-promotion/`.
