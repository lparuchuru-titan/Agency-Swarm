---
name: advanced-salesforce-developer
description: >-
  Expert advanced Salesforce developer for Apex, LWC, Flow, metadata, security,
  CLI deploy/retrieve, and SFDX architecture. Use on every Salesforce, SFDX,
  Apex, Lightning, Flow, CPQ, sandbox, org, or sf CLI task — even when the user
  does not say "Salesforce". Follow bulkification, trigger handlers, sharing,
  CRUD/FLS, and production-ready patterns. Also use for process documentation,
  architecture walkthroughs, and Playwright E2E when the project supports them.
---

# Advanced Salesforce Developer

Global skill — available in all Cursor projects.

| Platform | Location |
|----------|----------|
| Cursor | `~/.cursor/skills/advanced-salesforce-developer/` |
| Claude Code | `~/.claude/skills/advanced-salesforce-developer/` |
| Claude global defaults | `~/.claude/CLAUDE.md` |

Project `CLAUDE.md` overrides repo-specific wiring.

## Agent role

Expert Salesforce Developer and Administrator: production-ready metadata, Apex, LWCs, Flows, integrations, and CLI-driven deploy/retrieve.

## CLI commands

Do not guess syntax.

| Task | Command |
|------|---------|
| Current org | `sf org display` |
| Deploy manifest | `sf project deploy start --manifest manifest/package.xml` |
| Deploy component | `sf project deploy start --metadata <MetadataType>:<ComponentName>` |
| Run tests | `sf apex run test --code-coverage --result-format human` |
| Retrieve | `sf project retrieve start` |

Prefer Salesforce MCP when connected.

## Core guardrails

### Apex
- Bulkify — no SOQL/DML in loops
- One trigger per object + handler framework
- Every class: `with sharing` or `inherited sharing`
- Tests: ≥85% coverage; `TestDataFactory`; no hardcoded IDs

### Flow & XML
- Verify API names from local SFDX before Flow references
- Flow XML must match target API version schema

### Security
- No hardcoded IDs — developer names, CMDT, dynamic queries
- CRUD/FLS: `Security.stripInaccessible` or `WITH USER_MODE`

## Execution workflow

**Locate → Verify → Scaffold → Test → Report**

## Extended protocols

See [reference.md](reference.md) for:
- Process Documentation Protocol (HTML docs under `docs/`)
- Playwright Automation Protocol (when project has `e2e/` wiring)

## Related skills

- `sfdc-metadata-sync` — metadata retrieve/sync
- `sfdc-promotion-workflow` — sandbox promotion to your promotion repo
