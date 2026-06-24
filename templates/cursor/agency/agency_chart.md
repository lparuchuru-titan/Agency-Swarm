# Agency communication chart

Directional flows (left can initiate → right). **CEO** is the user entry point.

```
User → CEO
CEO → jira-subtask-workflow
CEO → sfdc-cta-mentor
CEO → advanced-salesforce-developer
CEO → sfdc-metadata-sync
CEO → sfdc-promotion-workflow
CEO → codebase-explainer
CEO → playwright-e2e-validation
jira-subtask-workflow → advanced-salesforce-developer  (story handoff)
sfdc-cta-mentor → advanced-salesforce-developer  (design handoff)
advanced-salesforce-developer → playwright-e2e-validation  (test handoff)
advanced-salesforce-developer → codebase-explainer  (doc handoff)
sfdc-metadata-sync → sfdc-promotion-workflow  (promote handoff)
```

In Cursor: CEO uses the **Task** tool to launch subagents matching `.cursor/agents/*.md`.

_Updated 2026-06-18T05:11:13.542346+00:00_