# Platform Events, Change Data Capture & Event-Driven Architecture
_Last refreshed (static open resources · no LLM) · 1 docs · 2026-07-26T02:00:40.280854+00:00_

**Focus:** Pub/Sub API, Platform Events, CDC, event replay, EDA patterns, decoupled integrations.

## Source excerpts

### Source: https://raw.githubusercontent.com/trailheadapps/event-driven-recipes/main/README.md [error]
HTTP 404 for https://raw.githubusercontent.com/trailheadapps/event-driven-recipes/main/README.md

### Source: https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Platform%20Event%20Recipes/PlatformEventPublishCallback.cls
/** * @description Demonstrates how to write Platform Event publish success and failure callbacks * @group Platform Event Recipes * @see PlatformEventRecipes */ public with sharing class PlatformEventPublishCallback implements EventBus.EventPublishFailureCallback, EventBus.EventPublishSuccessCallback { /** * Map that correlates event UUIDs with event data */ private Map eventMap; public PlatformEventPublishCallback(List eventInfos) { this.eventMap = new Map (); for (EventInfo eventInfo : eventInfos) { this.eventMap.put(eventInfo.EventUuid, eventInfo); } } /** * Callback for events that failed to publish * Note: this method is always called by the Automation user */ public void onFailure(EventBus.FailureResult result) { // Get event UUIDs from the result List eventUuids = result.getEventUuids(); // Sample use case: create a follow-up task for failed events insertTask(eventUuids, false); } /** * Callback for events that were successfully published * Note: this method is always called by the Automation user */ public void onSuccess(EventBus.SuccessResult result) { // Get event UUIDs from the result List eventUuids = result.getEventUuids(); // Sample use case: create a follow-up task for success events insertTask(eventUuids, true); } private void insertTask(List eventUuids, Boolean isSuccess) { // Load accounts related to events Set relatedAccountIds = new Set (); for (String eventUuid : eventUuids) { EventInfo eventInfo = this.eventMap.get(eventUuid); relatedAccountIds.add(eventInfo.accountId); } Map relatedAccounts = new Map ( [ SELECT OwnerId FROM Account WHERE Id = :relatedAccountIds WITH SYSTEM_MODE ] ); // Prepare and insert tasks List tasks = new List (); for (String eventUuid : eventUuids) { // Retrieve event data EventInfo eventInfo = this.eventMap.get(eventUuid); // Create a task on the related account Task t = new Task(); t.WhatId = eventInfo.accountId; t.ActivityDate = Date.today().addDays(1); if (isSuccess == true) { t.Subject = 'Follow up on successful event publishing.'; t.Description = 'Events published successfully. Event UUID: ' + eventUuid; } else { t.Subject = 'Follow up on event publishing failure.'; t.Description = 'Events failed to publish. Event UUID: ' + eventUuid; } t.OwnerId = relatedAccounts.get(eventInfo.accountId).OwnerId; tasks.add(t); } insert as system tasks; } /** * Data object that holds the minimum amount of information to identify our event and potentially republish it. * We recommend that you don't store all event fields to avoid hitting callback handler internal limits. */ public class EventInfo { public String eventUuid; public Id accountId; public EventInfo(String eventUuid, Id accountId) { this.eventUuid = eventUuid; this.accountId = accountId; } } }

### Source: https://raw.githubusercontent.com/salesforce/salesforcedx-vscode/develop/packages/salesforcedx-vscode-apex/README.md [error]
HTTP 404 for https://raw.githubusercontent.com/salesforce/salesforcedx-vscode/develop/packages/salesforcedx-vscode-apex/README.md

### Source: https://architect.salesforce.com/fundamentals/event-driven-architecture [error]
HTTP 404 for https://architect.salesforce.com/fundamentals/event-driven-architecture

## Summary
_Auto-generated excerpt index. Run `skill-refresh --tier open_deep` for LLM synthesis when stale._

## Sources
- https://raw.githubusercontent.com/trailheadapps/event-driven-recipes/main/README.md
- https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Platform%20Event%20Recipes/PlatformEventPublishCallback.cls
- https://raw.githubusercontent.com/salesforce/salesforcedx-vscode/develop/packages/salesforcedx-vscode-apex/README.md
- https://architect.salesforce.com/fundamentals/event-driven-architecture
