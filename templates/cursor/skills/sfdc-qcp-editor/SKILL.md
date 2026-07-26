---
name: sfdc-qcp-editor
description: >-
  Safely edit the Salesforce CPQ QuoteCalculatorPlugin (SBQQ__CustomScript__c
  "QuoteCalculatorPlugin") — isFieldVisibleForObject / isFieldEditableForObject /
  onBeforeCalculate / overrideUsageQuoteLinesPrice, and the loaded-field lists.
  Use for any QCP rule add/change/revert. Enforces the backup → char-cap
  measure → anchor-based additive splice → REST PATCH → verify-transpiled
  protocol, the 131,072-byte cap, the /* */-comments-only transpiler rule, and
  the "QCP is manual per-env, never via PR" promotion rule.
---

# SFDC QCP Editor (QuoteCalculatorPlugin)

## Role

Change the CPQ calculator plugin without breaking the org. The QCP is a single
shared `SBQQ__CustomScript__c` record whose `SBQQ__Code__c` (source) auto-transpiles
to `SBQQ__TranspiledCode__c` on save. A bad edit silently breaks calculation
**org-wide** (every quote), so edits are surgical, backed up, and size-checked.

## Hard constraints (violating any = silent org-wide breakage)

- **Char cap = 131,072 bytes** on BOTH `SBQQ__Code__c` and `SBQQ__TranspiledCode__c`. Source is usually the tight one. A save over cap is silently truncated → engine dies. Measure BEFORE editing.
- **`/* */` block comments ONLY — never `//`.** The transpiler minifies to one line; a `//` comment then comments out everything after it. Re-verify the transpiled CLOB after every PATCH.
- **Surgical additive splice — never overwrite the CLOB** with another org's version. Anchor on an existing verbatim code block; insert relative to it. Different orgs have different baselines.
- **QCP is a MANUAL per-env step** — never promoted via the metadata PR. Each env is edited by hand (env-relative OLD→NEW). It's the standard exception to "metadata via PR."

## The protocol (every edit)

```bash
ORG="<username>"; ID="<QCP record Id>"   # NG2 aAvdy0000000HIbCAM ; QA aAv1P0000004CPCSA2
BK="backups/qcp-<ticket>-$(date +%Y%m%d)"   # (pass date in; scripts can't call Date.now)
mkdir -p "$BK"
# 1. BACKUP source + transpiled
sf data query -o "$ORG" -q "SELECT SBQQ__Code__c, SBQQ__TranspiledCode__c FROM SBQQ__CustomScript__c WHERE Name='QuoteCalculatorPlugin'" --json > "$BK/backup.json"
# 2. MEASURE + BUILD candidate with a python anchor-splice; assert exactly ONE anchor match;
#    assert 131072 - len(new) > margin BEFORE patching (abort if not).
# 3. PATCH source only (transpiles automatically):
sf api request rest "/services/data/v61.0/sobjects/SBQQ__CustomScript__c/$ID" \
  --method PATCH -o "$ORG" --body @patch-body.json      # body = {"SBQQ__Code__c": "<new source>"}
# 4. VERIFY: re-query; confirm new rule present in source AND regenerated in transpiled,
#    and BOTH CLOBs < 131,072.
```

Empty/204 response = success. (`curl` + token gave `INVALID_AUTH_HEADER`; use `sf api request rest`.)

## Method map (where rules live)

- `isFieldVisibleForObject(fieldName, object, ...)` — QLE field visibility.
- `isFieldEditableForObject(fieldName, object, ..., objectName)` — QLE field editability. `objectName=='QuoteLine__c'` branch; first matching `return` wins. Return `true`/`false` explicitly; falling through = undefined → CPQ standard editability (which differs per org — don't rely on it silently).
- `onBeforeCalculate(quote, lines, conn)` — mutate line/quote records before pricing (stamps, per-segment math, list-price writes). The org-proven place to WRITE `SBQQ__ListPrice__c` (price rules don't hold it here).
- `overrideUsageQuoteLinesPrice(...)` — usage-meter net handling (e.g. a ProductCode exclusion list).
- Loaded-field lists `SBQQ__QuoteFields__c` / `SBQQ__QuoteLineFields__c` — NEWLINE/LF-separated, one API name per line, no commas/blank lines. **A rule referencing a field NOT in these lists → FATAL global `opType` crash.** Add fields to the list and activate together.

## Gotchas from real incidents

- **Deterministic two-way returns** when behavior must be identical across orgs whose defaults differ: `return line.SBQQ__Quote__r.MultiTenantDeal__c === true;` (editable iff MT) beats an unlock-only `if(MT) return true;` — the latter is a no-op where the default is already editable.
- **`isFieldEditableForObject` only affects the QLE grid cell** (render). It does NOT stop CPQ from re-asserting a bundle-child quantity on Calculate — that's ProductOption config (`Type`, `Quantity`), not the QCP.
- Pre-measure the target env's actual baseline bytes; NG2 has run within ~26–283 bytes of the cap — trim `/* */` comments before adding.
- After PATCH, if the transpiled didn't change, the save didn't take — investigate before assuming success.
- Back up ANY record before updating; keep the `backups/qcp-*` dir per episode.

## Related skills

- `cpq-qle-validation` — validate the QCP change in the real Standard QLE (headless calc NPEs)
- `sfdc-promotion-workflow` — QCP is the manual per-env exception to PR-based promotion
- `jira-subtask-workflow` — document the QCP change as a PDS (QCP) OLD→NEW step
