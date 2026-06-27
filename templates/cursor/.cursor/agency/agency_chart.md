# Agency communication chart

Directional flows — left can initiate → right. **CEO** is the user entry point.

```
User → CEO

# Discovery
CEO → org-analyst            (audit, health, security, technical debt)
CEO → reverse-engineer        (BRD, ERD, data dictionary, integration map)

# Requirements
CEO → jira-subtask-workflow   (stories, epics, acceptance criteria, subtasks)

# Design
CEO → sfdc-cta-mentor         (architecture, blueprints, trade-offs)
sfdc-cta-mentor → advanced-salesforce-developer   (design → implementation handoff)

# Build
CEO → advanced-salesforce-developer  (Apex, LWC, CPQ, Flows)
CEO → sfdc-metadata-sync             (retrieve, manifests, FLS, org sync)

# Review (pre-deploy gate)
CEO → pr-reviewer                                    (PR gate after every build)
advanced-salesforce-developer → pr-reviewer          (auto-gate after implementation)
pr-reviewer → sfdc-cta-mentor                        (escalate architecture disputes)

# Test
advanced-salesforce-developer → playwright-e2e-validation  (test handoff)
CEO → playwright-e2e-validation                             (direct E2E request)

# Promote
sfdc-metadata-sync → sfdc-promotion-workflow    (retrieve → promote handoff)
pr-reviewer → sfdc-promotion-workflow           (approved → promote handoff)

# Document
CEO → codebase-explainer                        (explain, deep dive, HTML docs)
advanced-salesforce-developer → codebase-explainer  (post-build doc handoff)
org-analyst → codebase-explainer                (findings → documented report)
reverse-engineer → codebase-explainer           (reverse-eng → full HTML doc)
```

## Full lifecycle flow

```
org-analyst ──────────────────────────────────────────────► (health baseline)
reverse-engineer ─────────────────────────────────────────► (org documentation)
     │
jira-subtask-workflow ────────────────────────────────────► (requirements)
     │
sfdc-cta-mentor ──────────────────────────────────────────► (architecture)
     │
sfdc-metadata-sync ───► advanced-salesforce-developer ────► (retrieve → build)
                                    │
                              pr-reviewer ─────────────────► (APPROVE / BLOCK)
                                    │
                        playwright-e2e-validation ─────────► (test)
                                    │
                        sfdc-promotion-workflow ────────────► (promote)
                                    │
                        codebase-explainer ─────────────────► (document)
```

In Cursor: CEO uses the **Task** tool to launch subagents matching `.cursor/agents/*.md`.

_Updated by agency_cursor_sync — generic Salesforce agency template_
