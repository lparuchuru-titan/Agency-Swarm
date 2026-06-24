---
name: sfdc-promotion-workflow
description: >-
  Track Salesforce sandbox deployments and promote validated changes to higher
  environments via SFDC-CRM-SFDX. Creates feature branches from latest NextGenDev,
  copies metadata from sandbox project to Master/main/default, and prepares commits
  and PRs. Use when deploying to sandbox, tracking sandbox changes, preparing a
  commit, creating a feature branch, promoting to NextGenQA/UAT, or moving code
  through servicetitan/SFDC-CRM-SFDX.
---

# SFDC Promotion Workflow

Track sandbox deployments and promote to **SFDC-CRM-SFDX** using the team's branch/PR pattern.

## Context (folder + sandbox org)

All paths and org alias are resolved from the **active project folder**:

```bash
python3 ~/.cursor/skills/_shared/show-context.py
```

| Auto-detected | How |
|---------------|-----|
| Sandbox project | `sfdx-project.json` from cwd |
| Source path | `force-app/...` or `Master/...` from sfdx-project.json |
| Target org | Project `sf config get target-org` |
| Promotion repo | Sibling `SFDC-CRM-SFDX` or `SFDC_PROMOTION_REPO` env |

Optional overrides: `.cursor/sfdc-project/config.json`

**Agent:** Run from the sandbox folder the user is connected to. Pass `--target-org` only when user names a different org.

## Skill location

Global skill: `~/.cursor/skills/sfdc-promotion-workflow/`

Per-project config (create once per sandbox workspace): `.cursor/sfdc-promotion/config.json`

## How the team promotes (SFDC-CRM-SFDX)

| Stage | Branch | Notes |
|-------|--------|-------|
| Sandbox dev | Local sandbox (e.g. NEXTGEN2) | Deploy with `sf project deploy` |
| Feature work | `SFDCLQ-7591-Pantheon-Bundles` | Branch from latest `NextGenDev` |
| PR merge | → `NextGenDev` | Commit format: `C-{branch}-V1` |
| Higher env | `NextGenDev-To-NextGenQA-Merge_*` | Team merge branches to `NextGenQA` |
| Production | `master` | AutoRABIT commits |

**Path mapping** (critical):

| Sandbox project | Promotion repo |
|-----------------|----------------|
| `force-app/main/default/` | `Master/main/default/` |

**Repos (default for this user):**

- Sandbox: `/Users/lakshmikanthparuchuru/SFDC/SFDC NextGen2/NEXTGEN2`
- Promotion: `/Users/lakshmikanthparuchuru/SFDC/SFDC-CRM-SFDX`

## First-time setup (per sandbox project)

Copy the example config into the **sandbox project** (not the skill folder):

```bash
mkdir -p .cursor/sfdc-promotion
cp ~/.cursor/skills/sfdc-promotion-workflow/config.example.json .cursor/sfdc-promotion/config.json
# Edit paths, epic, org alias
```

## Agent workflow

### After sandbox deploy — track changes

Whenever the user deploys metadata to sandbox, **automatically track** the deployed files:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py \
  --ticket SFDCLQ-7592 \
  --description "Product2 bundle fields" \
  --deploy-command "sf project deploy start ..." \
  objects/Product2/fields/Bundle_SKU_Flag__c.field-meta.xml
```

Or track directories:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py \
  -t SFDCLQ-7591 -d "Pantheon CPQ metadata" \
  objects/Bundle_Definition__c permissionsets/NextGen_Quoting_Access_Test.permissionset-meta.xml
```

Or from git diff in sandbox project:

```bash
cd <sandbox-project>
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py --from-git -t SFDCLQ-7591
```

Updates:
- `.cursor/sfdc-promotion/sandbox-tracker.json`
- `.cursor/sfdc-promotion/sandbox-changelog.md`

### Check status

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/status.py
```

Run from sandbox project root (or any subdirectory).

### Prepare feature branch — when user asks

When the user says "prepare commit", "create feature branch", or "promote to repo":

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/prepare-feature-branch.py \
  --ticket SFDCLQ-7591 \
  --description "Pantheon-Bundles"
```

This **always**:
1. `git fetch` + `git pull` latest `NextGenDev` in SFDC-CRM-SFDX
2. Creates/checks out feature branch on top of latest base
3. Copies tracked files: sandbox `force-app/` → repo `Master/main/default/`
4. `git add` staged files
5. Writes `last-promotion-summary.md` with PR template

**Does not push or commit** unless user confirms or passes `--commit`.

To commit when ready:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/prepare-feature-branch.py \
  --ticket SFDCLQ-7591 --description "Pantheon-Bundles" --commit
```

Then push and open PR:

```bash
cd /Users/lakshmikanthparuchuru/SFDC/SFDC-CRM-SFDX
git push -u origin SFDCLQ-7591-Pantheon-Bundles
gh pr create --repo servicetitan/SFDC-CRM-SFDX \
  --base NextGenDev \
  --head SFDCLQ-7591-Pantheon-Bundles \
  --title "SFDCLQ-7591: Pantheon 2026 Max Bundles CPQ metadata"
```

Only push/create PR when the user explicitly asks.

## Branch naming conventions

Match team patterns:

| Pattern | Example |
|---------|---------|
| `{ticket}-{description}` | `SFDCLQ-7591-Pantheon-Bundles` |
| `local-{ticket}-V1` | `local-SFDCLQ-7592-V1` |
| Short feature name | `nextgen-quotereadservice` |

Commit message: `C-{branch-name}-V1` (e.g. `C-SFDCLQ-7591-Pantheon-Bundles-V1`)

## Tracking files (per sandbox project)

| File | Purpose |
|------|---------|
| `.cursor/sfdc-promotion/config.json` | Paths, branches, epic, org |
| `.cursor/sfdc-promotion/sandbox-tracker.json` | Deploy + promotion history |
| `.cursor/sfdc-promotion/sandbox-changelog.md` | Human-readable log |
| `.cursor/sfdc-promotion/last-promotion-summary.md` | Last branch/PR summary |

Do not commit tracker files unless the team wants shared changelog in repo.

## Rules

- **Always pull latest base branch** before creating feature branch
- **Never** copy into wrong path — always `Master/main/default/` in SFDC-CRM-SFDX
- **Track after every sandbox deploy** so promotion is accurate
- **Do not push** without user confirmation
- **Do not commit** without user confirmation (unless they said "prepare and commit")
- Pantheon / NextGen work targets `NextGenDev` PR base, not `master`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/track-deploy.py` | Record sandbox deployment files |
| `scripts/status.py` | Show pending promotion status |
| `scripts/prepare-feature-branch.py` | Pull latest, branch, copy, stage, optional commit |
| `scripts/lib.py` | Shared helpers |
