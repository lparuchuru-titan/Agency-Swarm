# NEXTGEN2 — Architecture Overview (org-specific)
_Internal reference for the advanced-salesforce-developer skill. Source: code analysis of the NEXTGEN2 sandbox._

## What this org is
A large, mature ServiceTitan Salesforce org built on the **SteelBrick CPQ (`SBQQ__`)** + **Salesforce Billing (`blng__`)** managed packages, heavily extended. Scale: ~1,688 Apex classes, 90 LWCs, 132 Aura bundles, 224 objects, 129 triggers, 131 flows, 510 layouts, 252 permission sets. `force-app` is the only package dir.

## Domain map (by Apex naming prefix)
| Prefix | ~Count | Domain |
| --- | --- | --- |
| `ST_` | ~386 | Core business logic (cases, opps, assets, onboarding, integrations) |
| `STCB_` | ~213 | Billing & commerce: order→invoice→usage→tax→payment→provisioning (see [[stcb-billing-subsystem]]) |
| `asb_` | ~74 | App Store / marketplace (DAO/DO pattern) |
| `OSCPQ_` | ~22 | SteelBrick CPQ automation (quote/contract/order, renewals) |
| `SAL_` | ~24 | Sales (renewals, onboarding helpers) |
| `AI*` | ~17 | AI agent (Claude-based) — see [[ai-agent-subsystem]] |
| `ProductCatalog*` | 4 | NextGen Quoting catalog engine — see [[nextgen-quoting-runtime]] |

## End-to-end spine
Opportunity → **`nextGenQuotingBase`** (LWC) → **`ProductCatalogService`** (Apex) → **`SBQQ__LookupData__c`** rule engine ([[lookupdata-rule-engine]]) → cart → **`CartToQuoteModelTransformer`** → `SBQQ__QuoteLine__c` (delete+insert) → `SBQQ__Quote__c` → Order/OrderItem → **STCB_*** billing → `SBQQ__Subscription__c` → provisioning / `Onboarding__c`.

## Patterns
- **No fflib.** Hand-rolled **Selector + Service** split; DML is direct (no Unit-of-Work).
- **One trigger per object** → static `{Object}TriggerHelper` by DML context; bypass via `TriggerHelper.isBypassTrigger()` / `Trigger_Settings__mdt`; recursion via `ST_Recursionhandler`.
- **Config-driven**: dozens of behaviors keyed off Custom Labels + `CPQ_Setting__mdt` / `ORG_Setting__mdt` / `Trigger_Settings__mdt`. A missing/empty config silently changes runtime.
- **Async**: Queueable preferred over `@future`; Batch + Schedulable for bulk/recurring.
- **Reflection dispatch**: usage rating/amend services and entitlement impls are resolved at runtime via `Type.forName(Product2.<field>)` — a string field on Product2 is the real switchboard (no compile-time safety).

## Related notes
[[nextgen-quoting-runtime]] · [[lookupdata-rule-engine]] · [[stcb-billing-subsystem]] · [[amendment-renewal-usage-rating]] · [[ai-agent-subsystem]] · [[pantheon-2026-cpq]] · [[data-model-and-automation]]
