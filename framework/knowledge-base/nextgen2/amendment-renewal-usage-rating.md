# Amendment, Renewal & Usage-Rating Engine (org-specific)
_How usage overage becomes amendment billing, and how renewals cascade. Source: code analysis._

## Auto-amendment
A system amendment is a contract modification that bills usage **overage** (+proration). Usage rating writes `Amendment_Batch__c` rows; staggered batches drive them quote → order → activation:
- `STCB_AutoAmendQuoteBatchJob` → `STCB_ContractAmendService` (wraps CPQ `SBQQ.ContractManipulationAPI.ContractAmender`) → amendment quote.
- `STCB_AutoAmendHelper` stamps overage qty/dates, `Is_System_Amendment__c = true`.
- `STCB_AutoAmendOrderBatchJob` → Order/OrderItem + proration; `STCB_AutoAmendActivateOrderBatchJob` activates.
- Schedule is **time-offset, not `finish()`-chained**: Quote → +30m Order → +10m Activate. State machine on `Amendment_Batch__c.Status__c` (Generate Quote → In Progress → Activate Order → Completed/Error).

## Usage-rating services (strategy pattern, reflection-dispatched)
Selected at runtime in `STCB_TenantSummaryUsageService` from `Product2.Usage_Rating_Service__c` (rating) and `Usage_Amendment_Service__c` (amend), via `Type.forName().newInstance()`.
- **Interfaces**: `ISTCB_TenantUsageRatingService` (`publishTenantUsage`, `getOverage`) and `ISTCB_SystemAmendService` (`createAmendmentRequest`).
- **Slab** (`STCB_UsageWithSlabPricingRatingService` / `STCB_SlabPricingSystemAmendService`): usage spans stacked qty ranges; bills the delta across crossed tiers.
- **Tier** (`STCB_UsageWithTierPricingRatingService`): usage selects a single subscription tier; bills **qty 1** on first usage or tier change; tracks `BilledOrderProductId`.
- **Min-Commit** (`STCB_UsageWithMinCommitRatingService`, virtual base): bills `MAX(min, reported)` then increments above commit.
- **Arrear** (`STCB_UsageWithArrearBillingRatingService`): extends Min-Commit; bills all reported as incremental at period end.
- **Telecom** (`STCB_UsageWithTelPricingRatingServices`): standalone (does NOT implement the interface); writes `blng__Usage__c`/Orders directly; honors `Account.Defer_telecom_Fees__c`.

`getOverage()` = given cumulative usage vs already-billed, compute the new billable quantity this cycle.

## Renewal engine (4-stage cascade)
1. `OSCPQ_ContractRenewal_Batch` (sched `OSCPQ_ContractRenewal_Schedule`) — sets renewal-forecast flags, auto-activates draft contracts. **Note: the class is `OSCPQ_`-prefixed, not `STCB_`.**
2. `SAL_CreateRenewalOpptyController` (user-triggered on Closed Won) — creates Renewal Opportunity, clones lines to live assets.
3. `STCB_RenewalQuoteCreationBatch` (sched, batch size 1) — applies uplift to `SBQQ__Subscription__c.SBQQ__RenewalUpliftRate__c` from `Annual_Renewal_Uplift__mdt` (CPI/fixed).
4. `STCB_RenewalOrderCreationBatch` (sched, batch size 1) — orders the approved renewal quote; multi-tenant → `STCB_MultiTenantRenewalCascadeHelper` (master → per-tenant child Orders, `Master_Order_Product__c` links).

## Gotchas
- **Naming traps**: no `STCB_ContractRenewal_Batch` (it's `OSCPQ_`); two tier classes exist (`STCB_UsageWithTierPricingRatingService` current vs older `…TierPriceRatingService`) — confirm which is wired.
- Rating/amend dispatch is reflection from Product2 string fields — typo/rename silently breaks billing.
- Slab vs Tier overage math are fundamentally different — don't reuse one for the other.
- Telecom bypasses the standard rating→amendment pipeline.
- `SAL_RenewalOpptyUpdateBatch` is commented out/disabled — don't assume it runs.

## Key objects
`Amendment_Batch__c` (spine), `TenantSummary__c`/`TenantUsage__c`, `SBQQ__Quote__c`/`QuoteLine__c` (`Is_System_Amendment__c`), Order/OrderItem (`Master_Order_Product__c`), Contract (`SBQQ__Renewal*`), `blng__Usage__c`. Related: [[stcb-billing-subsystem]].
