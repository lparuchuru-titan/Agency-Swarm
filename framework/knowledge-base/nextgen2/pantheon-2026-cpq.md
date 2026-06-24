# Pantheon 2026 Max Bundles CPQ (org-specific)
_Epic SFDCLQ-7591. New bundle tiers (Core/Field/Demand/Max) on the NextGen runtime. Source: project work._

## Metadata (stories 7592–7595)
- **Product2** (7592): `Bundle_SKU_Flag__c`, `Visible_On_Quote_UI__c`, `Credit_Value__c`, `Credit_Bonus_Pct__c`, `Credit_Scope__c` (+ `Credit_ID__c`, `Per_MT_Free_Quantity__c`).
- **SBQQ__QuoteLine__c** (7593): `Line_Type__c` (Package; Included; Usage (auto-added); Usage (standalone); Prepaid (one-time)), `Billing_Treatment__c` (Per-seat recurring; Included entitlement (no usage charge); Chargeable usage (auto-added); Chargeable usage (standalone); Prepaid credit grant), `Included_Allotment__c`, `Overage_Rate__c`, `Overage_Discount__c`, `Credit_Eligible__c`.
- **SBQQ__Subscription__c** (7594): 10 fields incl. `External_Billing_ID__c` (External Id), `Provisioning_Status__c` (Pending/Provisioned/Failed), `Billing_Role__c`, `Credit_Balance__c`, `Credit_Exhausted_Date__c`.
- **Bundle_Definition__c** (7595): object (Auto Number `BD-{0000}`), fields `Parent_Product__c`/`Child_Product__c` (Lookup→Product2, **optional + SetNull** because Salesforce blocks required lookups to Product2), `Child_Price_On_Quote__c`, `Visible_To_Rep__c`, `Auto_Provision__c`, `Active__c`.

## Bundles & auto-add
- 8 base parents: Core `AOS001`, Field `FAI001`, Demand `DAI001`, Max `MAI001`, each × Per MT / GMV variant; plus add-on parents `FA0001/2`, `DA0001/2`, `MA0001/2`.
- **`Bundle_Definition__c`** holds parent→child mappings (84 records in NEXTGEN2) — but it is **read only by the `pantheonBundleQuoteLineView` viewer LWC, NOT by the runtime.**
- **Runtime auto-add** is driven by [[lookupdata-rule-engine]]: "Auto Add Mappings" (child Ids) + "NextGen ListPrice Override" (included children @100% → $0; chargeable usage SKUs @0% → stay priced — the required guard). Wired by `scripts/apex/pantheon/10_wire_included_children_autoadd.apex`.
- Per-tier auto-add usage SKUs: VA `CCP008`, SMS `GS0001`, Marketing `MP0041/MP0042/MP0073/SM0003`.

## Enterprise Hub
A **feature flag, not a SKU** ("Not A sku. Its a feature" in the authoritative sheet). Correctly **absent** from Bundle Definitions / auto-add. Model as an entitlement on the bundle parent (Product2 `Entitlement_*__c`) provisioned by the onboarding trigger (stories 7611–7614); tenant-scoped for Max Add-On. Jira 7595/7596 wording ("ENTHUB" as $0 child) contradicts the sheet — needs PM correction. Full write-up: `docs/Enterprise_Hub_Explained.html`.

## Data delivery
All Pantheon data is **environment-specific** (record Ids differ) — re-run `scripts/apex/pantheon/*.apex` per org (products, bundle defs, auto-add mappings, overrides). Do not copy records. Runbook: `docs/Pantheon2026_CPQ_Sandbox_Runbook.md`. Tracking convention: each story has `Dev Task` (PR + Merge Label) + `PDS` (post-deployment steps for DevOps) sub-tasks.

## Open items
Page-layout placement of new fields (CPQ Product / Quote Line / Subscription layouts) pending; LWC runtime UI smoke test for auto-add; widen `Auto_Add_Products__c` to Long Text Area (Text(255) near limit on Max); BYOA/SMS-allotment/VA-per-outcome rates are sheet-side TBD (due 2026-06-30).

Related: [[nextgen-quoting-runtime]], [[lookupdata-rule-engine]].
