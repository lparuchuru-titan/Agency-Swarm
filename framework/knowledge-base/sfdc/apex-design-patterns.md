# Apex Design Patterns & Trigger Frameworks
_Last refreshed via SFDC Knowledge Swarm · Sources: 6 docs_

## Summary

Apex automation should be organized so that triggers stay "thin" and all business
logic lives in testable, reusable classes. Two complementary bodies of practice
cover this:

1. **Trigger handler frameworks** — enforce *one trigger per object*, dispatch
   each trigger context (before/after × insert/update/delete/undelete) to a
   handler class with virtual methods, and centralize cross-cutting concerns like
   recursion control and per-handler bypass. The canonical reference
   implementation is Kevin O'Hara's `sfdc-trigger-framework` (a `TriggerHandler`
   base class with a `run()` dispatcher).
2. **Apex Enterprise Patterns** (Service / Domain / Selector / Unit of Work) —
   Salesforce's layered architecture (popularized by the `fflib-apex-common`
   library) that separates orchestration (Service), object-specific behavior
   (Domain), SOQL (Selector), and transactional DML (Unit of Work) for large,
   multi-team orgs.

Underlying both: **bulkification** (operate on collections, never SOQL/DML in
loops) is mandatory because Salesforce processes DML in **batches of up to 200
records**, and a trigger fires once per chunk.

## Key concepts

**Trigger context variables** (used to branch inside handlers):
- `Trigger.new` / `Trigger.old` — `List<SObject>` of new / prior record states.
- `Trigger.newMap` / `Trigger.oldMap` — `Map<Id, SObject>` for keyed lookups.
- `Trigger.isExecuting`, `Trigger.isBefore`, `Trigger.isAfter`,
  `Trigger.isInsert`, `Trigger.isUpdate`, `Trigger.isDelete`,
  `Trigger.isUndelete`, `Trigger.size`, `Trigger.operationType`.
- Availability: `Trigger.old`/`oldMap` are **not** available in insert;
  `Trigger.new`/`newMap` are **not** available in delete; `new`/`newMap` are
  read-only in *after* contexts; field edits to `Trigger.new` without DML are only
  possible in *before* contexts.

**One trigger per object** — multiple triggers on the same object have no
guaranteed order; consolidating to one trigger + one handler makes execution
order deterministic and testable.

**Trigger handler base class** — a `virtual` class exposing overridable methods
(`beforeInsert`, `beforeUpdate`, `beforeDelete`, `afterInsert`, `afterUpdate`,
`afterDelete`, `afterUndelete`). A `run()` method inspects the trigger context and
calls the right override. Handlers cast `Trigger.new`/`Trigger.old` to the
concrete SObject list.

**Enterprise (layered) patterns:**
- **Service layer** — coarse-grained, reusable business processes; transaction
  boundary; called by controllers, batch, queueable, REST. Contains no SOQL/DML
  directly — it orchestrates Domain and Selector calls.
- **Domain layer** — object-specific behavior (validation, defaulting,
  calculation). In fflib, `fflib_SObjectDomain` subclasses implement
  `onBeforeInsert()`, `onAfterUpdate()`, etc.; triggers delegate via
  `fflib_SObjectDomain.triggerHandler(MyDomain.class)`.
- **Selector layer** — owns all SOQL for an object (consistent field lists,
  security). In fflib, `fflib_SObjectSelector` subclasses implement
  `getSObjectType()`, `getSObjectFieldList()`, and `selectById(Set<Id>)`.
- **Unit of Work** — `fflib_ISObjectUnitOfWork`: accumulate changes with
  `registerNew`, `registerDirty`, `registerDeleted`, `registerRelationship`, then
  `commitWork()` flushes them in dependency order, **minimizing DML statements**
  and wrapping everything in one transaction/savepoint.
- **Application factory** — a single class returning instances of each layer
  (`Application.Service`, `Application.Domain`, `Application.Selector`,
  `Application.UnitOfWork`) so mocks can be injected for unit testing.

## Best practices / guardrails

- **Keep triggers thin** — the trigger body should do nothing but instantiate the
  handler and call `run()` (or `fflib_SObjectDomain.triggerHandler(...)`).
- **One trigger per object**; name it `<SObject>Trigger` and the handler
  `<SObject>TriggerHandler` (or domain `<PluralSObject>`).
- **Bulkify everything** — never put SOQL or DML inside a `for` loop; query/update
  on collections. Use maps keyed by Id (or by a related field) to correlate
  records without nested loops.
- **Control recursion** — guard re-entrant logic with a `static` variable (flag or
  `Set<Id>` of already-processed records); statics persist for the whole
  transaction across the 200-record chunks. Frameworks formalize this with a
  `setMaxLoopCount(n)` that throws when exceeded.
- **Provide a bypass mechanism** — for data loads / integrations, allow disabling a
  handler (`TriggerHandler.bypass('AccountTriggerHandler')` /
  `clearBypass(...)` / `isBypassed(...)` / `clearAllBypasses()`). Custom-metadata-
  driven bypass is common for admin control without redeploys.
- **Route SOQL through Selectors and DML through Unit of Work** in enterprise
  orgs; this consolidates DML and makes ordering across related objects safe.
- **Enforce CRUD/FLS** — Selector field lists + `WITH USER_MODE` /
  `Security.stripInaccessible` so the layers respect the running user's access.
- **Test at the right layer** — for fflib, trigger behavior is tested through
  Domain test classes (perform insert/update/delete and assert); Service and
  Domain are unit-tested with mocked Selectors/UoW via the Application factory.

## Gotchas & limits

- **Batching = 200**: DML processes up to 200 records per chunk; 400 records fire
  the trigger twice. Logic and static recursion guards must remain correct across
  multiple chunks in one transaction.
- **Governor limits per transaction** (the reason bulkification matters):
  ~100 SOQL queries (synchronous; 200 async), 150 DML statements, 50,000 rows
  retrieved by SOQL — SOQL/DML inside a 200-row loop blows past these fast.
- **Order of execution re-entrancy**: workflow field updates and roll-up summary
  recalculation re-fire before/after triggers on the same/parent record — a major
  source of unintended recursion. Static guards mitigate this.
- **Before vs after**: edit own-record fields in *before* (no extra DML); use
  *after* when you need the record Id or must touch related records.
  `Trigger.new` is read-only in *after* contexts.
- **Multiple triggers, undefined order** — exactly why one-trigger-per-object is a
  hard rule.
- **Static-flag recursion guards can be too aggressive** — a blanket
  "run once per transaction" flag can skip legitimate re-processing of *different*
  records; prefer a `Set<Id>` of processed records when partial re-entry is valid.
- **fflib learning curve / overhead** — full Service/Domain/Selector/UoW is
  justified for large or multi-team orgs; small orgs are better served by a
  lightweight one-trigger-per-object handler.

## Code / config patterns

Thin trigger delegating to a handler framework:

```apex
trigger OpportunityTrigger on Opportunity (
    before insert, before update, before delete,
    after insert, after update, after delete, after undelete
) {
    new OpportunityTriggerHandler().run();
}
```

Handler extending a base `TriggerHandler` (Kevin O'Hara style) with a recursion
cap:

```apex
public with sharing class OpportunityTriggerHandler extends TriggerHandler {

    public OpportunityTriggerHandler() {
        this.setMaxLoopCount(1); // throws if re-entered beyond the limit
    }

    public override void beforeUpdate() {
        for (Opportunity o : (List<Opportunity>) Trigger.new) {
            Opportunity prior = (Opportunity) Trigger.oldMap.get(o.Id);
            if (o.StageName != prior.StageName) {
                // bulkified, no SOQL/DML in this loop
            }
        }
    }

    public override void afterInsert() {
        // use Trigger.newMap.keySet() for related-record queries/DML in bulk
    }
}
```

Per-handler bypass (e.g. for a data load):

```apex
TriggerHandler.bypass('AccountTriggerHandler');
update accountsToLoad;            // AccountTriggerHandler logic skipped
TriggerHandler.clearBypass('AccountTriggerHandler');
```

Recursion control with a static Set (allows re-processing other records):

```apex
public with sharing class AccountService {
    private static Set<Id> processedIds = new Set<Id>();

    public static void rollupChildren(List<Account> accts) {
        List<Account> toProcess = new List<Account>();
        for (Account a : accts) {
            if (!processedIds.contains(a.Id)) {
                processedIds.add(a.Id);
                toProcess.add(a);
            }
        }
        if (toProcess.isEmpty()) return;
        // bulk SOQL/DML on toProcess only
    }
}
```

fflib-style enterprise wiring (Domain dispatch + Unit of Work):

```apex
// Trigger: one line, delegates to the Domain class
trigger AccountTrigger on Account (
    before insert, before update, after insert, after update
) {
    fflib_SObjectDomain.triggerHandler(Accounts.class);
}
```

```apex
// Domain class: object-specific behavior, named after the SObject (plural)
public with sharing class Accounts extends fflib_SObjectDomain {
    public Accounts(List<Account> records) { super(records); }

    public class Constructor implements fflib_SObjectDomain.IConstructable {
        public fflib_SObjectDomain construct(List<SObject> records) {
            return new Accounts(records);
        }
    }

    public override void onBeforeInsert() {
        for (Account a : (List<Account>) Records) {
            if (String.isBlank(a.Name)) {
                a.Name.addError('Name is required');
            }
        }
    }
}
```

```apex
// Service layer: orchestrates Domain + Selector + Unit of Work; no inline SOQL/DML
public with sharing class OpportunityService {
    public static void closeOpportunities(Set<Id> oppIds) {
        fflib_ISObjectUnitOfWork uow = Application.UnitOfWork.newInstance();
        for (Opportunity o : OpportunitiesSelector.newInstance().selectById(oppIds)) {
            o.StageName = 'Closed Won';
            uow.registerDirty(o);                 // queued, not committed yet
        }
        uow.commitWork();                          // single, ordered DML flush
    }
}
```

## Sources

- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers.htm (official Apex Triggers reference — page is JS-rendered; returned no extractable text via fetch)
- https://fflib.dev/docs/triggers (fflib trigger-to-domain dispatch, `fflib_SObjectDomain.triggerHandler`)
- https://trailhead.salesforce.com/content/learn/modules/apex_patterns_dsl/apex_patterns_dsl_learn_dl_principles (Salesforce Trailhead — Domain Layer principles)
- https://crsinfosolutions.com/trigger-framework-in-salesforce/ (one-trigger-per-object, base handler, recursion control)
- https://raw.githubusercontent.com/kevinohara80/sfdc-trigger-framework/master/README.md (TriggerHandler base class, run(), setMaxLoopCount, bypass API)
- https://sfdcdevelopers.com/2025/11/03/salesforce-order-of-execution-guide/ (order of execution, before vs after triggers, batch processing)
