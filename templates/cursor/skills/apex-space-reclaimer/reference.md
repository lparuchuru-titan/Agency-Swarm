# Apex reclaim — practices & validation

Inspired by:

- [Andy Fawcett — Spring Cleaning Apex with Tooling API / SymbolTable](https://andyinthecloud.com/2013/02/02/spring-cleaning-apex-code-with-the-tooling-api/)
- Salesforce Tooling `MetadataComponentDependency` + `ApexCodeCoverageAggregate`
- Salesforce Code Analyzer unused-method / unused-type rules (graph-based; complement this inventory)

## What counts toward the limit

Unmanaged **ApexClass** + **ApexTrigger** characters (`LengthWithoutComments`).  
**Test classes count.** Managed package Apex does **not**.

Org limit varies (base ~6MB historically; many enterprises have increases). This tool estimates limit from `currentPct` if `--limit-chars` is omitted:

`limit ≈ totalUnmanagedChars / (currentPct / 100)`

## Heuristics (why these)

| Heuristic | Rationale |
|-----------|-----------|
| Last modified ≥ 7 years | Long dormancy → likely abandoned (confirm with owners) |
| Old API version (&lt; 45 default) | Legacy surface; often paired with unused integrations |
| No inbound metadata deps | Nothing in org metadata references the type name |
| Zero coverage | Never executed by tests — often dead or unreachable |
| `*Backup*`, `*_Old`, `tmp`, `zzz_` names | Explicit scratch / abandoned copies |
| Invalid / Inactive | Safe first deletes after backup |

## False positives (always check)

Before delete, search / query for:

1. **Flows** — InvocableMethod, Apex Action
2. **LWC / Aura / VF** — controller / extension / import
3. **Scheduled / Batch / Queueable** jobs in Setup
4. **Email services**, outbound messages, REST/SOAP public classes
5. **Dynamic Apex** — `Type.forName`, string-based `JSON.deserialize`
6. **Managed subscriber** overrides / global interfaces
7. **Production-only** jobs not present in UAT

```bash
# Example local ripgrep after retrieve
rg -n "ClassNameHere" force-app manifest --glob '!**/staticresources/**'
```

```sql
-- Tooling: who references this class?
SELECT MetadataComponentName, MetadataComponentType
FROM MetadataComponentDependency
WHERE RefMetadataComponentName = 'ClassNameHere'
```

## Reclaim playbook (92% → 75%)

1. Run analyzer on **UAT** with `--current-pct 92 --target-pct 75`.
2. Batch 1: invalid + backup/temp names (highest confidence).
3. Batch 2: stale (≥7y) + no inbound deps + zero coverage.
4. Batch 3: old API + low refs (needs owner review).
5. After each batch: sandbox delete → tests → promote → re-measure.

Do **not** mass-delete test classes solely to free space without replacing coverage elsewhere — org deploy coverage gates still apply.

## Platform limits in this analyzer

- `MetadataComponentDependency` returns at most ~2000 rows per Tooling query. We slice by `MetadataComponentType` to widen coverage; orphan detection remains a **heuristic**.
- Prefer owner review + `rg` / Setup dependency UI before delete.

## Related agents

- `org-analyst` — broader health / debt
- `pr-reviewer` — gate any delete PR
- `sfdc-promotion-workflow` — promote approved removals
- `advanced-salesforce-developer` — implement destructive changes safely
