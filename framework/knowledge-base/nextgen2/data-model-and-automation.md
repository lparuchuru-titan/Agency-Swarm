# Data Model & Automation (org-specific)
_Core objects, heavy custom-field counts, flows, triggers. Source: code analysis._

## Core objects (most customized)
| Object | Scale | Role |
| --- | --- | --- |
| `SBQQ__QuoteLine__c` | ~341 custom fields | Line pricing, bundling (`NextGen_isParent__c`/`NextGen_ParentId__c`), `Line_Type__c`, `Billing_Treatment__c`, approvals |
| `SBQQ__Subscription__c` | ~137 custom fields | Recurring revenue / renewal / asset; billing treatment + provisioning |
| `Product2` | ~203 custom fields | Catalog brain — `Bundle_SKU_Flag__c`, `GMV_Pricing__c`, `Rate__c`, `True_MT__c`, `Entitlement_*__c`, `Provisioning_*`, `Usage_Rating_Service__c`/`Usage_Amendment_Service__c` (reflection dispatch) |
| `Onboarding__c` | ~476 fields | Implementation/provisioning hub |
| `Concession__c` | ~46 fields | Approval-tracked discounts/credits |
| `Promotion__c` | ~23 fields | Promos / free-month incentives / ramp deals |
| `Rate_Adjustment__c` | 15 fields | Geo/segment pricing, renewal uplift, FX |
| `Bundle_Definition__c` | 6 fields | Pantheon parent→child mapping ([[pantheon-2026-cpq]]) |
| `SCLblockPrice__c` / `Tenant__c` | 5 / 16 | Subscription block pricing / multi-tenant mapping |
| `Amendment_Batch__c` | — | Spine of usage→amendment ([[amendment-renewal-usage-rating]]) |

## Automation
- **Triggers (129)**: one per object → `{Object}TriggerHelper`. Notable: `OSCPQ_QuoteLineTrigger`, `OSCPQ_QuoteTrigger`, `OSCPQ_SubscriptionTrigger`, `ST_ProductTrigger`, `STCB_OrderTrigger`, `STCB_OrderItemTrigger`, `STCB_InvoiceTrigger`, `ST_AccountTrigger`, `ST_OpportunityTrigger`, `ST_OnboardingTrigger`, `ST_ConcessionTrigger`. Several `dlrs_*` triggers = Declarative Lookup Rollup Summary.
- **Flows (131)**: ~40 record-triggered after-save, ~7 before-save, ~7 scheduled, rest autolaunched/screen. Examples: `Quote_Before_Flow` (status/record-type), `Quote_After_Flow` (post-approval sync), `Subscription_on_Contract_Automation`, `Create_Workday_Sync_Requests`, many `Contact_To_Account_*` roll-ups.
- **Division of labor**: triggers carry bulk logic; flows carry routing/approvals/notifications/integration kicks.

## Config objects to know
`CPQ_Setting__mdt`, `ORG_Setting__mdt`, `Trigger_Settings__mdt`, `Annual_Renewal_Uplift__mdt`, `AI_Chat_Retention_Config__mdt`, `AI_Caching_Config__c`, plus many Custom Labels (`NextGen_Hidden`, `OnlyShowInNextGen`, `AusGMV`, `Core_Categories_*`, `FP_Shipping_*`). A missing/empty config silently changes runtime — check these first when debugging "it works in one org but not another."

Related: [[architecture-overview]], [[nextgen-quoting-runtime]].
