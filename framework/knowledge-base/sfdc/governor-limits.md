# Governor Limits & Large Data Volumes
_Last refreshed via SFDC Knowledge Swarm · Sources: 4 docs_

> Note: The two official Salesforce Apex docs (`apex_gov_limits.htm`, `apex_async_overview.htm`) are JavaScript-rendered and returned no extractable text on fetch. Values below are grounded in the Salesforce Developer Limits & Allocations cheat sheet (referenced via search), Apex Hours, and Salesforce Geek. Always confirm current numbers against the live Salesforce docs for your org's API version, since some limits change between releases.

## Summary
Salesforce is multi-tenant: every Apex transaction runs inside **per-transaction governor limits** that cap how many queries, DML operations, CPU cycles, and memory a single execution context may consume. Exceeding a limit throws a non-catchable `System.LimitException` and rolls back the transaction. Limits reset at the start of each new transaction. **Asynchronous Apex** (Future, Queueable, Batch, Scheduled) runs in a separate transaction with **higher limits** (notably 2x SOQL queries, 6x CPU, 2x heap), which is the primary lever for processing **Large Data Volumes (LDV)**. On top of governor limits, LDV introduces *data-side* concerns: query selectivity, indexing, skinny tables, and sharing/row-lock contention.

## Key concepts
- **Per-transaction limit**: enforced per execution context (one trigger fire + everything synchronous it invokes is ONE transaction). Limits do not accumulate across transactions.
- **Synchronous vs. asynchronous context**: async jobs get more generous limits because they run off the user-facing thread.
- **Bulk context**: triggers and Batch `execute()` receive up to 200 records at once; code must handle collections, not single records.
- **Selective query**: a SOQL `WHERE` filter whose indexed predicate narrows results below Salesforce's selectivity thresholds. Non-selective queries on large objects throw `QueryException: Non-selective query against large object type` (commonly when an object exceeds ~100,000+ records and no selective index is used).
- **Skinny table**: a Salesforce-maintained, read-optimized table (created by Support) that copies a subset of frequently-used fields from a base object + its custom fields, avoiding joins. Caps at 100 columns; not copied to sandboxes by default; supports a subset of field types.
- **Custom index**: index on a field requested via Support (or implicit on External ID / Unique fields) to make queries selective.
- **LDV (Large Data Volumes)**: objects with millions of records where query/report/sharing performance degrades; mitigated by selective queries, indexes, skinny tables, data archiving (`PK chunking`), and async/batch processing.

## Best practices / guardrails
- **Never put SOQL or DML inside a loop.** Build collections (`List`/`Map`/`Set`) and execute one bulk DML per object.
- **Query only what you need**: select specific fields (not `SELECT *`-style field lists you don't use), add `WHERE` filters and `LIMIT`, and filter at the database, not in Apex.
- **Make queries selective**: filter on indexed fields (Id, Name, External Id, Unique, audit fields, or custom-indexed fields). Avoid `!=`, `NOT`, leading `%` wildcards, and formula fields referencing other objects in `WHERE` — these defeat indexes.
- **One trigger per object** with a handler/framework class; guard against recursion.
- **Use `Database.QueryLocator` in Batch Apex** to stream up to 50 million records; each `execute()` chunk gets a fresh set of governor limits.
- **Use `Limits` methods defensively** (e.g., `Limits.getQueries()` / `Limits.getLimitQueries()`) to branch before hitting a ceiling.
- **Use `WITH USER_MODE` or `Security.stripInaccessible`** for CRUD/FLS — also keeps queries honest.
- **Move heavy/external work async**: offload callouts and large processing to Future/Queueable/Batch so the synchronous limits aren't the bottleneck.
- **For LDV**: request custom indexes / skinny tables from Support, use PK chunking for bulk reads, archive old data, and reduce sharing-rule complexity to avoid row-lock and recalculation contention.

## Gotchas & limits
**Per-transaction governor limits (synchronous → asynchronous):**

| Limit | Synchronous | Asynchronous |
|---|---|---|
| Total SOQL queries issued | 100 | 200 |
| Total query rows retrieved by SOQL | 50,000 | 50,000 |
| Total SOSL queries issued | 20 | 20 |
| Total SOSL records retrieved | 2,000 | 2,000 |
| Total DML statements | 150 | 150 |
| Total records processed by DML / `Database.emptyRecycleBin` | 10,000 | 10,000 |
| Max CPU time on Salesforce servers | 10,000 ms (10 sec) | 60,000 ms (60 sec) |
| Max heap size | 6 MB | 12 MB |
| Total callouts (HTTP/web service) per transaction | 100 | 100 |
| Max cumulative callout timeout | 120 sec | 120 sec |
| Future calls (`@future`) per transaction | 50 | 50 |
| Queueable jobs added (`System.enqueueJob`) per transaction | 50 | 50 (1 from within a Queueable) |
| Async Apex executions per 24h (batch + future + queueable + scheduled) | 250,000 or 200×licenses, whichever is greater | — |

**Common gotchas:**
- **CPU time** is the most common silent killer in trigger-heavy / formula-heavy orgs — DML and callout time do NOT count toward CPU; loops, sorting, and logic do.
- **`@future` cannot return a value, cannot take sObjects/objects** (only primitives and collections of primitives, to avoid stale data), and **cannot be chained** or called from another future/batch. Prefer Queueable.
- **Queueable chaining**: from within a running Queueable you may enqueue only **1** child job (chain depth effectively unbounded in production; Developer/Trial editions cap chain depth at **5**).
- **Batch Apex**: default scope **200**, max scope **2,000** records per `execute()`; only **5** batch jobs can run/queue at once (the **Apex Flex Queue** holds up to **100** batches in *Holding* status); `start()` `QueryLocator` may return up to **50 million** rows.
- **Non-selective query on a large object** throws `QueryException` even if it would return few rows — selectivity is about the filter+index, not the result size.
- **Mixed DML**: setup objects (User, Group, etc.) and non-setup objects cannot be DML'd in the same transaction — split into a Future/Queueable.
- Skinny tables are **not auto-created in sandboxes** and must be re-requested after a refresh; they don't include data from related objects.

## Code / config patterns

Bulkified trigger handler — collect then one DML:
```apex
public with sharing class AccountTriggerHandler {
    public static void handleAfterUpdate(List<Account> newList, Map<Id, Account> oldMap) {
        List<Contact> toUpdate = new List<Contact>();
        // ONE query for all parents, keyed by Id
        Map<Id, List<Contact>> byAccount = new Map<Id, List<Contact>>();
        for (Contact c : [SELECT Id, AccountId, Active__c
                          FROM Contact
                          WHERE AccountId IN :newList WITH USER_MODE]) {
            if (!byAccount.containsKey(c.AccountId)) byAccount.put(c.AccountId, new List<Contact>());
            byAccount.get(c.AccountId).add(c);
        }
        for (Account a : newList) {
            if (a.Active__c != oldMap.get(a.Id).Active__c && byAccount.containsKey(a.Id)) {
                for (Contact c : byAccount.get(a.Id)) {
                    c.Active__c = a.Active__c;
                    toUpdate.add(c);
                }
            }
        }
        if (!toUpdate.isEmpty()) update toUpdate; // single bulk DML
    }
}
```

Batch Apex for LDV — selective QueryLocator, fresh limits per chunk:
```apex
public with sharing class AccountArchiveBatch
        implements Database.Batchable<SObject>, Database.Stateful {

    public Database.QueryLocator start(Database.BatchableContext bc) {
        // Selective: filtered on indexed/date field; QueryLocator streams up to 50M rows
        return Database.getQueryLocator(
            'SELECT Id, Name FROM Account WHERE LastActivityDate < LAST_N_DAYS:730');
    }

    public void execute(Database.BatchableContext bc, List<Account> scope) {
        // Each execute() chunk (default 200) gets its own governor limits
        for (Account a : scope) { a.Archived__c = true; }
        update scope;
    }

    public void finish(Database.BatchableContext bc) { /* notify / chain */ }
}
// Invoke with explicit scope size (1..2000)
// Database.executeBatch(new AccountArchiveBatch(), 200);
```

Queueable with chaining + defensive limit check (preferred over @future):
```apex
public with sharing class NotifyQueueable implements Queueable, Database.AllowsCallouts {
    private List<Id> recordIds;
    public NotifyQueueable(List<Id> ids) { this.recordIds = ids; }

    public void execute(QueueableContext ctx) {
        // ... do work / callouts ...
        // Chain only if there is more to do and limits allow (1 child enqueue max)
        if (!recordIds.isEmpty() && Limits.getLimitQueueableJobs() > Limits.getQueueableJobs()) {
            System.enqueueJob(new NotifyQueueable(remaining));
        }
    }
}
```

Defensive limit guard:
```apex
if (Limits.getQueries() >= Limits.getLimitQueries() - 5) {
    // approaching SOQL ceiling — defer remaining work to a Queueable
    System.enqueueJob(new DeferredWork(pending));
}
```

## Sources
- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm (official; JS-rendered, no text extracted on fetch — listed as canonical reference)
- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_async_overview.htm (official; JS-rendered, no text extracted on fetch — listed as canonical reference)
- https://www.apexhours.com/governor-limits-in-salesforce/
- https://salesforcegeek.in/batch-vs-queueable-vs-future-vs-schedulable-apex/
- https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/salesforce_app_limits_cheatsheet.pdf (Salesforce Developer Limits & Allocations cheat sheet — values via search excerpt)
