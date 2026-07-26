# Salesforce CPQ (SteelBrick) Fundamentals
_Last refreshed via SFDC Knowledge Swarm · Sources: 5 docs_

## Summary

Salesforce CPQ (originally SteelBrick, acquired by Salesforce in 2015) is a managed package — all of its objects and fields carry the `SBQQ__` namespace prefix. It sits on top of Sales Cloud and turns Opportunities/Accounts into configured, priced, and quoted deals. Its core is a **Quote → Quote Line** data model where bundles (Product → Feature → Option) are configured, **Product Rules** enforce configuration logic, and **Price Rules** automate pricing. Quotes flow downstream to Orders, Contracts, Subscriptions, Assets, and (with Billing) Invoices using the same data model.

For developers, the two main extension surfaces are the **Calculate Quote API** (server-side, Apex/REST, operating on a `QuoteModel` JSON) and the **JavaScript Quote Calculator Plugin (QCP)** (client-side hooks in the Quote Line Editor). Both operate on the in-memory `QuoteModel` / `QuoteLineModel` representation rather than directly on SObjects during calculation.

This note is directly relevant to any CPQ bundle project: bundle structure, product/price rules, lookup data, and how the calculation pipeline fires.

## Key concepts

### Core data model (object API names)
| Object | API name | Role |
|--------|----------|------|
| Quote | `SBQQ__Quote__c` | Top-level quoting record; child of Opportunity. Holds totals (`SBQQ__NetAmount__c`, etc.). |
| Quote Line | `SBQQ__QuoteLine__c` | One configured product on the quote. Bundle parent/child linked via `SBQQ__RequiredBy__c`. |
| Quote Line Group | `SBQQ__QuoteLineGroup__c` | Groups quote lines (e.g., by segment/location); represented by `QuoteLineGroupModel`. |
| Product | `Product2` (standard) | Catalog product. A bundle is a `Product2` with child Features/Options. |
| Product Feature | `SBQQ__ProductFeature__c` | A category/group of options inside a bundle. Has `Min Options` / `Max Options` selection limits. |
| Product Option | `SBQQ__ProductOption__c` | An individual selectable product within a Feature/bundle (quantity, default selection, bundled flag). |
| Configuration Attribute | `SBQQ__ConfigurationAttribute__c` | Reusable attribute set shown in a drawer under options to drive configuration. |
| Product Rule | `SBQQ__ProductRule__c` | Validation/Alert/Selection/Filter logic over a bundle/quote/quote line. |
| Error Condition | `SBQQ__ErrorCondition__c` | Trigger logic ("when") for a Product Rule. |
| Product Action | `SBQQ__ProductAction__c` | The "then" — add/remove/hide/show/enable/disable an option. |
| Configuration Rule | `SBQQ__ConfigurationRule__c` | Binds a Product Rule to a specific bundle (Product) so it is reusable. |
| Price Rule | `SBQQ__PriceRule__c` | Automates pricing; targets Quote, Quote Line, or Product Options. |
| Price Condition | `SBQQ__PriceCondition__c` | "When" a Price Rule fires. |
| Price Action | `SBQQ__PriceAction__c` | "Then" — what field gets set/adjusted. |
| Lookup Query | `SBQQ__LookupQuery__c` | Matches quote/product fields against a custom Lookup Data object to drive filter/price/selection decisions. |
| Summary Variable | `SBQQ__SummaryVariable__c` | Aggregates quote line data (Sum/Min/Max/Count/Average) for use in conditions. |
| Subscription | `SBQQ__Subscription__c` | Persisted recurring/term product after order; basis for renewals/amendments. |
| Contract | `Contract` (standard) | Holds subscriptions; renewal/amendment source. |
| Order | `Order` (standard) | Generated from the quote; same data model carries through. |

### Bundle structure
A **bundle** is a parent `Product2` configured with `Product Features`, and each Feature contains `Product Options`. Hierarchy: **Product → Feature → Option**. A bundle may have zero or many Features; a Feature may have many Options. `Min Options` / `Max Options` on the Feature enforce how many options the rep may select. On the quote, bundle children are stitched to the parent quote line via `SBQQ__RequiredBy__c`.

### Product Rule types
- **Validation** — blocks saving and shows an error until the user fixes the configuration.
- **Alert** — advisory message only; user may proceed.
- **Selection** — silently adds/removes/hides/shows/enables/disables options (no message).
- **Filter** — dynamically restricts which products appear in the bundle/catalog.

A Product Rule = `Error Condition` (when) + `Product Action` (then), optionally bound to a bundle via `Configuration Rule`, and optionally fed by a `Lookup Query`.

### Calculation pipeline (developer surfaces)
1. **Calculate Quote API** — server-side. Apex/REST `PATCH`, available since **Summer '16**. Takes a `QuoteModel` (representation of `SBQQ__Quote__c` plus `lineItems` and `lineItemGroups`) and a `callbackClass` string (an Apex class implementing the CPQ `CalculateCallback` interface). Callback is **required when evaluating quote-scoped product rules**. Supports JSON and Apex formats.
2. **JavaScript Quote Calculator Plugin (QCP)** — client-side hooks in the Quote Line Editor, each returning a Promise:
   - `onInit(lineItems)` — before formula fields evaluate.
   - `onBeforeCalculate(quote, lines)` — after formulas, before calculation.
   - `onBeforePriceRules(quote, lines)` — before price rule evaluation.
   - `onAfterPriceRules(quote, lines)` — after price rules.
   - `onAfterCalculate(quote, lines)` — after calculation, before formula re-eval; **cannot alter data**.
   - `isFieldVisible(fieldName, lineRecord)` / `isFieldEditable(fieldName, lineRecord)` — page-level field security; return Boolean; **cannot alter data**.

## Best practices / guardrails

- **Always use the namespace prefix** (`SBQQ__`) in SOQL, formulas, and Apex; never reference CPQ fields without it.
- **Configuration Rules for reuse:** bind a Product Rule to bundles via `SBQQ__ConfigurationRule__c` rather than duplicating rules per product.
- **Rank rules** when multiple rules target the same product/bundle so evaluation order is deterministic.
- **Push logic into declarative CPQ** (Product Rules, Price Rules, Summary Variables, Lookup Queries) before reaching for QCP/Apex — it is upgrade-safe and supported.
- **QCP should be lightweight and async-correct:** every hook must return a Promise; do heavy work server-side via the Calculate Quote API and a callback instead of in `onAfterCalculate`.
- **Lookup Data** lets you externalize pricing/eligibility matrices (e.g., region-based options) without hardcoding — match quote/product fields to the lookup object via `SBQQ__LookupQuery__c`.
- **Summary Variables** keep rule conditions readable (aggregate once, reference everywhere) instead of repeated rollups.

## Gotchas & limits

- **No batching in Calculate Quote API:** the API does not batch when creating/calculating quotes, so **performance degrades on quotes with large numbers of quote lines** — design bundles and rule counts with this in mind.
- **Quote-scoped product rules require a callback** — the Calculate Quote API will not resolve them without a `callbackClass` implementing `CalculateCallback`.
- **`quoteModel` / `quoteLineModel` have circular references** — they **cannot be `JSON.stringify`'d** directly in QCP; serialize only the needed sub-objects.
- **`onAfterCalculate`, `isFieldVisible`, `isFieldEditable` cannot alter data** — use them only for read/security decisions; mutate values in the `onBefore*` hooks.
- **QCP runs only in the Quote Line Editor**, not for calculations triggered headlessly (API/triggers) — keep authoritative logic server-side if both paths matter.
- **Model vs SObject:** during calculation you operate on the in-memory model (`record` wrapper), not on a committed `SBQQ__QuoteLine__c` row; saves happen after the pipeline completes.

## Code / config patterns

QCP skeleton (each hook returns a Promise):

```js
export function onBeforeCalculate(quote, lines, conn) {
    return new Promise((resolve, reject) => {
        // mutate line.record fields here, e.g. custom discount logic
        lines.forEach(line => {
            // line.record is the SBQQ__QuoteLine__c representation
        });
        resolve();
    });
}

export function isFieldVisible(fieldName, line) {
    // read-only security decision; cannot mutate data
    return fieldName !== 'SBQQ__CustomerDiscount__c' || line.record.Hide_Discount__c === false;
}
```

Calculate Quote API — Apex call with a callback (callback required for quote-scoped product rules):

```apex
// Apex class must implement the CPQ CalculateCallback interface
global class MyCalcCallback implements SBQQ.CalculateCallback {
    global void callback(String quoteJSON) {
        // quoteJSON is the recalculated QuoteModel; deserialize/persist as needed
        SBQQ.QuoteModel quote =
            (SBQQ.QuoteModel) JSON.deserialize(quoteJSON, SBQQ.QuoteModel.class);
        // ... act on recalculated totals ...
    }
}

// Trigger the calculation (callbackClass = name of the class above)
SBQQ.ServiceRouter.load(
    'SBQQ.QuoteAPI.QuoteCalculator',
    quoteId,
    null
);
```

Conceptual QuoteModel JSON shape passed to the Calculate API:

```json
{
  "record": { "attributes": { "type": "SBQQ__Quote__c" }, "Id": "a0X..." },
  "lineItems": [
    {
      "record": {
        "attributes": { "type": "SBQQ__QuoteLine__c" },
        "SBQQ__Quantity__c": 1,
        "SBQQ__RequiredBy__c": null
      },
      "key": "1"
    }
  ],
  "lineItemGroups": [
    { "record": { "attributes": { "type": "SBQQ__QuoteLineGroup__c" } }, "key": "g1" }
  ],
  "netTotal": 0,
  "customerTotal": 0
}
```

Each line/group `key` must be **unique within the quote** (used to wire bundle relationships in the model before Ids exist).

## Sources

- https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/cpq-quote-api-calculate-final.html
- https://developer.salesforce.com/docs/revenue/cpq-plugins/guide/cpq-dev-jsqcp-methods.html
- https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/cpq_developer_guide.pdf
- https://atrium.ai/resources/a-complete-guide-to-salesforce-cpq-objects/
- https://www.absyz.com/salesforce-cpq-product-rules/
