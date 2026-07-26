---
name: pr-reviewer
description: >-
  Structured Salesforce PR/changeset review with APPROVE / REQUEST CHANGES / BLOCK. Use before deploy.
---

# PR Reviewer Skill

## Role
Automated code quality gate for all Salesforce changes before any deployment.
Produces a structured review with a clear **APPROVE**, **REQUEST CHANGES**, or **BLOCK** decision.

## Lifecycle position
**Review** — runs after every implementation and before any sandbox/UAT/production deploy.

## Decision criteria

| Decision | Condition |
|---|---|
| **APPROVE** | Zero P1 issues. Zero P2 issues. Coverage ≥85%. |
| **REQUEST CHANGES** | P2 issues present but no P1 blockers. Coverage between 75–84%. |
| **BLOCK** | Any P1 issue present. OR coverage < 75% on modified classes. |

## P1 Blockers (BLOCK if any present)

- SOQL inside a `for` loop
- DML inside a `for` loop
- `without sharing` without a documented reason in the same file
- Missing CRUD/FLS enforcement on any user-facing data operation
- Hardcoded record ID (15 or 18 char Salesforce ID in a string literal)
- Test coverage < 75% on any modified Apex class
- `@isTest(SeeAllData=true)` on any new test class
- Flow with a Get Records element and no null-check branch
- Flow with no fault path on any DML element
- `ConnectedApp` or `NamedCredential` credentials exposed in source

## P2 Required Changes (REQUEST CHANGES if any present)

- Business logic directly in a trigger body (no handler delegation)
- Multiple triggers on the same object and event
- Apex method > 50 lines
- Apex class > 300 lines (flag for discussion)
- Missing null checks on `list.get(0)` or query result usage
- `System.debug` statements in production code paths
- Tests without assertions or with only `System.assert(true)`
- Tests not covering a negative / error scenario
- LWC with no error handling on an imperative Apex call
- Deprecated `@future` used where `Queueable` is more appropriate
- New fields deployed without FLS on relevant permission sets

## P3 Suggestions (optional — note in review)

- Method could be extracted for reuse
- Magic string should be a Custom Label or CMDT value
- Comment missing on non-obvious business logic
- Could use `WITH USER_MODE` instead of manual FLS check
- Flow could replace simple trigger logic (or vice versa — flag overlap)

## Static analysis Grep patterns

```bash
# SOQL in loop
rg "for\s*\(" --multiline -A3 force-app/ | grep -i "SELECT"

# DML in loop
rg "for\s*\(" --multiline -A5 force-app/ | grep -iE "insert|update|delete|upsert"

# without sharing
rg "without sharing" force-app/

# Hardcoded IDs (15/18 char)
rg "'[0-9A-Za-z]{15,18}'" force-app/

# seeAllData
rg "SeeAllData\s*=\s*true" force-app/

# System.debug
rg "System\.debug" force-app/
```

## Coverage check

```bash
sf apex run test --class-names <TestClass1,TestClass2> \
  --code-coverage --result-format human --target-org <alias>
```

## Review output format

```markdown
## PR Review — <branch or title>
**Decision: APPROVE | REQUEST CHANGES | BLOCK**
Reviewed: <YYYY-MM-DD>
Reviewer: pr-reviewer agent

### P1 Blockers
- None  OR  - `ClassName.cls` line 42: SOQL inside for loop (DML_IN_LOOP)

### P2 Required Changes
- `ClassName.cls`: no handler delegation in trigger body
- `MyTest.cls`: no negative test scenario

### P3 Suggestions
- `ServiceClass.cls` method `doWork()` is 68 lines — consider extraction

### Test Coverage
| Class | Coverage |
|---|---|
| MyClass | 91% |
| MyTriggerHandler | 87% |

### Summary
<2–3 sentence overall assessment of the changeset quality and readiness.>
```

Save to `docs/reviews/YYYYMMDD-pr-review-<branch>.md`.

## Escalation

- Architecture disagreements → `sfdc-cta-mentor`
- Implementation fixes required → `advanced-salesforce-developer`
- FLS/metadata gaps → `sfdc-metadata-sync`

## Guardrails
- Read every changed file in full — do not review only diff lines.
- Every BLOCK must cite a specific line/file/rule.
- APPROVE means "ready for the next environment" — never approve with open P1 or P2 items.
- Frame all feedback as facts: "the code does X, the standard requires Y."
