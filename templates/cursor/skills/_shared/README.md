# Salesforce Skills — Shared Context

All global skills resolve **project folder** and **sandbox org** automatically from where you work.

## Resolution order

1. **Project root** — walk up from current directory until `sfdx-project.json` is found
2. **Default org** — **`.sf/config.json`** in that project (`target-org`) — this is the org you set when opening/configuring the project
3. **Source path** — from `sfdx-project.json` `packageDirectories`
4. **Optional overrides** — `.cursor/sfdc-project/config.json` (only if `targetOrgAlias` is set)

### Org priority (important)

| Priority | Source |
|----------|--------|
| 1 | CLI `--target-org` flag |
| 2 | **Project `.sf/config.json`** ← use this when you open a project |
| 3 | `.cursor/sfdc-project/config.json` override |
| 4 | `sf config get target-org` fallback |

Each sandbox folder (e.g. DEV, QA, UAT) has its own `.sf/config.json`. Skills always pick **that project's** default org.


## Show context (run from any subfolder of a DX project)

```bash
python3 ~/.cursor/skills/_shared/show-context.py
```

## Optional project config

```bash
mkdir -p .cursor/sfdc-project
cp ~/.cursor/skills/_shared/config.example.json .cursor/sfdc-project/config.json
```

Only set values you need to override:

| Field | When to set |
|-------|-------------|
| `targetOrgAlias` | Force a specific org instead of project default |
| `promotionRepoRoot` | If the promotion repo is not a sibling folder |
| `parentStoryKey` | Current Jira story for subtask tracking |
| `defaultBaseBranch` | Promotion repo base branch |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SFDC_PROMOTION_REPO` | Path to the promotion repo when not auto-found |

## Agent rule

Before any skill runs deploy/retrieve/sync/promotion/jira:

1. `cd` to the user's **active sandbox project folder** (where `sfdx-project.json` lives)
2. Run `show-context.py` or let skill scripts auto-resolve
3. Use resolved `targetOrgAlias` in all `sf` commands (`--target-org`)
4. Never assume a specific org alias or hardcoded paths unless user explicitly names them

## Skills using shared context

- `sfdc-metadata-sync`
- `sfdc-promotion-workflow`
- `jira-subtask-workflow`
- `playwright-e2e-validation`
