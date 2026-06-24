---
name: sfdc-metadata-sync
description: >-
  Automatically retrieve Salesforce metadata from an org, detect whether local
  is empty (full sync) or has existing source (delta sync), compare local vs org,
  and pull only changed components. Use when the user asks to retrieve, pull,
  sync, or refresh metadata from a Salesforce org, get metadata delta, compare
  local vs org, or set up initial metadata download for an empty project.
---

# Salesforce Metadata Sync

Automatically pull metadata from a Salesforce org into the **current Salesforce DX project folder**. Handles first-time full retrieve (empty local) and ongoing delta retrieve (org changes only).

## Context (folder + sandbox org)

Skills auto-detect from the **folder you are working in**:

```bash
python3 ~/.cursor/skills/_shared/show-context.py
```

- Project root: nearest `sfdx-project.json` walking up from cwd
- Target org: `sf config get target-org` for that project (override with `--target-org` or `.cursor/sfdc-project/config.json`)

**Agent:** Always run scripts from the user's active sandbox project directory. Never hardcode org aliases or absolute paths.

## Skill Location

This skill is installed globally at `~/.cursor/skills/sfdc-metadata-sync/` and is available in **all Cursor projects**.

| Location | Path | Scope |
|----------|------|-------|
| Personal (global) | `~/.cursor/skills/sfdc-metadata-sync/` | All projects |
| Project (optional) | `.cursor/skills/sfdc-metadata-sync/` | Repo only, shared with team |

Do **not** put skills in `~/.cursor/skills-cursor/` — that folder is for Cursor built-in skills.

## Script Path

Always use the global script path (works from any Salesforce project):

```bash
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh
```

The script finds the project root by walking up from the current directory until it finds `sfdx-project.json`.

## When to Run

Run this skill when the user wants to:
- Pull/retrieve/sync metadata from an org
- Compare local source vs org and get the delta
- Initialize an empty local project from an org
- Refresh local metadata without manual package.xml editing

## Prerequisites

1. Salesforce CLI (`sf`) installed and on PATH
2. Target org authenticated (`sf org list` shows the org)
3. Run from inside the Salesforce DX project (or pass `--project-root`)

## Quick Start

```bash
# Use default target org from sf config
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh

# Specify org alias
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh --target-org my-sandbox

# Force full retrieve even if local has files
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh --full

# Preview delta only (no retrieve)
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh --preview-only
```

## Agent Workflow

When the user asks to sync metadata, **run the script automatically** — do not ask them to retrieve manually.

### Step 1: Verify prerequisites

```bash
sf --version
sf org display --target-org <org> 2>/dev/null || sf org list
```

If no org is specified, use the default from `sf config get target-org` or ask the user once.

### Step 2: Run sync

```bash
~/.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh --target-org <org>
```

The script auto-detects:
- **Empty local** → full batched retrieve using `manifest/batches/package-*.xml`
- **Local has source** → delta retrieve via `sf project retrieve preview` + generated `manifest/delta-package.xml`

### Step 3: Report results

After the script completes, summarize for the user:
- Mode used (full vs delta)
- Number of components retrieved
- Conflicts (if any) — do not auto-resolve; ask user preference
- Local-only changes (`toDeploy` from preview) — not retrieved, may need deploy
- Org-deleted components (`toDelete`) — still in local, user may want to remove

Read `manifest/delta-report.json` in the project if it exists for structured output.

### Step 4: Handle failures

| Failure | Action |
|---------|--------|
| Batch retrieve timeout | Script uses `--wait 120`; if still failing, run that batch individually |
| Auth error | `sf org login web --alias <alias>` |
| Conflicts in preview | Show conflict list; retrieve with `--ignore-conflicts` only if user confirms |
| Empty delta | Tell user local is in sync with org |

## Project Conventions

Paths below are relative to the **Salesforce DX project root** (where `sfdx-project.json` lives):

| Path | Purpose |
|------|---------|
| `force-app/main/default/` | Default package directory |
| `manifest/package.xml` | Full metadata type manifest (`members *` per type) |
| `manifest/batches/package-*.xml` | Batched manifests for large full retrieves |
| `manifest/delta-package.xml` | Generated manifest for delta retrieves (do not commit) |
| `manifest/delta-report.json` | Generated sync report (do not commit) |
| `.forceignore` | Excluded from retrieve preview |

API version: read from `sfdx-project.json` `sourceApiVersion`.

## Full Retrieve (First Time / Empty Local)

Triggered when `force-app/main/default` has no `*-meta.xml` files, or when `--full` flag is passed.

1. Loops through `manifest/batches/package-*.xml` in sorted order
2. Runs `sf project retrieve start --manifest <batch> --target-org <org> --wait 120`
3. Logs output to `manifest/batches/log-<batch-name>.txt`

If `manifest/batches/` is missing, fall back to single manifest:

```bash
sf project retrieve start --manifest manifest/package.xml --target-org <org> --wait 120
```

For very large orgs, split `manifest/package.xml` into batches (~5-10 metadata types per file) in `manifest/batches/`.

## Delta Retrieve (Local vs Org)

Triggered when local already has metadata files.

1. `sf project retrieve preview --json --concise --target-org <org>`
2. Parse `result.toRetrieve` → build `manifest/delta-package.xml`
3. If components found: `sf project retrieve start --manifest manifest/delta-package.xml`
4. If zero components: local matches org for tracked types

Preview JSON fields:
- `toRetrieve` — org differs from local; will be pulled
- `toDeploy` — local differs from org; not pulled (user may deploy)
- `toDelete` — removed from org but still local
- `conflicts` — both changed; needs user decision

## Do Not

- Manually edit `manifest/delta-package.xml` — it is generated each run
- Use `--ignore-conflicts` without user confirmation
- Commit `manifest/delta-package.xml` or `manifest/delta-report.json`

## Additional Resources

- Script details: `~/.cursor/skills/sfdc-metadata-sync/scripts/README.md`
