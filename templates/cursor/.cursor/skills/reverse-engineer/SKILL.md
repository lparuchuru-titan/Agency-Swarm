# Reverse Engineer Skill

## Role
Turn any Salesforce org or metadata set into comprehensive, human-readable documentation.
Read-only. Never modifies the org or repo.

## Lifecycle position
**Discover** — runs on unfamiliar orgs, before migrations, or when team knowledge needs to be externalised.

## Output catalogue

| Document | What it covers | Primary audience |
|---|---|---|
| BRD | Business rules, user roles, journeys inferred from metadata | Product, Business stakeholders |
| Functional Spec | Feature-by-feature, AC from test assertions, known gaps | Developers, QA |
| Data Dictionary | Every custom object + field: type, purpose, relationships | Developers, Admins, Data team |
| ERD | Mermaid entity-relationship diagram | Architects, Developers |
| Integration Map | Named Creds, callouts, REST resources, Platform Events | Architects, Integration team |
| Automation Inventory | Flows, Triggers, Process Builders, conflict matrix | Admins, Developers |
| Onboarding Guide | Repo structure, key classes, gotchas, "start here" | New developers |

## Metadata retrieval commands

```bash
# Objects + fields
sf project retrieve start --metadata "CustomObject" --target-org <alias>

# Flows
sf project retrieve start --metadata "Flow" --target-org <alias>

# Triggers + classes
sf project retrieve start --metadata "ApexTrigger,ApexClass" --target-org <alias>

# Permission sets + profiles (for role mapping)
sf project retrieve start --metadata "PermissionSet,Profile" --target-org <alias>
```

## ERD generation (Mermaid)

Template to embed in HTML output:
```html
<pre class="mermaid">
erDiagram
  ACCOUNT ||--o{ OPPORTUNITY : "has"
  OPPORTUNITY ||--|{ QUOTE : "has"
  QUOTE ||--o{ QUOTE_LINE : "contains"
  QUOTE_LINE }|--|| PRODUCT : "references"
</pre>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
```

## Business rule extraction heuristics

| Salesforce artefact | Business rule to extract |
|---|---|
| Validation Rule | "Field X is required when Y" or "X cannot exceed Y" |
| Formula field | Computed business value or classification |
| Flow decision element | Business branch condition |
| `if` in Apex | Programmatic business rule |
| Required field | Must-have data for the process |
| Picklist values | Allowed statuses / categories in the business |
| Lookup filter | Relationship constraint |

## Automation conflict detection

A conflict exists when:
- Same object, same trigger event (BeforeInsert) has BOTH a Trigger AND a Record-Triggered Flow
- Same object has multiple active Triggers
- A Flow and a Validation Rule check the same field with contradictory logic

## Output template

Save HTML to `docs/explainers/YYYYMMDD-reverse-eng-<scope>.html`.
Structure:
1. Executive summary (what this org does in 3 sentences)
2. Data model overview (ERD + key object descriptions)
3. Business rules catalogue (validation rules + formula logic)
4. Automation inventory table
5. Integration map
6. Onboarding quick-start

## Guardrails
- Read-only. Never modify the org or repo.
- Do not invent business rules not evidenced in metadata or code.
- Mark inferred intent as "inferred — confirm with business owner."
- Cite every claim: "Field `X__c` is required by validation rule `VR_Name`."
