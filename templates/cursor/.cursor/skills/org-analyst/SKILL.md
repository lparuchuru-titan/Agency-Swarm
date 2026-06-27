# Org Analyst Skill

## Role
Discover the health, security posture, and technical debt of any Salesforce org.
Read-only. Never deploys or modifies anything.

## Lifecycle position
**Discover** — runs before any implementation on an unfamiliar org, and as a release-readiness gate before go-live.

## SOQL query library

### Security
```sql
-- Profiles with dangerous permissions
SELECT Name FROM Profile
WHERE PermissionsModifyAllData = true OR PermissionsViewAllData = true

-- Guest user with data access
SELECT Name, UserType FROM User
WHERE UserType = 'Guest' AND IsActive = true

-- Named Credentials (integration surface)
SELECT DeveloperName, Endpoint, AuthProtocol FROM NamedCredential

-- Connected Apps
SELECT Name, ContactEmail, MobileSessionTimeout FROM ConnectedApplication

-- Permission sets granting ModifyAll
SELECT PermissionSet.Name FROM PermissionSetAssignment
WHERE PermissionSet.PermissionsModifyAllData = true
```

### Code Quality
```sql
-- Apex coverage (classes with zero coverage)
SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered,
       (NumLinesCovered / (NumLinesCovered + NumLinesUncovered + 0.001)) * 100 pct
FROM ApexCodeCoverageAggregate
ORDER BY NumLinesCovered ASC LIMIT 50

-- Large triggers (likely no handler pattern)
SELECT Name, TableEnumOrId, LengthWithoutComments
FROM ApexTrigger
WHERE LengthWithoutComments > 3000 AND Status = 'Active'
ORDER BY LengthWithoutComments DESC

-- Old API versions
SELECT Name, ApiVersion FROM ApexClass
WHERE ApiVersion < 55.0 ORDER BY ApiVersion ASC LIMIT 50
```

### Data Model
```sql
-- Objects with most DML in Apex (heuristic — objects frequently written to)
SELECT TableEnumOrId, COUNT(Id) dml_count
FROM ApexLog GROUP BY TableEnumOrId ORDER BY dml_count DESC LIMIT 20

-- External IDs
SELECT QualifiedApiName, EntityDefinition.QualifiedApiName
FROM FieldDefinition WHERE IsIdLookup = true
```

## Static analysis patterns (Grep targets in force-app/)

| Pattern | Risk | Grep |
|---|---|---|
| SOQL in loop | Governor limit | `for.*\(.*\[SELECT` |
| DML in loop | Governor limit | `for.*\{[^}]*insert\|update\|delete` |
| `without sharing` | Security bypass | `without sharing` |
| Hardcoded ID | Fragile | `'[0-9a-zA-Z]{15,18}'` |
| Missing null check | NPE | `\.get(0)` without if-null |
| `System.debug` | Production noise | `System\.debug` |
| `seeAllData=true` | Test isolation | `SeeAllData\s*=\s*true` |

## Health score rubric (0–100)

| Dimension | Weight | 100 (perfect) | 0 (critical) |
|---|---|---|---|
| Security | 25 | No profiles with ModifyAll except Admin; no guest exposure; FLS enforced | Profiles with ModifyAll, exposed Named Creds, no FLS |
| Code Quality | 25 | All classes ≥85% coverage; handler pattern on all triggers; zero dead code | Classes at 0%; business logic in trigger body |
| Architecture | 20 | Service layer; selector pattern; API versions current; no hardcoded IDs | God classes; hardcoded IDs everywhere; v20 API |
| Data Model | 15 | Relationships correct; rollups working; required fields have defaults | Orphaned lookups; missing required field handling |
| Automation | 15 | No flow/trigger overlap; all fault paths wired; bulk-safe | Multiple triggers on same object; flows with no fault paths |

## Output template

Save HTML to `docs/explainers/YYYYMMDD-org-health-<scope>.html`.
Structure:
1. Executive summary (health score, top 3 risks)
2. Security findings (P1 blockers)
3. Technical debt (P2/P3)
4. Coverage table
5. Release readiness checklist
6. Remediation roadmap (P1 → P2 → P3, effort estimates)

## Guardrails
- Read-only. No `sf project deploy`, no DML, no metadata updates.
- Cite every finding with a file path, class name, or SOQL result.
- Mark inferred findings as "inferred" — do not state as fact without evidence.
