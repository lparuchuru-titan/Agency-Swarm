---
name: sfdc-promotion-workflow
description: >-
  Track Salesforce sandbox deployments and promote validated changes to higher
  environments via your production metadata repo. Creates feature branches from
  the latest base branch, copies metadata from the sandbox project to the repo's
  package directory, and prepares commits and PRs. Use when deploying to sandbox,
  tracking sandbox changes, preparing a commit, creating a feature branch,
  promoting to QA/UAT, or moving code through your metadata repo.
---

# SFDC Promotion Workflow

Track sandbox deployments and promote to your **production metadata repo** using your team's branch/PR pattern.

## Context (folder + sandbox org)

All paths and org alias are resolved from the **active project folder**:

```bash
python3 ~/.cursor/skills/_shared/show-context.py
```

| Auto-detected | How |
|---------------|-----|
| Sandbox project | `sfdx-project.json` from cwd |
| Source path | `force-app/...` (or your configured package path) from sfdx-project.json |
| Target org | Project `sf config get target-org` |
| Promotion repo | Sibling repo or `SFDC_PROMOTION_REPO` env |

Optional overrides: `.cursor/sfdc-project/config.json`

**Agent:** Run from the sandbox folder the user is connected to. Pass `--target-org` only when user names a different org.

## Skill location

Global skill: `~/.cursor/skills/sfdc-promotion-workflow/`

Per-project config (create once per sandbox workspace): `.cursor/sfdc-promotion/config.json`

## How the team promotes (example pattern — adapt to your repo)

| Stage | Branch | Notes |
|-------|--------|-------|
| Sandbox dev | Local sandbox (e.g. MY_SANDBOX) | Deploy with `sf project deploy` |
| Feature work | `PROJ-1234-short-description` | Branch from latest base branch (e.g. `main` or `develop`) |
| PR merge | → base branch | Commit format per your team convention |
| Higher env | Team merge branches | Promote to QA/UAT branch |
| Production | `master` / `main` | Per your release process |

**Path mapping** (adjust to your repo layout):

| Sandbox project | Promotion repo |
|-----------------|----------------|
| `force-app/main/default/` | `<package-dir>/main/default/` |

**Repos:**

- Sandbox: `/path/to/your-sfdx-project`
- Promotion: `/path/to/your-prod-metadata-repo`

## First-time setup (per sandbox project)

Copy the example config into the **sandbox project** (not the skill folder):

```bash
mkdir -p .cursor/sfdc-promotion
cp ~/.cursor/skills/sfdc-promotion-workflow/config.example.json .cursor/sfdc-promotion/config.json
# Edit paths, epic, org alias, base branch
```

## Agent workflow

### After sandbox deploy — track changes

Whenever the user deploys metadata to sandbox, **automatically track** the deployed files:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py \
  --ticket PROJ-1234 \
  --description "Product2 bundle fields" \
  --deploy-command "sf project deploy start ..." \
  objects/Product2/fields/Example_Flag__c.field-meta.xml
```

Or track directories:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py \
  -t PROJ-1234 -d "CPQ bundle metadata" \
  objects/Bundle_Definition__c permissionsets/Quoting_Access_Test.permissionset-meta.xml
```

Or from git diff in sandbox project:

```bash
cd <sandbox-project>
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/track-deploy.py --from-git -t PROJ-1234
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
  --ticket PROJ-1234 \
  --description "example-bundles"
```

This **always**:
1. `git fetch` + `git pull` latest base branch in the promotion repo
2. Creates/checks out feature branch on top of latest base
3. Copies tracked files: sandbox `force-app/` → repo package directory
4. `git add` staged files
5. Writes `last-promotion-summary.md` with PR template

**Does not push or commit** unless user confirms or passes `--commit`.

To commit when ready:

```bash
python3 ~/.cursor/skills/sfdc-promotion-workflow/scripts/prepare-feature-branch.py \
  --ticket PROJ-1234 --description "example-bundles" --commit
```

Then push and open PR:

```bash
cd /path/to/your-prod-metadata-repo
git push -u origin PROJ-1234-example-bundles
gh pr create --repo your-org/your-prod-metadata-repo \
  --base main \
  --head PROJ-1234-example-bundles \
  --title "PROJ-1234: Example bundle metadata"
```

Only push/create PR when the user explicitly asks.

## Branch naming conventions

Match your team's patterns — example:

| Pattern | Example |
|---------|---------|
| `{ticket}-{description}` | `PROJ-1234-example-bundles` |
| `local-{ticket}-V1` | `local-PROJ-1234-V1` |
| Short feature name | `example-quotereadservice` |

Commit message: `C-{branch-name}-V1` (e.g. `C-PROJ-1234-example-bundles-V1`) — or whatever convention your team uses.

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
- **Never** copy into wrong path — always your repo's `<package-dir>/main/default/`
- **Track after every sandbox deploy** so promotion is accurate
- **Do not push** without user confirmation
- **Do not commit** without user confirmation (unless they said "prepare and commit")
- Feature work targets your configured base branch, not the production branch directly

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/track-deploy.py` | Record sandbox deployment files |
| `scripts/status.py` | Show pending promotion status |
| `scripts/prepare-feature-branch.py` | Pull latest, branch, copy, stage, optional commit |
| `scripts/lib.py` | Shared helpers |
