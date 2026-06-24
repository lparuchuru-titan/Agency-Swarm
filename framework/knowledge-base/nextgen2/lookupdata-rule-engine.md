# SBQQ__LookupData__c Rule Engine (org-specific)
_The generic rule table that drives NextGen Quoting behavior. Source: code analysis._

`SBQQ__LookupData__c` is a single generic table partitioned by `SBQQ__Category__c`. One query (`ProductCatalogSelector.getLookupData()`), one parse pass (`ProductCatalogService.buildLookupDataMaps`), attached to each catalog item.

## Categories
| Category | Source field(s) | Effect |
| --- | --- | --- |
| Auto Add Mappings | `Auto_Add_Products__c` (`;`-delimited child **Ids**, Text(255)) | Which children auto-attach to a parent → `item.autoAddProducts` |
| NextGen ListPrice Override | `Discounted_Product__c` (child **Code**) + `Auto_Discount__c` (percent) | Per-child bundle discount; presence flips parent into "bundle mode" → `item.listPriceOverrides` |
| Product Dependencies | `Product_Dependencies__c` (AND) / `Product_Dependencies_OR__c` (OR) | Gating before add |
| Product Exclusions | `Product_Exclusions__c` | Mutually exclusive products |
| Marketing Pro Mapping | `Marketing_Package__c`, tiers, `Unit_Price__c`, `Country__c` | Marketing Pro tier/addon config (product `MP00XX`) |
| NextGen Price Calculation | `Price_Calculation__c` (lookup) | Custom pricing calc records |
| Amendment Core Package Swap | `Core_Package_Family/Tier/Rank__c` | Core-for-core swap families |

Note the **key asymmetry**: Auto-Add keys children by **Id**; ListPrice Override keys the same children by **ProductCode**. Keep both in sync.

## Pricing decision (the bundle-mode rule — critical)
Implemented in LWC `nextGenQuotingBaseListPriceOverride.js` (`shouldFlagAsOverrideAddon`) + `addAutoAddProductToCart` in `nextGenQuotingBase.js`:
- Parent has **no** overrides → every auto-add child = **catalog price**.
- Parent **has** overrides, child **in** map → apply that % (100% → $0, 0% → full price).
- Parent has overrides, child **not** in map → **$0** ("implicitly included"). ← the trap.

So to keep a chargeable usage auto-add priced under a bundle parent, it **must** have an explicit `0%` override row; otherwise it is silently zeroed.

## Gotchas
- `autoAddProductMap.put(parentId, …)` **overwrites** per parent → can't split a parent's children across two "Auto Add Mappings" rows (last wins).
- `Auto_Add_Products__c` is **Text(255)** → ~15 child Ids max (use 15-char Ids). Pantheon Max sits at 239/255.
- The LWC normalizes child Ids to canonical 18-char regardless of what's stored.

## Files
`classes/ProductCatalogService.cls` (parse, ~lines 828–1003), `ProductCatalogSelector.cls` (query, ~186–220); `lwc/nextGenQuotingBase/nextGenQuotingBaseListPriceOverride.js`, `nextGenQuotingBaseHelpers.js`. Full write-up: `docs/NextGen_AutoAdd_Logic.html`. Related: [[nextgen-quoting-runtime]], [[pantheon-2026-cpq]].
