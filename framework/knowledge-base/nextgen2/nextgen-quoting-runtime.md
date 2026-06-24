# NextGen Quoting Runtime (org-specific)
_How the custom quoting experience loads, prices, and saves a quote. Source: code analysis._

## Flow
1. **LWC `nextGenQuotingBase`** (`lwc/nextGenQuotingBase/`, ~950KB, split into modules: `.js` orchestrator, `Calculations`, `Helpers`, `Utils`, `ListPriceOverride`, `Amendment`, `Agent`, `HeaderSchema`, `Constants`). Imperatively calls Apex.
2. **`ProductCatalogService.getProductCatalog(quoteId)`** (`classes/ProductCatalogService.cls`, ~1461 lines, `without sharing`) returns a `ProductCatalogResponse` with one `ProductCatalogItem` (~65 fields) per product. Bulk query → in-memory map builds → single product loop (no SOQL/DML in loop).
3. **`ProductCatalogSelector`** (`without sharing`, static SOQL only). Catalog eligibility: active, `SBQQ__Component__c != true` (unless whitelisted via Labels `OnlyShowInNextGen`/`NextGen_Hidden`), has active PricebookEntry, `NextGen_Eligible__c = true`.
4. Rep builds cart in browser; the LookupData rules ([[lookupdata-rule-engine]]) drive auto-add, $0/overrides, dependencies, exclusions.
5. **Save** → `CPQQuoteSaveService.saveQuote` → **`CartToQuoteModelTransformer.transformCart(cartJson, quoteId)`** builds `SBQQ__QuoteLine__c` via **DELETE + INSERT** (Ids null on insert). **Net-price math lives here**, not in the catalog.
6. **`QuoteModelToCartTransformer`** is the reverse path for editing an existing quote.

## Pricing inputs (catalog exposes; transformer applies)
- List price = first active `PricebookEntry.UnitPrice` (`getListPrice`).
- Block/tier: native `SBQQ__BlockPrice__c` **and** custom `SCLblockPrice__c` (two parallel models).
- Discount schedules: `SBQQ__DiscountSchedule__c`/`Tier`.
- GMV vs MT: `Product2.Rate__c != null` → GMV (`item.gmvRate`, bypasses approval buffer); `True_MT__c` → core/MT.
- Approval-rate buffers: `CPQ_Setting__mdt` + Canada/Roofing adjustments.
- Renewal uplift: `Rate_Adjustment__c` keyed by Business Focus + Size Segment.
- Ramps: eligible when product has `SBQQ__Dimensions__r` and is a subscription.

## Gotchas
- **Two catalog entry points**: legacy `ProductCatalogController` (simple, queries PricebookEntry directly, largely untested) vs production `ProductCatalogService`. Risk of divergence — use the Service.
- Catalog path runs **`without sharing`** and does **not** use `WITH USER_MODE` — deliberate (catalog must be visible) but flag for FLS/CRUD review.
- Net price is computed in `CartToQuoteModelTransformer`, so the LWC `Calculations.js` and the transformer must agree on the formula.
- Magic product code `MP00XX` (Marketing Pro container) is special-cased in the catalog loop.

## Files
`classes/ProductCatalogService.cls`, `ProductCatalogSelector.cls`, `ProductCatalogController.cls` (legacy), `CartToQuoteModelTransformer.cls`, `QuoteModelToCartTransformer.cls`; `lwc/nextGenQuotingBase/`. Tests: `ProductCatalogServiceTest`, `CartToQuoteModelTransformerTest`, `QuoteModelToCartTransformerTest`. Related: [[lookupdata-rule-engine]], [[pantheon-2026-cpq]].
