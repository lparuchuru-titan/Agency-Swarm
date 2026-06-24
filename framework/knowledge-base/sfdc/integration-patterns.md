# Integration Patterns
_Last refreshed via SFDC Knowledge Swarm · Sources: 4 docs_

## Summary
Salesforce integration design starts by classifying the use case into one of the canonical patterns from Salesforce's *Integration Patterns and Practices* guide, then choosing the technology that fits the timing (synchronous vs. asynchronous), the direction (Salesforce-initiated vs. external-initiated), the volume, and the delivery guarantees required. The five-to-six canonical patterns are: **Remote Process Invocation – Request and Reply**, **Remote Process Invocation – Fire and Forget**, **Batch Data Synchronization**, **Remote Call-In**, **UI Update Based on Data Changes**, and **Data Virtualization**. The rule of thumb: prefer asynchronous, event-driven, loosely-coupled designs for resilience and scale; reserve synchronous request/reply for cases that genuinely need an immediate response. Use **Named Credentials** for all outbound auth, **Platform Events / Change Data Capture** for decoupled near-real-time flows, and **Bulk API** for large data volumes.

## Key concepts
- **Remote Process Invocation – Request and Reply**: Salesforce calls an external system, waits, and processes the response in the same transaction. Implemented with Apex HTTP callouts, External Services, or LWC/Visualforce calling external HTTP services. Synchronous; use only when an immediate response is required.
- **Remote Process Invocation – Fire and Forget**: Salesforce triggers an external process and does not wait for completion. Implemented with **Platform Events**, **Outbound Messaging** (SOAP, declarative), or asynchronous Apex callouts. Best for resilience and decoupling.
- **Batch Data Synchronization**: Bidirectional bulk data movement, typically on a schedule, via ETL/middleware, **Bulk API 2.0**, or **Change Data Capture** to drive deltas. Used for keeping a system of record and Salesforce in sync at high volume.
- **Remote Call-In**: An external system creates/reads/updates/deletes Salesforce data. Implemented with the **REST API**, **SOAP API**, **Bulk API**, or custom **Apex REST/SOAP** web services.
- **UI Update Based on Data Changes**: Push data changes to the Salesforce UI in near real time using the **Streaming API** (PushTopics), **CDC**, or **Platform Events** consumed by `lightning/empApi` in LWC.
- **Data Virtualization**: Access external data in real time without persisting it in Salesforce, via **Salesforce Connect** with an **OData** adapter (or a custom Apex adapter) exposing external objects (`__x`).
- **Named Credentials**: Declarative store for an endpoint URL plus auth (Basic, OAuth, JWT, etc.). The callout references `callout:MyNamedCred/path`; credentials are encrypted and decoupled from code so endpoints/secrets change without redeploying Apex. Removes hardcoded secrets and satisfies CRUD/security hygiene.
- **Platform Events vs. Change Data Capture**: Platform Events are custom, developer-defined messages (`__e` suffix, no tab) for both inbound and outbound business-logic-driven events. CDC is automatic — Salesforce publishes change events (create/update/delete/undelete) for selected objects to `/data/<Object>ChangeEvent` (standard) or `/data/<Object>__ChangeEvent` (custom), with no schema you maintain. Both use a pub/sub model over the Streaming API with a **replay ID** for durable replay.

## Best practices / guardrails
- **Default to asynchronous / event-driven.** Synchronous request/reply only when low latency and an immediate result are mandatory; otherwise async improves resilience and decoupling.
- **Use Named Credentials for every callout.** Never hardcode endpoints or secrets in Apex.
- **Design for idempotency and retries**, especially for fire-and-forget and inbound webhooks, since at-least-once delivery can replay messages.
- **Use Bulk API for large data volumes** so processing runs in the background and does not tie up the UI; tune batch sizes and use parallel processing.
- **Prefer event-driven over direct external REST writes** to keep the architecture loosely coupled — let external systems publish events that platform-event-triggered Flows/Apex handle, rather than writing records directly.
- **Prevent recursion** by excluding the integration user from re-triggering CDC/event publication.
- **Don't name a Platform Event the same as a standard/custom object** to avoid channel/naming collisions.
- **Track replay IDs** on subscribers so a restarted consumer resumes without gaps or duplicates.
- Enforce CRUD/FLS on inbound writes (`WITH USER_MODE` / `Security.stripInaccessible`) and bulkify all DML/SOQL in event handlers.

## Gotchas & limits
- **Apex callouts: max 100 callouts per transaction** (HTTP requests + Web service calls combined).
- **Callout timeout: 10 seconds default; configurable per request up to 120,000 ms (120 s).**
- A transaction with a pending uncommitted DML cannot make a callout — commit/finish DML first, or use async (`@future(callout=true)`, Queueable, or Continuation for long-running synchronous-feeling callouts).
- **Platform Events / CDC are at-least-once delivery, not exactly-once** — subscribers must dedupe.
- Platform Events and CDC have publishing and delivery **allocations** (daily event delivery to CometD/empApi clients and to async subscribers); high-volume events and event retention (replay window, typically up to 72 hours) must be designed around. Confirm current per-edition allocations in the org's limits before relying on them.
- **Outbound Messaging** is SOAP-only and fire-and-forget; it retries but offers no synchronous response path.
- **Salesforce Connect external objects (`__x`)** have query/relationship limitations vs. native objects (e.g., limited reporting, callout latency on every access, row/paging limits).
- The official guide now lives at `architect.salesforce.com/fundamentals/integration-patterns` (the old `developer.salesforce.com` atlas URL 301-redirects there); that page blocked automated fetch, so pattern definitions below were corroborated from the Apex Hours and Salesforce Ben summaries plus the official Apex callout limits doc.

## Code / config patterns

Named Credential callout (Apex):
```apex
public with sharing class OrderCalloutService {
    // Reference the Named Credential; endpoint + auth resolved at runtime.
    public static HttpResponse postOrder(String body) {
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:ERP_System/services/orders'); // ERP_System = Named Credential
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setTimeout(120000); // max 120s
        req.setBody(body);
        return new Http().send(req);
    }
}
```

Asynchronous callout (fire-and-forget) — DML-safe:
```apex
public with sharing class AsyncNotifier {
    @future(callout=true)
    public static void notifyExternal(Set<Id> recordIds) {
        // future method runs after DML commits, allowing the callout
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:ERP_System/notify');
        req.setMethod('POST');
        req.setBody(JSON.serialize(recordIds));
        new Http().send(req);
    }
}
```

Publishing a Platform Event:
```apex
public with sharing class OrderEventPublisher {
    public static void publish(String orderId, String status) {
        Order_Update__e evt = new Order_Update__e(
            Order_Id__c = orderId,
            Status__c   = status
        );
        Database.SaveResult sr = EventBus.publish(evt);
        if (!sr.isSuccess()) {
            for (Database.Error err : sr.getErrors()) {
                System.debug('Publish failed: ' + err.getMessage());
            }
        }
    }
}
```

Subscribing to a Platform Event with an after-insert trigger:
```apex
trigger OrderUpdateTrigger on Order_Update__e (after insert) {
    List<Task> followUps = new List<Task>();
    for (Order_Update__e evt : Trigger.New) {
        followUps.add(new Task(Subject = 'Order ' + evt.Order_Id__c + ' -> ' + evt.Status__c));
    }
    if (!followUps.isEmpty()) insert followUps; // bulkified DML
}
```

CDC channel subscription in an LWC (near-real-time UI update):
```javascript
import { subscribe, onError } from 'lightning/empApi';

const channel = '/data/AccountChangeEvent'; // standard object CDC channel
subscribe(channel, -1, (event) => {
    // event.data.payload.ChangeEventHeader has changeType, recordIds, etc.
    console.log('CDC payload', JSON.stringify(event.data.payload));
}).then((sub) => console.log('Subscribed to', sub.channel));
onError((err) => console.error('empApi error', JSON.stringify(err)));
```

## Sources
- https://architect.salesforce.com/fundamentals/integration-patterns (official guide; 301 from the developer.salesforce.com atlas URL — page blocked automated fetch)
- https://www.apexhours.com/salesforce-integration-pattern-best-practices/
- https://www.salesforceben.com/integration-using-change-data-capture-and-platform-events/
- https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_timeouts.htm
