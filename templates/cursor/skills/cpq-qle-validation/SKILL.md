---
name: cpq-qle-validation
description: >-
  Validate Salesforce CPQ quote-line behavior (field editability, quantity
  persistence through Calculate, pricing/allotment math, ramp/segments) on the
  REAL Standard Quote Line Editor via Playwright, because headless SBQQ
  calculation NPEs org-wide. Use whenever verifying that a CPQ config/QCP change
  actually works end-to-end in the QLE — field is editable, an edit sticks after
  Calculate, Net/Total scales, no opType errors. Enforces the calibration gate,
  fresh-quote rule, and parent-control row that keep these tests honest.
---

# CPQ Standard-QLE Validation (Playwright)

## Role

Prove a CPQ change behaves correctly for a rep in the **Standard Quote Line Editor**
(`/apex/SBQQ__sb`) — not just that metadata/QCP saved. Every CPQ feature
(qty-lock, onboarding editability, VLC term pricing, allotment calc, ramp) is
validated this way. There are already ~40 `e2e/*.spec.js` files following this
pattern; reuse them, don't reinvent.

## The one rule that dictates everything

**Headless SBQQ calculation NPEs org-wide in these orgs.** So you CANNOT validate
by calling the calculator/API headlessly. You MUST drive the real Standard QLE in
a browser (Playwright), which runs the calculator the way a rep does. This is why
the whole harness exists.

## Setup / auth (do this every run)

The CLI `sf org display` token is often `[REDACTED]`. Get a real token and pass it
via env so Playwright's `auth.setup` uses the env path:

```bash
export SF_TARGET_ORG="<username>"                 # e.g. lparuchuru@your project.com.your project
export SF_ACCESS_TOKEN=$(sf org auth show-access-token --target-org "$SF_TARGET_ORG" --json \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['accessToken'])")
export SF_INSTANCE_URL=$(sf org display --target-org "$SF_TARGET_ORG" --json \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['instanceUrl'])")
export PW_HEADLESS=true
npx playwright test e2e/<spec>.spec.js --reporter=line --workers=1
```

Long specs auto-background — poll the task output, don't block.

## The detector (field editability / quantity persistence)

The modern SBQQ line grid renders a numeric cell as **static text** and only spawns
an editable `<input>` when an editable cell is activated. So:

- **Editable?** dblclick-sweep a few X positions across the target column at the row Y;
  a cell is EDITABLE iff a focused, non-readonly `<input>` appears **in that column's
  x-band** (Quantity ≈ x 640; band `[600,705]`) within ±25px of the row Y. Piercing
  shadow roots via `document.activeElement` is the reliable focus signal.
- **Persists?** For an edit-through-Calculate test, type with **REAL keystrokes**
  (`page.keyboard.type`, not a synthetic value set — frameworks ignore synthetic
  input events), press Tab, click **Calculate**, then re-read the cell. Confirm the
  DB value after Save via SOQL for Net/Total scaling.

## Two guardrails that keep the test HONEST (non-negotiable)

1. **Calibration gate.** A run is only trustworthy if a **known-editable control row
   reads EDITABLE and a known-locked row reads LOCKED** in the SAME run — e.g. the
   bundle **parent line** (editable) + a **usage meter** (locked by the qty-lock rule).
   If the control fails, the "LOCKED"/"REVERTED" reading is a dead-edit false
   negative, not a real result. Always include a parent-control row.
2. **Fresh-quote rule.** Config changes (ProductOption Type/Quantity, feature counts)
   only take effect on quote lines **created AFTER** the change. Old / data-loaded
   test quotes bake in their creation-time behavior and give false failures. Build a
   **fresh quote through the configurator** to validate config changes. (For pure
   QCP editability changes, existing quotes are fine — QCP is evaluated live at render.)

## Reusable specs (in `e2e/`)

- `onboarding-edit-persist.spec.js` — type qty in grid (real keys) → Calculate → read back; multi-row with parent control. Env `E2E_EDIT={"id","rows":[{code,newQty}]}`.
- `onboarding-qty-mtd.spec.js` — report-only editability probe with the calibration gate. Env `E2E_OB_QUOTES=[{tag,name,id,rows:[{code,role}]}]`.
- `std-config-build.spec.js` — build a FRESH quote via the Standard configurator (Add Products → Configure → Save) so option config is exercised.
- `std-edit-save.spec.js` — edit → Calculate → Save, then verify via SOQL.


## Related skills

- `sfdc-qcp-editor` — the QCP changes this skill validates
- `playwright-e2e-validation` — generic auto-generation of E2E specs (this skill is the CPQ-QLE-specific technique)
- `your project-bundle-builder` — the bundle config being validated
