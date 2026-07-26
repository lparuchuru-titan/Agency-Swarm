---
name: apex-space-reclaimer
description: >-
  Analyze Salesforce unmanaged Apex for reclaim candidates to free org Apex
  character limit (e.g. 92% → ≤75%). Scores stale classes (last modified ≥7
  years), old API versions, zero coverage, no inbound metadata dependencies,
  backup/temp names. Read-only; prefers UAT. Use when Apex code size is high,
  Setup shows Apex used near limit, or user asks to find unused classes / free
  Apex space / reduce code usage.
---

# Apex Space Reclaimer

Read-only specialist: inventory unmanaged Apex, score likely-dead or low-value classes, produce a reclaim plan toward a target usage % (default **≤75%**).

## When to run

- Apex character / code usage near org limit (e.g. 90%+)
- User asks to find unused Apex, free space, delete dead classes, spring-clean Apex
- Pre-release capacity work before large package installs

## Org choice

| Org | Use |
|-----|-----|
| **Higher sandbox / UAT** (preferred) | Best inventory — closer to prod volume |
| Feature sandbox | Faster iteration; may under-count vs higher envs |
| Production | Only if user explicitly requests; still **read-only** |

Never delete or deploy without explicit user approval in the same message.

## Hard rules

1. **Read-only analysis** — no `sf project deploy`, no destructive changes.
2. **Exclude managed packages** (`NamespacePrefix != null`).
3. **No false deletes** — zero inbound Apex refs ≠ unused (Flows, LWC, schedulers, `Type.forName`, integrations).
4. **Report + plan** — HTML + JSON under `docs/apex-reclaim/`; chat summarizes P1 candidates and chars-to-free.
5. Prefer a higher sandbox / UAT alias when connected.

## Workflow

```bash
cd ~/.cursor/skills/apex-space-reclaimer   # or .cursor/skills/apex-space-reclaimer in the project
node scripts/analyze.mjs -o YOUR_ORG_ALIAS --current-pct 92 --target-pct 75 --stale-years 7 --old-api 45
```

Then:

1. Open the generated HTML report.
2. Triage score ≥ 70 with code owners.
3. Validate candidates (see `reference.md`).
4. Hand safe deletes to `advanced-salesforce-developer` / promotion workflow in a **sandbox first**.
5. Re-run analyzer until projected usage ≤ target.

## Scoring (summary)

| Signal | Weight |
|--------|--------|
| Last modified ≥ 7 years | High |
| API version &lt; 45 (configurable) | Medium–High |
| No inbound `MetadataComponentDependency` | High |
| Zero test coverage (non-test) | Medium |
| Backup/temp/deprecated name | High |
| Invalid / inactive | High |
| Large `LengthWithoutComments` | Boost |

Details: `reference.md`.

## Outputs

- `docs/apex-reclaim/YYYYMMDD-apex-reclaim-<org>.html`
- `docs/apex-reclaim/YYYYMMDD-apex-reclaim-<org>.json`

Chat: chars used, estimated limit, chars to free, top 15 candidates, next validation steps.
