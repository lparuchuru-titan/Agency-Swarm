---
name: jira-subtask-workflow
description: >-
  Create and maintain Jira subtasks (Dev Task, PDS Data, PDS Permissions/Layout,
  PDS QCP, PDS Manual) for Salesforce stories. Tracks metadata pushed to sandbox
  in Dev Task and manual/data steps in PDS for DevOps promotion. Use when working
  on a Jira story, deploying to sandbox, preparing promotion, or when the user
  asks to update Dev Task or PDS subtasks for project tickets.
---

# Jira Subtask Workflow

Maintain **Dev Task** and **PDS** subtasks under each parent story so DevOps can promote metadata and manual steps to higher environments.

Global skill:
- **Cursor:** `~/.cursor/skills/jira-subtask-workflow/`
- **Claude:** `~/.claude/skills/jira-subtask-workflow/`

## Team patterns (example — adapt to your Jira project)

| Parent type | Example | Subtasks created |
|-------------|---------|------------------|
| Product / Story | `PROJ-1001` | Dev Task + PDS variants |
| Dev Task + metadata | `PROJ-1002` | Deploy manifest, components, validation |
| PDS (Data) | `PROJ-1003` | Apex scripts, seed data, LookupData |
| PDS (QCP) | `PROJ-1004` | CPQ / quote calculator manual steps |

### What goes where

| Bucket | Goes in subtask | Examples |
|--------|-----------------|----------|
| **Dev Task** | Metadata in git / manifest deploy | Apex, LWC, fields, objects, permission sets, layouts, tabs, profiles |
| **PDS (Data)** | Per-org data — **never copy record IDs** | `scripts/apex/*.apex`, `SBQQ__LookupData__c`, junction/config object seed data |
| **PDS (Permissions & Layout)** | Post-deploy manual checks + profile/layout deploy notes | FLS verification, tab visibility, perm set assignment |
| **PDS (QCP)** | CPQ-specific manual steps | Quote lines, product rules, QCP calculator |
| **PDS (Manual Steps)** | Finance pricing, open decisions, onboarding | Runbook section C items |

## Setup (once per project)

```bash
mkdir -p .cursor/jira-subtasks
cp ~/.cursor/skills/jira-subtask-workflow/config.example.json .cursor/jira-subtasks/config.json
# Edit parentStoryKey, sandbox org, Jira project key
```

### Jira API (optional — for auto push)

```bash
export JIRA_EMAIL='you@yourcompany.com'
export JIRA_API_TOKEN='...'   # Atlassian API token
export JIRA_BASE_URL='https://yourcompany.atlassian.net'
```

Without credentials, the skill still updates **local tracker + markdown** for copy-paste into Jira.

## Agent workflow

### 1. Start work on a story

```bash
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/init-story.py PROJ-1001 --push
```

Creates tracker + Jira subtasks (if `--push` and credentials set):
- `Dev Task — {story title}`
- `PDS (Data) — {story title}`
- `PDS (Permissions & Layout) — {story title}`
- `PDS (Manual Steps) — {story title}`

### 2. After every sandbox deploy — sync changes

**Run automatically** when user deploys metadata to sandbox:

```bash
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/sync-from-work.py \
  --deploy-command "sf project deploy start --manifest manifest/my_deploy.xml --target-org MY_SANDBOX" \
  --ticket PROJ-1001 \
  --push
```

This:
- Reads git changes + `.cursor/sfdc-promotion/sandbox-tracker.json` (if present)
- Classifies files → Dev Task vs PDS buckets
- Updates `dev-task.md`, `pds-data.md`, etc.
- Updates Jira subtask descriptions when `--push`

### 3. Add manual PDS steps (runbook / open decisions)

```bash
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/add-pds-step.py \
  -t "Set bundle list prices after Finance sign-off" \
  -n "Update Product2 + PricebookEntry in each org"
```

### 4. Check status

```bash
python3 ~/.cursor/skills/jira-subtask-workflow/scripts/status.py
```

## Creating subtasks via Atlassian MCP

**Cursor** — **`atlassian`** MCP (OAuth in Settings). **Claude Code** — built-in Atlassian connector.

Use create/edit issue tools with:
- `projectKey: "<YOUR_PROJECT_KEY>"`, `issueTypeName: "Sub-task"`, `parent: "<story key>"`
- `contentFormat: "markdown"` — **GFM tables render** in Jira; always use tables (see templates below).
- Some Jira instances require additional custom fields on create (e.g. an "Enablement" flag) — check your project's issue-type field metadata for required custom fields before creating.
- Summaries follow your team's convention (e.g. exactly `Dev Task` and `PDS`, not "Dev Task — …") — confirm with your team.

## Dev Task template (tabular — Labels + API names)

```markdown
## Dev Task — <object> fields (PROJ-####)

### Components (metadata) — object: <Object__c>
| Field Label | API Name | Type | Default / Picklist values / Notes |
| --- | --- | --- | --- |
| <Label> | <API_Name__c> | <Type> | <notes> |

### FLS
| Permission Set / Profile | Access |
| --- | --- |
| <Custom CPQ User perm set> | Read + Edit |
| <Custom CPQ Admin perm set> | Read + Edit |
| System Administrator (profile) | Read + Edit |

### Layout
<Object> → **<Layout name>** (add the N fields).

### Release
| Item | Link |
| --- | --- |
| PR | _paste PR link_ |
| Merge Label | _paste merge label_ |
```

## PDS template (tabular, step-by-step for DevOps)

Lightweight PDS (verify-only) = a single step table. **Data PDS** must give DevOps BOTH delivery options and be self-contained:

```markdown
## PDS — <topic> (PROJ-####)

| Expected result | Count |
| --- | --- |
| <object/records> | <n> |

## Option A — Anonymous Apex (recommended; resolves ProductCode→Id automatically)
| # | Step |
| --- | --- |
| 1 | Run prerequisite script(s) … |
| 2 | Setup → Developer Console → Execute Anonymous → paste A.1 → Execute (or `sf apex run --file <path> --target-org <ORG>`) |
| 3 | Confirm debug line: `<expected>` |

**A.1 — Script** (repo: `scripts/apex/.../<file>.apex`):
​```apex
<FULL runnable script inlined here so the ticket is self-contained>
​```

## Option B — Data Loader (sheets / CSV)
| File | Object | Operation | Match field |
| --- | --- | --- | --- |
| <file>.csv | <Object> | Insert/Upsert | <field> |

| # | Step |
| --- | --- |
| 1 | Export Product2 (Id, ProductCode) → ProductCode→Id VLOOKUP |
| 2..n | Map ProductCode→Id for every lookup / Id-string field, then load each file |

⚠️ Lookups + `;`-Id-string fields store **Ids**, so Option B needs ProductCode→Id mapping. Prefer Option A.

## Verify (either option)
| # | Check (SOQL / UI) | Expected |
| --- | --- | --- |
```

**Rules for the data PDS:**
- Inline the **full** Apex script (DevOps may not have repo access); keep a matching real file in `scripts/apex/...`.
- Generate CSV sheets in `scripts/data/...`, then create real **Google Sheets** so they can be linked on the ticket: `create_file` (Google Drive MCP) with `contentMimeType: "text/csv"` + `textContent: <csv>` → auto-converts `text/csv` to a Google Sheet; put the returned `viewUrl` in the Option B table. (No Jira attachment API is available via MCP — link Google Sheets instead.) Note the sheet owner so DevOps can request access.
- **Never put org-specific record Ids in the ticket** — the script/sheets use ProductCode and resolve ProductCode→Id in the target org. When exporting org data to a sheet, resolve stored Ids back to ProductCode (build the Id→Code map keyed by both 18- and 15-char Ids if your org stores 15-char Ids anywhere).
- Data load on junction/config objects with no External Id uses **scoped delete + insert** (delete only rows for the parents in scope, then insert the full desired set) — idempotent and re-runnable; row Ids change each run, which is fine because nothing references them by Id.

## Integration with other skills

| Event | Also run |
|-------|----------|
| Sandbox deploy | `sfdc-promotion-workflow` track-deploy → then `sync-from-work.py` |
| Prepare commit | Sync Jira before `prepare-feature-branch.py` |
| Multi-part runbook | Mirror sections A→Dev Task, B→PDS Data, C→PDS Manual |

## Local files (per project)

| File | Purpose |
|------|---------|
| `.cursor/jira-subtasks/config.json` | Project + parent story |
| `.cursor/jira-subtasks/tracker.json` | Subtask keys, components, PDS steps |
| `.cursor/jira-subtasks/dev-task.md` | Dev Task body (markdown) |
| `.cursor/jira-subtasks/pds-data.md` | PDS Data body |
| `.cursor/jira-subtasks/pds-permissions-layout.md` | PDS Permissions body |

Do not commit tracker if it contains sensitive deploy notes — or commit if team wants shared runbook.

## Rules

- **Always** update Dev Task when metadata is pushed to sandbox
- **Never** put org-specific record IDs in Dev Task — only in PDS Data with script references
- **Create PDS** for anything DevOps must do manually in higher envs
- **Match naming**: `Dev Task — …`, `PDS (Data) — …`, `PDS (QCP) — …`
- **Re-sync** before user asks to prepare commit or promotion

## Acceptance criteria — do not skip non-field work

When implementing a Jira story, read **every** acceptance criterion — not only custom fields:

| AC type | Repo / org artifact | Often missed |
|---------|---------------------|--------------|
| Custom fields | `objects/**/fields/*.field-meta.xml` | — |
| **Page layouts** | `layouts/<Object>-<Layout>.layout-meta.xml` | Checkbox / config fields left off CPQ layouts |
| FLS | permission sets / profiles | — |
| Tabs, apps, record types | respective metadata | — |
| Data scripts | `scripts/apex/`, `scripts/data/` | PDS not updated |

**Layout rule:** If AC says "add fields to layout", confirm whether **all** new fields or **only specific types** (e.g. checkboxes only) — quote the story verbatim in Dev Task → Layout section.

## Post-dev validation (required when user asks you to develop)

After metadata changes and sandbox deploy, **automatically** run AC validation before marking work complete:

1. **Repo checks** — fields exist, layouts include required API names, manifest lists new components.
2. **Org checks** (when sandbox available) — deploy succeeded; retrieve or query confirms layout/field in target org.
3. **Jira** — update Dev Task metadata table + comment with deploy ID and validation result.

Project helper (extend per story):

```bash
python3 tools/sfdc-knowledge-swarm/validate_jira_ac.py PROJ-1001
python3 tools/sfdc-knowledge-swarm/validate_jira_ac.py PROJ-1001 --target-org MY_SANDBOX
```

If validation fails, fix gaps before telling the user the story is done.

See [reference.md](reference.md) for classification rules and Jira API details.
