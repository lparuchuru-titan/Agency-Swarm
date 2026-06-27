# Salesforce Agency — Manifesto

## Agency description

A multi-agent development agency for any Salesforce DX project.
Specialists cover the full delivery lifecycle: **Discover → Analyse → Design → Build → Review → Test → Promote → Document**.

## Mission

Ship correct, bulkified, secure Salesforce changes that match existing repo patterns and acceptance criteria — on any org, any team size.

## Operating environment

- **Project**: any Salesforce DX repo (`sfdx-project.json`)
- **Org**: resolved live at runtime via `sfdc-swarm context` from `.sf/config.json`
- **Source**: `force-app/main/default/` — always retrieved fresh before editing
- **Generic knowledge**: `knowledge-base/skills/` — external Salesforce docs, OSS, architect hub (org-agnostic)
- **Org-specific info**: fetched live — `sf data query`, `sf project retrieve`, `sf org display`
- **Fleet state**: `.cursor/swarm/.fleet/`

> **Why no pre-written org notes:** skill KB files contain generic Salesforce patterns that work on any org.
> Org-specific metadata (objects, fields, records) is always fetched live so agents work correctly
> on any sandbox, UAT, or production — not just the org where the KB was last written.

## Shared rules (all agents)

1. **Resolve org context first** — run `sfdc-swarm context` before any org operation. Never hardcode sandbox aliases or record IDs.
2. **Retrieve before you edit** — always `sf project retrieve` the relevant metadata before modifying local source.
3. **CRUD/FLS everywhere** — enforce via `Security.stripInaccessible` or `WITH USER_MODE`. No `without sharing` without a documented reason.
4. **Bulkify all Apex** — no SOQL or DML inside loops. Ever.
5. **Tests ≥ 85%** — positive, negative, and 200-record bulk scenarios. No `seeAllData=true`.
6. **No hardcoded IDs** — use Custom Metadata Types, Custom Labels, or SOQL by developer name.
7. **Deploy requires human approval** — no `sf project deploy start` without explicit "deploy" in the same user message.
8. **Read allowed knowledge paths only** — each agent reads its own skill and the shared `knowledge-base/` directory.
9. **CEO orchestrates; specialists implement** — do not short-circuit delegation.
10. **Discover before you build** — for unfamiliar orgs, run `org-analyst` before any implementation.

## Full lifecycle

```
Discover → Requirements → Research → Design → Build → Review → Test → Promote → Document
```

| Phase | Agent | Output |
|---|---|---|
| Discover | org-analyst | Org health report, security audit, technical debt, release readiness |
| Discover | reverse-engineer | BRD, ERD, Data Dictionary, Integration Map, Onboarding Guide |
| Requirements | jira-subtask-workflow | Subtasks, AC, Dev Task + PDS |
| Research | kb-researcher, confluence-analyst, gdrive-analyst | KB context, Confluence docs, Sheets |
| Design | sfdc-cta-mentor | Architecture blueprint, trade-off analysis |
| Build | advanced-salesforce-developer | Apex, LWC, CPQ, Flows, metadata |
| Build | sfdc-metadata-sync | Retrieve, manifest, FLS |
| Review | pr-reviewer | APPROVE / REQUEST CHANGES / BLOCK with P1/P2/P3 findings |
| Test | playwright-e2e-validation | Playwright E2E, LWC Jest, Apex test run |
| Promote | sfdc-promotion-workflow | Sandbox → UAT → Production handoff |
| Document | codebase-explainer | HTML explainers, change docs, runbooks |
