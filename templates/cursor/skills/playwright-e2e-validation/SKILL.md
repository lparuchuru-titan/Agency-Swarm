---
name: playwright-e2e-validation
description: >-
  Auto-generate Playwright E2E tests and run validation after development work.
  Detects changed LWC, Apex, and UI metadata, scaffolds Playwright if missing,
  writes specs to e2e/generated, runs LWC Jest, Apex tests, and Playwright.
  Use when completing a feature, before commit/PR, after deploying to sandbox,
  or when the user asks for E2E tests, Playwright scripts, UI validation, or
  test automation for Salesforce Lightning or web development.
---

# Playwright E2E Validation

After development work, auto-generate Playwright tests and run validation.

## Context (folder + sandbox org)

E2E tests run against the org connected to **the current project folder**:

```bash
python3 ~/.cursor/skills/_shared/show-context.py
```

- `SF_USERNAME` / `SF_PASSWORD` for that sandbox instance
- Source path from `sfdx-project.json` for detecting changed LWCs/Apex

**Agent:** Scaffold and validate in whichever DX project folder is active — do not assume a fixed project name or path.

Global skill paths:
- **Cursor:** `~/.cursor/skills/playwright-e2e-validation/`
- **Claude:** `~/.claude/skills/playwright-e2e-validation/`

## When to run (automatic)

Run this skill when:
- User finishes implementing LWC, Apex UI controller, tab, or page
- User asks to validate, test, or generate Playwright scripts
- User says "prepare commit", "ready for PR", or "deployed to sandbox"
- Before promotion workflow (pair with `sfdc-promotion-workflow`)

## Agent workflow

### Step 1 — Detect project

Salesforce DX project (`sfdx-project.json`) or repo with `playwright.config.js`.

Optional per-project config: `.cursor/playwright-e2e/config.json` (copy from `config.example.json`).

### Step 2 — Scaffold if missing

```bash
python3 ~/.cursor/skills/playwright-e2e-validation/scripts/scaffold.py
```

Creates `playwright.config.js`, `e2e/auth.setup.js`, `e2e/home.spec.js` (matches a typical SFDX e2e layout).

### Step 3 — Generate Playwright specs from changes

```bash
python3 ~/.cursor/skills/playwright-e2e-validation/scripts/generate-specs.py --write
```

Reads git-changed files under source (`force-app/main/default` or `Master/main/default`):
- **LWC** → `e2e/generated/{component}.spec.js` with tab/record-page navigation
- **Apex controller** → maps to `{ClassName}Test` for Apex test run
- **Tab metadata** → links to LWC tab tests

Preview plan without writing:

```bash
python3 ~/.cursor/skills/playwright-e2e-validation/scripts/generate-specs.py --json
```

### Step 4 — Run full validation

```bash
~/.cursor/skills/playwright-e2e-validation/scripts/run-validation.sh
```

Runs in order:
1. **LWC Jest** — `npm run test:unit` (if package.json has it)
2. **Apex tests** — `sf apex run test --tests ClassNameTest,...`
3. **Playwright** — `npx playwright test e2e/generated e2e/home.spec.js` (if `SF_USERNAME` + `SF_PASSWORD` set)

### Step 5 — Report results

Summarize pass/fail/skipped for each layer. If Playwright skipped (no creds), tell user how to run:

```bash
export SF_USERNAME='user@company.com.sandbox'
export SF_PASSWORD='...'
export SF_LOGIN_URL='https://test.salesforce.com'
export E2E_RECORD_ID='a0Q...'   # optional, for record-page LWCs
npm run test:e2e
```

## Generated spec patterns (Salesforce Lightning)

| LWC target | Playwright navigation |
|------------|----------------------|
| `lightning__Tab` | `/lightning/n/{TabApiName}` |
| `lightning__RecordPage` | `/lightning/r/{Object}/{recordId}/view` |
| App / Home page | Start at `/lightning/page/home` + TODO navigate |

Component selector: `c-{kebab-case-lwc-name}` (e.g. `myQuoteLineView` → `c-my-quote-line-view`).

## Salesforce E2E auth (team standard)

Matches your production metadata repo's `e2e/auth.setup.js`:
- Setup project runs first, saves `e2e/.auth/user.json`
- Chromium project depends on setup
- Instance URL saved to `e2e/.auth/instance-url.txt`

## What to generate manually (agent edits after scaffold)

Generated specs are **starting points**. After generation, improve:
- Specific assertions (table rows, buttons, labels from user story)
- `data-testid` attributes in LWC HTML for stable selectors
- Record IDs via `E2E_RECORD_ID` env var
- Multi-step flows (create quote → open tab → verify lines)

Prefer:
```javascript
await page.getByRole('button', { name: 'Save' });
await page.getByLabel('Quantity');
```
Avoid brittle XPath. Use `timeout: 90_000` for Lightning shell load.

## Non-Salesforce web projects

If no `sfdx-project.json`, scaffold Playwright and generate specs from changed `.tsx/.jsx/.vue` files using generic page-load tests. Extend `generate-specs.py` or write specs in `e2e/` by hand following Playwright best practices.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/scaffold.py` | Create Playwright config + auth setup |
| `scripts/generate-specs.py` | Generate `e2e/generated/*.spec.js` from git changes |
| `scripts/run-validation.sh` | Jest + Apex + Playwright pipeline |
| `scripts/lib.py` | Shared detection helpers |

## Do not

- Commit `e2e/.auth/` (credentials/session)
- Skip Apex tests when only controller changed
- Push generated tests without reviewing assertions
- Use production credentials in local Playwright runs

## Pair with other skills

- `sfdc-metadata-sync` — retrieve before testing against org state
- `sfdc-promotion-workflow` — run validation before `prepare-feature-branch.py`

See [reference.md](reference.md) for selector tips and npm script template.
