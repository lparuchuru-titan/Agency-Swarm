# Security, Sharing & FLS
_Last refreshed via SFDC Knowledge Swarm · Sources: 4 docs_

## Summary
Salesforce enforces data access at three layers: object-level (CRUD), field-level (FLS),
and record-level (sharing). Apex traditionally runs in **system mode**, where CRUD, FLS,
and sharing are NOT automatically enforced — the developer is responsible. Modern Apex
should use **user mode** (`WITH USER_MODE` for SOQL/SOSL, `AccessLevel.USER_MODE` for DML)
which enforces OLS, FLS, and record sharing of the running user in a single construct.
When user mode is not desired, FLS/CRUD can be enforced with `Security.stripInaccessible`
or `WITH SECURITY_ENFORCED`, while record sharing is governed by the class sharing keyword
(`with sharing` / `without sharing` / `inherited sharing`). At the configuration layer,
Salesforce is steering teams away from permissions on profiles toward permission sets and
permission set groups.

## Key concepts
- **Three access layers**
  - Object (CRUD) and Field (FLS): granted via profiles and permission sets.
  - Record (sharing): governed by OWD, role hierarchy, sharing rules, manual/Apex sharing.
- **System mode vs user mode**
  - System mode (Apex default): elevated permissions; CRUD/FLS/sharing not auto-enforced.
  - User mode: respects CRUD, FLS, and sharing of the running user.
- **Sharing keywords (class-level, control record access in system-mode code)**
  - `with sharing` — respects OWD, role hierarchy, and sharing rules for the running user.
  - `without sharing` — ignores record-level restrictions; returns all matching records.
  - `inherited sharing` — adopts the sharing mode of the calling class; safer than omitting.
  - Omitted — inherits from the caller; a standalone/entry-point class effectively runs
    `without sharing`. Always declare a keyword explicitly.
- **FLS / CRUD enforcement options**
  - `WITH USER_MODE` (SOQL/SOSL) — enforces OLS, FLS, and sharing together; precise errors.
  - `AccessLevel.USER_MODE` — same enforcement on `Database.*` DML methods.
  - `Security.stripInaccessible(AccessType, records)` — strips fields (and relationship
    fields) the user can't access; ideal for dynamic SOQL and sanitizing untrusted data
    before DML. `AccessType`: `READABLE`, `CREATABLE`, `UPDATABLE`, `UPSERTABLE`.
  - `WITH SECURITY_ENFORCED` (static SOQL) — checks OLS/FLS on SELECT/FROM fields only;
    throws a generic exception; has limited polymorphic-field support.
  - Schema describe checks (`isAccessible()`, `isUpdateable()`, etc.) — legacy, verbose,
    no longer the recommended default.
- **Profiles vs permission sets**
  - Best practice: assign the **Minimum Access - Salesforce** base profile and grant all
    permissions through permission sets and permission set groups (least privilege).
  - Permission sets only **add** access; they cannot revoke what a profile grants.
  - Permission set groups support **muting** to remove specific permissions within a group.
  - Profiles continue to hold login hours, IP ranges, default app/record types, and page
    layout assignments; permission-bearing settings are moving off profiles over time.

## Best practices / guardrails
- Declare a sharing keyword on **every** class — omission is insecure by default.
- Prefer `WITH USER_MODE` / `AccessLevel.USER_MODE` for new controller and service code
  that should run with the running user's full access profile.
- Use `Security.stripInaccessible` + an explicit sharing keyword when you need FLS
  enforcement but want sharing controlled by the class (e.g., system automation that must
  still hide inaccessible fields).
- Use `inherited sharing` for shared utility classes so the caller's sharing context is
  honored rather than silently running without sharing.
- Follow least privilege: base profile + targeted permission sets / permission set groups;
  use muting in PSGs instead of editing shared permission sets directly.
- Strip/validate fields on untrusted input before DML to avoid leaking or writing
  fields the user cannot access.

## Gotchas & limits
- Apex `insert`/`update` in plain system-mode code does **not** check FLS or CRUD — silent
  over-permission unless you enforce it.
- An entry-point class with no sharing keyword runs effectively `without sharing`.
- `WITH SECURITY_ENFORCED` only validates fields referenced in SELECT/FROM (not WHERE/ORDER
  BY in older behavior), throws a non-specific exception, and has limited polymorphic
  support — `WITH USER_MODE` gives clearer per-field errors.
- When user mode is active, class sharing keywords do not override it — sharing is enforced
  by user mode regardless of the keyword.
- Permission sets cannot remove access a profile already grants; to restrict, you must
  adjust the profile or use PSG muting.
- `stripInaccessible` silently removes inaccessible fields — downstream code must not assume
  those fields are populated.

## Code / config patterns

```apex
// Class-level record-access control
public with sharing class AccountService { /* respects sharing rules */ }
public without sharing class BatchJob { /* ignores record restrictions */ }
public inherited sharing class SharedUtil { /* uses caller's sharing context */ }
```

```apex
// User mode: enforces OLS + FLS + sharing in one construct
List<Account> accts = [SELECT Id, Industry FROM Account WITH USER_MODE];

Database.insert(newAccts, AccessLevel.USER_MODE);   // DML in user mode
Database.update(toUpdate, AccessLevel.USER_MODE);
```

```apex
// stripInaccessible: enforce FLS while sharing stays under class control
SObjectAccessDecision decision =
    Security.stripInaccessible(AccessType.CREATABLE, accountsToInsert);
insert decision.getRecords();
// decision.getRemovedFields() reports what was stripped, by SObject type

// Sanitize query results for reads
SObjectAccessDecision rd =
    Security.stripInaccessible(AccessType.READABLE, queriedAccounts);
List<Account> safe = (List<Account>) rd.getRecords();
```

```apex
// WITH SECURITY_ENFORCED: static-SOQL FLS/OLS check (generic exception on failure)
List<Contact> cons =
    [SELECT Id, Email FROM Contact WITH SECURITY_ENFORCED];
```

```apex
// Legacy describe-based FLS check (avoid for new code)
if (Schema.sObjectType.Account.fields.Industry.isUpdateable()) {
    // safe to write Industry
}
```

## Sources
- https://blog.beyondthecloud.dev/blog/apex-security-and-sharing
- https://www.salesforceben.com/a-guide-to-security-in-apex-object-field-and-record-level/
- https://gearset.com/blog/devops-and-the-transition-from-profiles-to-permission-sets/
- https://bluecanvas.io/blog/mastering-salesforce-permission-change-management-best-practices-and-tools-for-2024
