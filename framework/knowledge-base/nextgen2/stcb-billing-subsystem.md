# STCB_* Billing & Commerce Subsystem (org-specific)
_~213 STCB_ classes. Vendors: `blng__` = Salesforce Billing, `SBQQ__` = CPQ. Source: code analysis._

## End-to-end flow
| Stage | Entry | Transition | Key objects |
| --- | --- | --- | --- |
| Order | `STCB_OrderTriggerHandler.afterInsert` → `STCB_OrderTriggerHelper.createEntitlements` | Trigger `STCB_OrderTrigger` (gated by `Trigger_Settings__mdt='ST_OrderTrigger'`); also `STCB_OrderActivationBatch` / REST `/order/process` | Order, OrderItem, SBQQ__Quote__c |
| Entitlement/Provision | `STCB_EntitlementService.createEntitlements(orderId)` | from Order afterInsert; offload to `STCB_EntitlementProcessor` (Queueable) when large | Entitlement, Tenant__c, TenantSummary__c |
| Invoice | `STCB_InvoicePlanService.generateInvoicePlanSchedule` | scheduled `STCB_AutoInvoiceBatch` + `STCB_AutoPostInvoiceBatchJob` | blng__Invoice__c/InvoiceLine__c/BillingSchedule__c |
| Usage | `STCB_UsageServiceEx` → rating service | REST ingest (`STCB_UsageAPI` v1 sync / `STCB_BulkUsageAPI` v2) → PE `Usage_Batch_Process__e` → `STCB_UsageBatchJob` | Usage_Batch_Record__c, TenantSummary__c, TenantUsage__c |
| Tax | `STCB_TaxCalculationAPI` (implements `blng.TaxEngines`) → `STCB_TaxHelper` | callout at invoice post | invoiceLine tax, Custom_Tax_Fields__c |
| Payment | `STCB_PaymentIntegrationSynchService` / `STCB_PaymentCalloutService.charge` | `STCB_PaymentIntegration_Batch` (charge) then `STCB_PaymentSync_Batch` (poll) | blng__PaymentTransaction__c, blng__Payment__c |

**Tax = Avalara** (AvaTax standard `callout:AvaTaxCreateAPI`; AvaCom telecom — split by `Product__r.AvaCom_Split__c`). **Payment gateway = Stripe**.

## REST APIs (@RestResource)
`/api/v1/order/process` (`STCB_OrderAPI`) · `/api/v1/quote/amend` (`STCB_SystemAmendQuoteAPI`) · `/api/v1/invoices` (`STCB_InvoiceAPI`) · `/api/v1/usage/publish` (`STCB_UsageAPI`) · `/api/v2/usage/publish` (`STCB_BulkUsageAPI`) · `/api/v1/payment/*` (`STCB_PaymentAPIService`) · `/api/v1/balance/*` (`STCB_BalanceService`) · `/api/v1/transactions/*` · `/api/v1/provisioning/*` (`STCB_TenantProvisioningService`) · `/api/v1/MTcascade/*` (`STCB_MultiTenantCascadeService`).

## Entitlements & provisioning
- `STCB_EntitlementService.createEntitlements(orderId)` — New/Amendment/Renewal per product group; dynamically loads `ISTCB_EntitlementService` impls per product via `Type.forName`.
- **Two confusingly-named provisioning services**: `STCB_ProvisioningService` *publishes outbound* requests; `STCB_TenantProvisioningService` is the *inbound REST callback* that writes tenant config back onto Entitlements.
- Multi-tenant: `STCB_MultiTenantCascadeService.createCascadeOrders()` routes by `Order_Batch__c.Queue_Type__c` to order-creation / amend / renewal cascade helpers.

## Gotchas
1. **Trigger gating via metadata** — flip `Trigger_Settings__mdt` ('ST_OrderTrigger') off and ALL order→entitlement/invoice automation silently stops.
2. **Usage rating = string-typed reflection** — `Product2.Usage_Rating_Service__c` holds the Apex class name, resolved via `Type.forName().newInstance()`. A typo/blank breaks billing with no compile error.
3. **Usage ingestion is async** — v2 writes `Usage_Batch_Record__c` then fires a platform event; not rated inside the API transaction.
4. **Payments are eventually consistent** across two batches (charge then sync). `blng__Payment__c` is created only on the later sync.
5. **Tax routing is product-data-driven** (`AvaCom_Split__c`) and dual-provider; misconfig silently routes to the wrong Avalara endpoint.
6. `STCB_ProvisioningEventLogService` insert is largely commented out — event logging may be a no-op. (Some PE/trigger names reported from constants — verify if load-bearing.)

Related: [[amendment-renewal-usage-rating]], [[architecture-overview]].
