#!/usr/bin/env python3
"""Compare Product Attributes sheet expectations vs NEXTGEN2 Product2 query JSON."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CORE_DESC = (
    "Run your business — core scheduling, dispatching, call booking, invoicing, "
    "pricebook, and reporting functionality, with basic AI-assist capabilities. "
    "The reliable operational foundation."
)
FIELD_DESC = (
    "Win more jobs in the field — diagnose, quote, follow-up, install, and support automation."
)
DEMAND_DESC = (
    "Grow your revenue — AI-orchestrated demand generation, call booking, and dispatching."
)
MAX_DESC = (
    "Automate your business — ST's full AI roster with customization. Flagship ST product "
    "with end to end automation built in across the entire contractor funnel. "
    "Maximize the power of the Trades native Agentic OS."
)
FIELD_ADDON_CUST = (
    "Win more jobs in the field — diagnose, quote, follow-up, install, and support automation."
)
CREDIT_DESC = "Voice Agent prepaid credit commitment SKU for Pantheon Max bundles."

# Sheet-aligned expected values (Product Attributes tab gid 1350702246)
# Name column intentionally excluded from comparison.
EXPECTED: dict[str, dict] = {}

def _base(code, cfn, desc, cust, cat, grp, promo, st_type, bundle=True):
    EXPECTED[code] = {
        "Customer_Facing_Product_Name__c": cfn,
        "Description": desc,
        "Customer_Description__c": cust,
        "NRR_Product_Codes__c": False,
        "Product_Category__c": cat,
        "Grouping__c": grp,
        "Product_Subscription_Term__c": "Month to Month",  # sheet: monthly / term 1
        "ST_Product_Type__c": st_type,  # sheet ? for Core → Core; others implied Pro
        "Promotion_Product_Grouping__c": promo,  # sheet formulas → picklist mapping
        "Family": "Recurring Revenue",
        "SBQQ__BillingType__c": "Advance",
        "ST_Charge_Type__c": "Recurring - Usage + Min",
        "SBQQ__ChargeType__c": "Recurring",
        "SBQQ__BillingFrequency__c": "Monthly",
        "SBQQ__SubscriptionTerm__c": 1,
        "ST_ProductCode__c": "ST_Legacy_0",
        "IsActive": True,
        "SBQQ__Component__c": False,
        "Core_Product__c": False,
        "Teams_Allowed_to_Sell__c": "Corp Sales;Ent Sales;PAMs",
        "Billing_Country__c": "United States;Canada",
        "SBQQ__SubscriptionType__c": "Renewable",
        "SBQQ__SubscriptionPricing__c": "Fixed Price",  # sheet: Fixed
        "SBQQ__QuantityEditable__c": True,
        "Bundle_SKU_Flag__c": bundle,
        "blng__BillingRule__c": None,
        "SBQQ__TaxCode__c": None,
        "blng__TaxRule__c": None,
        "blng__RevenueRecognitionRule__c": None,
        "Revenue_Category__c": None,
        "Revenue_Treatment__c": None,
    }

for code in ("AOS001 (Per MT)", "AOS002 (GMV)"):
    _base(code, "Core", CORE_DESC, CORE_DESC, "Core", "Core", "Core", "Core")
_base("FAI001 (Per MT)", "Field", FIELD_DESC, FIELD_DESC, "Unified Max", "Field", "Pro Product - Subscription", "Pro")
_base("FAI002 (GMV)", "Field", FIELD_DESC, FIELD_DESC, "Unified Max", "Field", "Pro Product - Subscription", "Pro")
_base("DAI001 (Per MT)", "Demand", DEMAND_DESC, DEMAND_DESC, "Unified Max", "Demand", "Pro Product - Subscription", "Pro")
_base("DAI002 (GMV)", "Demand", DEMAND_DESC, DEMAND_DESC, "Unified Max", "Demand", "Pro Product - Subscription", "Pro")
_base("MAI001 (Per MT)", "Max", MAX_DESC, MAX_DESC, "Unified Max", "Max", "Pro Product - Subscription", "Pro")
_base("MAI002 (GMV)", "Max", MAX_DESC, MAX_DESC, "Unified Max", "Max", "Pro Product - Subscription", "Pro")
_base("FA0001", "Field Addon", FIELD_DESC, FIELD_ADDON_CUST, "All Pro", "Field", "Pro Product - Subscription", "Pro")
_base("FA0002", "Field Addon", FIELD_DESC, FIELD_DESC, "All Pro", "Field", "Pro Product - Subscription", "Pro")
_base("DA0001", "Demand Addon", DEMAND_DESC, DEMAND_DESC, "All Pro", "Demand", "Pro Product - Subscription", "Pro")
_base("DA0002", "Demand Addon", DEMAND_DESC, DEMAND_DESC, "All Pro", "Demand", "Pro Product - Subscription", "Pro")
_base("MA0001", "Max Addon", MAX_DESC, MAX_DESC, "All Pro", "Max", "Pro Product - Subscription", "Pro")
_base("MA0002", "Max Addon", MAX_DESC, MAX_DESC, "All Pro", "Max", "Pro Product - Subscription", "Pro")

# VL0001 — sheet row ambiguous; credit SKU expectations
EXPECTED["VL0001"] = {
    **EXPECTED["AOS001 (Per MT)"],
    "Customer_Facing_Product_Name__c": None,
    "Description": CREDIT_DESC,
    "Customer_Description__c": CREDIT_DESC,
    "Product_Category__c": None,
    "Grouping__c": None,
    "Promotion_Product_Grouping__c": None,
    "ST_Product_Type__c": "Pro",
    "Bundle_SKU_Flag__c": False,
}


from typing import Optional

def norm_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def query_sf() -> list[dict]:
    q = (
        "SELECT ProductCode, Customer_Facing_Product_Name__c, Description, "
        "Customer_Description__c, NRR_Product_Codes__c, Product_Category__c, Grouping__c, "
        "Product_Subscription_Term__c, ST_Product_Type__c, Promotion_Product_Grouping__c, "
        "Family, SBQQ__BillingType__c, ST_Charge_Type__c, SBQQ__ChargeType__c, "
        "SBQQ__BillingFrequency__c, SBQQ__SubscriptionTerm__c, ST_ProductCode__c, IsActive, "
        "SBQQ__Component__c, Core_Product__c, Teams_Allowed_to_Sell__c, Billing_Country__c, "
        "SBQQ__SubscriptionType__c, SBQQ__SubscriptionPricing__c, SBQQ__QuantityEditable__c, "
        "Bundle_SKU_Flag__c, blng__BillingRule__c, SBQQ__TaxCode__c, blng__TaxRule__c, "
        "blng__RevenueRecognitionRule__c, Revenue_Category__c, Revenue_Treatment__c "
        "FROM Product2 WHERE ProductCode IN ('AOS001 (Per MT)','AOS002 (GMV)','FAI001 (Per MT)',"
        "'FAI002 (GMV)','DAI001 (Per MT)','DAI002 (GMV)','MAI001 (Per MT)','MAI002 (GMV)',"
        "'FA0001','FA0002','DA0001','DA0002','MA0001','MA0002','VL0001')"
    )
    r = subprocess.run(
        ["sf", "data", "query", "--target-org", "NEXTGEN2", "--query", q, "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr)
        sys.exit(1)
    return json.loads(r.stdout)["result"]["records"]


def main() -> None:
    records = query_sf()
    by_code = {r["ProductCode"]: r for r in records}
    missing_products = sorted(set(EXPECTED) - set(by_code))
    mismatches: list[str] = []
    matches = 0
    text_fields = {"Description", "Customer_Description__c"}

    for code in sorted(EXPECTED):
        if code not in by_code:
            continue
        exp = EXPECTED[code]
        act = by_code[code]
        for field, exp_val in exp.items():
            act_val = act.get(field)
            if field in text_fields:
                ok = norm_text(act_val) == norm_text(exp_val if isinstance(exp_val, str) else "")
            elif exp_val is None:
                ok = act_val is None or act_val == ""
            else:
                ok = act_val == exp_val
            if ok:
                matches += 1
            else:
                mismatches.append(f"| {code} | {field} | {exp_val!r} | {act_val!r} |")

    # Pricebook entries
    pbe_q = subprocess.run(
        [
            "sf", "data", "query", "--target-org", "NEXTGEN2", "--json",
            "--query",
            "SELECT COUNT() FROM PricebookEntry WHERE Product2.ProductCode IN "
            "('AOS001 (Per MT)','AOS002 (GMV)','FAI001 (Per MT)','FAI002 (GMV)',"
            "'DAI001 (Per MT)','DAI002 (GMV)','MAI001 (Per MT)','MAI002 (GMV)',"
            "'FA0001','FA0002','DA0001','DA0002','MA0001','MA0002','VL0001') "
            "AND Pricebook2.IsStandard = true",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    pbe_count = json.loads(pbe_q.stdout)["result"]["totalSize"]

    print("# Pantheon Product Attributes — Sheet vs NEXTGEN2")
    print()
    print(f"- Products in sheet: **{len(EXPECTED)}**")
    print(f"- Products found in SF: **{len(by_code)}**")
    if missing_products:
        print(f"- **Missing in SF:** {', '.join(missing_products)}")
    print(f"- Field checks passed: **{matches}**")
    print(f"- Field mismatches: **{len(mismatches)}**")
    print(f"- Standard PricebookEntries for these SKUs: **{pbe_count}** (sheet list price blank → expect 0)")
    print()

    if mismatches:
        print("## Mismatches")
        print()
        print("| ProductCode | Field | Sheet (expected) | Salesforce (actual) |")
        print("|-------------|-------|------------------|---------------------|")
        for line in mismatches:
            print(line)
    else:
        print("## All compared fields match sheet expectations.")
    print()
    print("## Notes")
    print("- **Name** not compared (per your request).")
    print("- Sheet **Promotion** columns J/K are CMRR formulas; SF uses picklist **Core** / **Pro Product - Subscription**.")
    print("- Sheet **Product Subscription Term** `1` mapped to picklist **Month to Month**.")
    print("- Sheet **ST Product Type** `?` on Core rows mapped to **Core**; Pro tiers to **Pro**.")
    print("- **VL0001** sheet row is ambiguous; compared to credit-SKU interpretation.")


if __name__ == "__main__":
    main()
