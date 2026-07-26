# Agency communication chart

Directional flows (left can initiate → right). **CEO** is the user entry point.

```
User → CEO
CEO → org-analyst
CEO → reverse-engineer
CEO → jira-subtask-workflow
CEO → sfdc-cta-mentor
CEO → advanced-salesforce-developer
CEO → sfdc-metadata-sync
CEO → apex-space-reclaimer
CEO → pr-reviewer
CEO → sfdc-promotion-workflow
CEO → codebase-explainer
CEO → playwright-e2e-validation
org-analyst → sfdc-cta-mentor  (findings → design)
reverse-engineer → codebase-explainer  (docs handoff)
jira-subtask-workflow → advanced-salesforce-developer  (story handoff)
sfdc-cta-mentor → advanced-salesforce-developer  (design handoff)
advanced-salesforce-developer → pr-reviewer  (review gate)
advanced-salesforce-developer → playwright-e2e-validation  (test handoff)
advanced-salesforce-developer → codebase-explainer  (doc handoff)
pr-reviewer → sfdc-promotion-workflow  (approved promote)
sfdc-metadata-sync → sfdc-promotion-workflow  (promote handoff)
apex-space-reclaimer → advanced-salesforce-developer  (reclaim implementation)
```

In Cursor: CEO uses the **Task** tool to launch subagents matching `.cursor/agents/*.md`.

_Updated 2026-07-25_
