"""Five lender LenderProfile entries — each described by a free-text rate sheet.

Architecture: there is no policy engine, no subscription pre-filter, no
strategy knobs. Every bid decision — including out-of-box declines —
runs through the LoRA-fine-tuned underwriter. A lender's policy is its
``rate_sheet_text``, full stop.

The rate sheet plays two roles, both of which are consequences of the same
text:

  * **Training seed.** ``lora_training/synthetic_data.py`` runs the base
    model with the rate sheet inlined as a system prompt to label synthetic
    bid requests. The LoRA learns to imitate those labels; after training,
    the rate sheet is "in the weights."
  * **Inference fallback.** With ``LORA_MODE=prompt`` the underwriter sends
    the rate sheet directly to the base model as a system prompt. Same text,
    same decisions, no LoRA required — the demo degrades gracefully if
    multi-LoRA serving misbehaves.

To onboard a new lender, paste their rate sheet into a new ``LenderProfile``
and add it to ``LENDER_PROFILES``. That's the entire onboarding contract.
"""
from __future__ import annotations

from shared.models import LenderProfile

LORA_ADAPTERS_DIR = "./lora_adapters"


# Decision schema — appended to whichever system prompt the underwriter
# sends (rate sheet for prompt mode, schema-only for multi mode where the
# LoRA carries the policy in its weights).
DECISION_SCHEMA = """\
You are an auto-loan underwriter. Read the bid request and produce a
final pricing decision following your institution's policy.

Bid request fields:
  applicant_fico (int 300-850), loan_amount (USD), vehicle_type (new|used|ev),
  term_months (int), state (2-letter), dealer_reserve_bps (int).

Respond with ONLY a JSON object — no prose, no code fences, no markdown:
{
  "decision": "approve" | "decline" | "counter",
  "apr_bps": <int 0-10000, basis points; 100 bps = 1%>,
  "term_months": <int 12-120>,
  "max_amount_usdc": <number>,
  "max_ltv_bps": <int 0-20000, basis points; 10000 = 100% LTV>,
  "cash_down_required_usdc": <number, default 0>,
  "dealer_reserve_bps": <int 0-500>,
  "stipulations": [<string>, ...],
  "confidence": <float 0.0-1.0>,
  "rationale": "<one paragraph referring to applicant specifics>"
}

If the bid request falls outside your rate sheet — wrong vehicle type,
FICO out of range, term too long, etc. — respond with decision="decline",
zero amounts, and a brief rationale citing the policy reason.
"""


# ---------- Lender rate sheets ----------


PRIME_BANK = LenderProfile(
    id="prime-bank",
    name="STCU Retail Auto",
    lora_alias="stcu_retail_auto",
    rate_sheet_text="""\
STCU RETAIL VEHICLE FINANCING PROGRAM (effective April 2026)
Source: "Indirect-Vehicle-Rates (1).pdf"

PROGRAM NOTES
- Dealer compensation: 2.00% of amount financed, max $1,500, chargeback 120 days.
- Add +0.50% rate for terms 79-84 months.
- 85-96 month terms allowed only when: score >= 680, amount financed >= $40,000,
  model year <= 3 years old, max 115% LTV including TT&L.
- Minimum financed amount for dealer compensation: $5,000.

INELIGIBLE
- Straw purchases, salvaged/branded/lemon vehicles.
- Commercial/cargo/conversion vans, rideshare/taxi use, business-titled vehicles.
- Trustee or power-of-attorney contracts.

RATE MATRIX (1-78 month base term)
- Model years 2019-2027:
  - 730+: 4.99%
  - 680-729: 5.74%
  - 650-679: 6.24%
  - 620-649: 7.24%
  - 590-619: 9.74%
  - 0-589: 13.74%
- Model years 2016-2018:
  - 730+: 6.99%
  - 680-729: 7.74%
  - 650-679: 8.24%
  - 620-649: 9.24%
  - 590-619: 11.74%
  - 0-589: 15.74%
- Model years 2011-2015:
  - 730+: 8.99%
  - 680-729: 9.74%
  - 650-679: 10.24%
  - 620-649: 11.24%
  - 590-619: 13.74%
  - 0-589: 17.74%
- 85-96 month special (model years 2024-2027 only):
  - 730+: 6.49%
  - 680-729: 7.24%
  - lower tiers: not eligible

LTV / PRODUCT LIMITS
- Loan terms and LTV depend on JD Power retail (used) or MSRP (new).
- GAP max $1,500.
- STCU does not accept loans exceeding 36% APR after products.

STIPULATIONS / DOCUMENTATION
- Valid US driver's license for applicants.
- VOI required for scores < 650, no-score FTB, and certain self-employed borrowers.
- Proof of insurance required.
- Must qualify for STCU membership.
""",
)


MID_MARKET = LenderProfile(
    id="mid-market",
    name="Unitus Community CU",
    lora_alias="unitus_community_cu",
    rate_sheet_text="""\
UNITUS COMMUNITY CREDIT UNION - CONSUMER LOAN RATE SHEET
Source: "consumer-rates.pdf"

PRICING BASIS
- Uses score tiers: 740+, 739-700, 699-660, 659-610, 609-560, 559 or below.
- Published APRs include:
  - 0.25% ACH autopay discount
  - 0.25% e-statements discount
- If discounts are not maintained, service termination fees may be added.

NEW AUTO (model years 2019+)
- Up to 36 months: 1.69% to 14.44% by score tier.
- 37-60 months: 2.19% to 14.94%.
- 61-66 months: 2.44% to 15.19%.
- 67-75 months: 2.69% to 15.44%.
- 76-84 months (score >= 610): 2.94% to 9.44% (lowest tiers ineligible).

USED AUTO (model years 2018-2016)
- Up to 36 months: 1.94% to 14.69%.
- 37-60 months: 2.44% to 15.19%.
- 61-66 months: 2.69% to 15.44%.
- 67-75 months: 2.94% to 15.69%.
- 76-84 months: 3.19% to 9.69% (lowest tiers ineligible).

OLDER AUTO (2015 and older)
- Add +0.25% for 2018-2016.
- Add +1.00% for 2015 and older.
- Max term shorter on high mileage; >100k miles max term 66 months.

ELIGIBILITY / CONSTRAINTS
- Vehicle cannot have salvage/rebuilt/lemon/branded title.
- Maximum financing/term determined by value, model year, mileage, and score.
- Taxes/title/registration/doc fees and some backend products may be financed
  subject to limits.
""",
)


SUBPRIME = LenderProfile(
    id="subprime",
    name="Exeter Finance",
    lora_alias="exeter_finance",
    rate_sheet_text="""\
EXETER RATE SHEET / PROGRAM GUIDELINES (updated 4.25.24)
Source: "Exeter_4.25.24.pdf"

PROGRAMS
- Exeter: score floor ~400 (will consider 0), rates as low as 10.95%.
- ExeterPLUS: score 620+, rates as low as 9.95%.
- Dealer markup of customer APR not permitted; participation as power flat.

CORE LIMITS
- Max amount financed: $50,000.
- Min amount financed: $6,000.
- Term: up to 78 months (tier-dependent).
- Vehicles: new or used, up to 13 years old, up to 200k miles.
- Typical minimum monthly income: $1,700 individual / $2,500 joint.

ADVANCE / LTV
- Front-end advance up to 128%.
- LTV up to 141%.
- Backend limits (program/tier dependent), e.g. GAP cap ~ $1,200.

STIPULATION-HEAVY UNDERWRITING
- POI/VOE requirements by employment type and risk.
- Insurance requirements (comprehensive/collision, deductible limits).
- Valid ID and title requirements.
- Pre-funding confirmation calls.
- No deferred down payments (except where state allows).

INELIGIBLE / HIGH-RISK EXCLUSIONS
- No rideshare/commercial-use vehicles.
- No salvage/flood/branded/TMU/etc.
- No recent repos in disallowed windows by program.
- No straw purchases.
""",
)


USED_ONLY_CU = LenderProfile(
    id="used-only-cu",
    name="Family Savings CU",
    lora_alias="family_savings_cu",
    rate_sheet_text="""\
FAMILY SAVINGS CREDIT UNION - INDIRECT AUTO RATE SHEET (effective 09/01/2025)
Source: "FSCU Indirect Auto Rate Sheet 09012025 (1).pdf"

SCORE TIERS
- 740+, 739-700, 699-650, 649-600, 599-525, 524 and below.
- Equifax FICO Auto 8 used; joint uses highest score.

NEW/USED AUTOS 7 YEARS OR NEWER
- Up to 36 months: 4.99% to 14.75%.
- 37-60 months (>= $10k): 5.24% to 15.25%.
- 61-72 months (>= $20k): 5.49% to 15.50%.
- 73-84 months (>= $30k): 5.99% to 15.50%.
- For model years current-3 to current-7, add +1.00% to table.

OLDER COLLATERAL (current year - 8 or older)
- Up to 36 months: 8.24% to 15.75%.
- 37-60 months (>= $10k): 10.24% to 15.75%.
- Older collateral valuation based on trade-in value.

MILEAGE / TERM RULES
- >40,000 miles: max term 72 months.
- >100,000 miles: max term 60 months and trade-in valuation.
- >150,000 miles: max term 36 months for older collateral.

DEALER RESERVE / LTV
- Dealer reserve: flat 1.50% of amount financed.
- LTV by score and collateral age (e.g., top tiers up to 115% on newer collateral).

SPECIAL NOTES / STIPS
- Valid US driver's license required.
- No commercial/cargo vans, salvaged/rebuilt/lemon vehicles.
- Backend product and term-extension constraints apply.
""",
)


EV_CAPTIVE = LenderProfile(
    id="ev-captive",
    name="Crouse Federal Credit Union",
    lora_alias="crouse_federal_cu",
    rate_sheet_text="""\
CROUSE FCU - 251 GRID LOAN RATE SHEET (as of 01/17/2025)
Source: "251-Loan-Grid-Rate-Sheet-01172025.pdf"

AUTO PURCHASE / REFINANCE (2023-2025)
- 36 mo: 4.49%
- 48 mo: 4.89%
- 60 mo: 4.99%
- 72 mo: 5.49%
- 84 mo (for >$25k and 2024-2025 vehicles): 5.99%
- New EV discount: -0.10% APR (new untitled EV).

AUTO PURCHASE / REFINANCE (2019-2022)
- 36 mo: 4.49%
- 48 mo: 5.24%
- 60 mo: 5.49%
- 72 mo: 5.70%

UNDERWRITING NOTES
- Rates are "as low as" and score-sensitive (best tiers around Experian 680+).
- Term and approvals depend on year, mileage, and NADA values.
- Auto equity loans require score ~650+ with Experian and equity constraints.

REQUIRED DOCUMENTS / STIPS
- Completed loan application (co-borrower separate app).
- Current payroll stub.
- Signed purchase agreement and delivery date.
- Vehicle details (year, make, model, mileage, VIN).
- Insurance information.
- Refinance: payoff letter and current contract copy.

RISK POLICY
- If profile does not meet term/year/value constraints, decline or counter.
- If borrower quality weaker than top tiers, return higher APR within sheet ranges.
""",
)


LENDER_PROFILES: list[LenderProfile] = [
    PRIME_BANK,
    MID_MARKET,
    SUBPRIME,
    USED_ONLY_CU,
    EV_CAPTIVE,
]


if __name__ == "__main__":
    for p in LENDER_PROFILES:
        sheet_lines = p.rate_sheet_text.count("\n")
        print(
            f"{p.id:14}  {p.name:24}  alias={p.lora_alias:11}  "
            f"sheet={sheet_lines} lines"
        )
