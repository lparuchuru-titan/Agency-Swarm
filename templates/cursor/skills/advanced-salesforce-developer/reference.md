# Advanced Salesforce Developer — Reference Protocols

## Process Documentation Protocol

When the user asks to **explain, understand, walk through, analyze, or document** any process, feature, automation, integration, or architecture — produce a formal HTML artifact, not just chat.

Trigger phrases: "how does X work", "explain the X process", "walk me through X", "document X", "I need to understand X".

### Output location & naming
- All docs under `docs/` at repo root — never elsewhere
- Kebab-case filenames: `docs/lead-conversion-process.html`
- Update in place if same topic exists; note revision

### Required sections (standalone HTML, inline CSS, no external deps)
1. Title & metadata — author, date, target org, API version
2. Overview / purpose
3. Scope & actors — profiles, permission sets, external systems
4. Data model — objects, fields (API names), relationships, record types
5. End-to-end process flow — numbered steps through Flows, Apex, validation, approvals, async, integrations; include visual diagram
6. Component inventory — table: Type, API Name, Role, File Path
7. Business logic & rules — branching, formulas, governor limits
8. Integration & security — auth, sharing, CRUD/FLS, USER_MODE
9. Error handling & edge cases
10. Assumptions & open questions

### Grounding
- Read actual `force-app/` metadata first; cite exact API names and paths
- Distinguish verified facts from inferred behavior
- Report doc path and summary after generation

---

## Playwright Automation Protocol

Apply only when the project has Playwright wired (`playwright.config.js`, `e2e/`). Auth via default `sf` CLI org — never hardcode credentials.

When the user asks for **testing** or **UI documentation**, write and **run** Playwright — do not only describe tests.

### Typical project wiring
- `playwright.config.js` — reports → `docs/test-reports/playwright`
- `e2e/global-setup.js` — frontdoor session → `e2e/.auth/state.json`
- `e2e/lib/fixtures.js` — import `{ test, expect }` from here, not `@playwright/test`
- `e2e/lib/doc-capture.js` — `capture(page, name)` → `docs/assets/screenshots/`
- `e2e/tests/*.spec.js` — all specs

### Commands
- `npm run e2e` · `npm run e2e:headed` · `npm run e2e:debug` · `npm run e2e:ui`
- `npm run e2e:codegen` · `npm run e2e:report`
- Prerequisite: `sf org login web` + `sf config set target-org <alias>`

### Testing workflow
1. Read relevant metadata for selectors and expected behavior
2. Author spec under `e2e/tests/` with `../lib/fixtures`
3. Use `page.goto('/lightning/...')` — no `networkidle` on Lightning; wait on elements/URLs
4. Run `npm run e2e`; iterate until green or product failure identified
5. Report pass/fail, report path, traces/screenshots on failure

### Documentation + UI capture workflow
1. Produce HTML doc per Process Documentation Protocol
2. Add capture spec calling `capture(page, '<step>')` at each meaningful UI step
3. Run capture; embed screenshots in the HTML doc
4. Report doc path, image list, capture success
