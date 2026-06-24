# Flow & Declarative Automation
_Last refreshed via SFDC Knowledge Swarm · Sources: 4 docs_

## Summary
Salesforce Flow is the platform's primary declarative (low-code) automation tool. The
modern, recommended automation surfaces are **record-triggered flows** (fire on
create/update/delete), **screen flows** (UI-driven), **scheduled flows** (run on a
schedule against a batch of records), and **autolaunched flows / subflows** (invoked from
other flows, Apex, processes, or actions). Workflow Rules and Process Builder are retired
for new builds — record-triggered flows are their successor.

The single most important design axis is **when** a record-triggered flow runs relative to
the database save:

- **Before-save (fast field update):** runs in the pre-commit context, before the record is
  written. It updates fields on the *triggering record only*, with **no extra DML** and no
  separate save cycle. It is cited as running up to ~10x faster than after-save automation,
  approaching Apex before-trigger performance.
- **After-save:** runs after the record is committed. It has the record Id and full context,
  and can create/update related records, delete, send email/Chatter, call subflows and
  invocable Apex, and schedule async paths — but every cross-record change costs explicit DML.

The current architectural consensus is a **hybrid model**: use record-triggered Flow as the
orchestration layer (entry criteria + execution context) and push genuinely complex logic
(multi-step integrations, ordered callouts, heavy computation) into **invocable Apex** called
from the flow.

## Key concepts
- **Flow types:** record-triggered, screen, scheduled, autolaunched (no trigger), platform-event-triggered.
- **Record-triggered run timing:** *Fast Field Update* (before-save) vs *Actions and Related
  Records* (after-save); plus an optional **asynchronous (scheduled) path** and a
  **scheduled (time-based) path** within after-save flows for deferred/async work.
- **Before-save capabilities:** update the triggering record only; zero extra DML; cannot get
  the new record Id, cannot create/delete records, cannot send emails/Chatter, cannot call
  Apex or subflows, does not run on delete.
- **After-save capabilities:** has record Id; can create/update/delete related records, send
  notifications, post to Chatter, call invocable Apex and subflows, run on delete, and kick
  off async paths.
- **Subflows:** an autolaunched flow invoked from another flow. Used to centralize reusable
  logic — e.g., one shared **error-handling subflow** that every flow calls from its fault path.
- **Bulkification:** record-triggered flows are automatically invoked for **batches of up to
  200 records per transaction**. Auto-bulkification holds *only* if you keep DML and Get
  Records out of loops.
- **Fault paths:** every element that can fail (Get/Create/Update/Delete, Action, callout)
  can have a fault connector that routes to error handling. Background flows have no UI, so
  faults must log and/or notify rather than show a screen error.

## Best practices / guardrails
- **Default to before-save** whenever you only need to set fields on the record that fired the
  flow — it is the cheapest and fastest option and consumes no DML.
- **Use entry conditions** aggressively so the flow only runs when it must (set "When to Run
  the Flow for Updated Records" to *only when a record meets the condition requirements* to
  avoid recursive/no-op re-entry).
- **One before-save + one after-save flow per object** is the recommended enterprise pattern.
  Splitting by sub-process inside ordered flows (via the flow trigger order / priority) keeps
  things maintainable; avoid scattering many uncoordinated flows on one object.
- **Design for bulk:** never put Get Records or DML (Create/Update/Delete) inside a Loop.
  Query related data once before the loop, accumulate changes into a collection variable, then
  do a single Update Records after the loop.
- **Centralize error handling:** route fault paths to one shared error-handling subflow that
  logs the error (custom object / platform event) and alerts admins. Keep error logic consistent.
- **No hard-coded IDs** (record types, users, queues) — use $Record references, custom metadata/labels, or dynamic lookups.
- **Push complexity to invocable Apex** via `@InvocableMethod` and call it from the flow; let
  Flow own orchestration/entry criteria and Apex own algorithms and ordered callouts.
- **Test with realistic volume** (200-record batches); monitor *Setup > Process Automation
  Usage and Limits*.

## Gotchas & limits
- **Per-transaction batch = 200 records.** Auto-bulkification is silently defeated by any DML
  or query inside a loop — each iteration then consumes its own SOQL/DML against governor limits.
- **Governor limits are shared** across all automation in the transaction (Flow + Apex +
  triggers): 100 SOQL queries, 150 DML statements, ~10s sync CPU. A loop with per-record
  Update Records is the classic limit-blower.
- **Before-save cannot** get the new record Id, do cross-object DML, send email/Chatter, call
  Apex/subflows, or run on delete — putting those into a before-save context is impossible by design.
- **After-save updates of the triggering record cost a full DML** (and re-fire automation) —
  prefer before-save for same-record field sets to avoid the extra save cycle.
- **Recursion / re-entry:** an after-save flow that updates its own record (or a record that
  re-triggers it) can loop. Gate with entry conditions and the "only when changed" option.
- **Background flows have no screens** — a fault with no fault path produces an unhandled flow
  error and rolls back the transaction; always wire fault connectors.
- For volumes beyond what Flow handles cleanly, hand off to **Queueable/Batch Apex** through an
  invocable wrapper rather than forcing it through Flow.
- The official help page `sf.flow.htm` was JS-rendered/non-fetchable at refresh time; details
  here are corroborated from Salesforce Ben, SFDC Developers, and Salesforce search summaries.

## Code / config patterns

Invocable Apex called from a record-triggered flow (bulk-safe orchestration handoff):

```apex
public with sharing class AccountRatingAction {
    public class Request {
        @InvocableVariable(required=true) public Id accountId;
        @InvocableVariable public Decimal annualRevenue;
    }
    public class Result {
        @InvocableVariable public String rating;
    }

    // Flow passes a COLLECTION; method receives a List and returns a List
    // of equal size. This preserves bulk safety end-to-end.
    @InvocableMethod(label='Compute Account Rating' category='Account')
    public static List<Result> compute(List<Request> requests) {
        List<Result> results = new List<Result>();
        for (Request req : requests) {            // no SOQL/DML in this loop
            Result r = new Result();
            r.rating = (req.annualRevenue != null && req.annualRevenue > 1000000)
                ? 'Hot' : 'Warm';
            results.add(r);
        }
        return results;                            // 1:1 with input order
    }
}
```

Conceptual bulk-safe flow shape (declarative, expressed as steps):

```text
Before-save flow (Fast Field Update) on Account, entry: Industry changed
  -> Assignment: $Record.Rating = 'Reassess'        (no DML, no loop)

After-save flow on Account, entry: Type = 'Customer' AND ISCHANGED(Type)
  -> Get Records: Contacts WHERE AccountId IN triggering records   (1 query)
  -> Loop over Contacts
       -> Assignment: build/modify Contact in memory
       -> Add to contactsToUpdate collection            (NO Update inside loop)
  -> Update Records: contactsToUpdate                    (1 bulk DML after loop)
  -> Fault path on every Get/Update -> Subflow: Log_And_Notify_Error
```

Trigger-handler equivalent when logic moves to Apex (one trigger per object):

```apex
trigger AccountTrigger on Account (before insert, before update,
                                   after insert, after update) {
    new AccountTriggerHandler().run();   // no logic in trigger body
}
```

## Sources
- https://www.salesforceben.com/before-save-flow-vs-after-save-flow-in-salesforce/
- https://sfdcdevelopers.com/2025/09/13/how-to-handle-bulk-record-processing-in-flows/
- https://help.salesforce.com/s/articleView?id=sf.flow.htm&type=5 (JS-rendered / not directly fetchable at refresh time)
- WebSearch syntheses of: architect.salesforce.com record-triggered decision guide, admin.salesforce.com "Ultimate Guide to Flow Best Practices", salesforce.com "Record-Triggered Automation: Apex or Flow?"
