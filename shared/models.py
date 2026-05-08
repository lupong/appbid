"""Domain Pydantic models for Credit App+.

Money is represented as Decimal in app code; never float. Values flowing on
chain are converted to USDC base units (6 decimals) at the wallet boundary.

The marketplace shops *bid requests* — PII-free structural proposals
(dealer-pulled FICO, vehicle, term, amount, state, incentive). Lenders return
``Bid`` packages — rate, term, max amount, LTV, cash down, dealer incentive,
and stipulations — and the marketplace ranker scores on what dealers
actually optimize for (rate, incentive economics, stip burden, lender
reputation). Identity verification, fresh credit pulls, and KYC happen
out-of-band at the funding stage with the winning lender, not here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleType(str, Enum):
    NEW = "new"
    USED = "used"
    EV = "ev"


class RequestStatus(str, Enum):
    OPEN = "open"
    FUNDED_PENDING = "funded_pending"
    CLOSED = "closed"


class BidStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    LOST = "lost"


class DecisionType(str, Enum):
    APPROVE = "approve"
    DECLINE = "decline"
    COUNTER = "counter"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BidRequest(BaseModel):
    """A PII-free structural proposal submitted by a dealer for lender bids.

    Carries the dealer-pulled FICO and the deal structure; no name, SSN,
    address, or anything else that would invoke GLBA / FCRA / KYC at the
    marketplace layer. Lenders bid on the structure; the winning lender
    receives the full PII-bearing application out-of-band post-acceptance
    for funding-stage underwriting.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    dealer_id: str
    applicant_fico: int = Field(ge=300, le=850)
    loan_amount: Decimal = Field(gt=0)
    vehicle_type: VehicleType
    term_months: int = Field(ge=12, le=84)
    state: str = Field(min_length=2, max_length=2)
    # Signed dealer incentive in bps: negative = dealer discount, positive = fee.
    dealer_reserve_bps: int = Field(ge=-500, le=500)
    created_at: datetime = Field(default_factory=_utcnow)
    status: RequestStatus = RequestStatus.OPEN

    @field_validator("state")
    @classmethod
    def _upper_state(cls, v: str) -> str:
        return v.upper()


class Bid(BaseModel):
    """A lender's full pricing package responding to a BidRequest.

    Fields beyond `apr_bps` are what differentiate one lender's bid from
    another's — same applicant, different rates, terms, stips, LTVs, and
    dealer reserves. The marketplace ranker scores on this whole package,
    not just rate. Bids are conditional: stipulations are how the lender
    prices the uncertainty about the full PII-bearing application that will
    arrive at funding.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    lender_id: str
    lender_name: str | None = None

    # Pricing package
    decision: DecisionType = DecisionType.APPROVE
    apr_bps: int = Field(ge=0, le=10_000, description="APR in basis points (549 = 5.49%)")
    term_months: int = Field(ge=12, le=120)
    max_amount_usdc: Decimal = Field(gt=0, description="Max amount the lender will fund")
    max_ltv_bps: int = Field(ge=0, le=20_000, default=10_000, description="Max LTV in bps")
    cash_down_required_usdc: Decimal = Field(ge=0, default=Decimal("0"))
    # Signed dealer incentive in bps: negative = dealer discount, positive = fee.
    dealer_reserve_bps: int = Field(ge=-500, le=500, default=0)
    stipulations: list[str] = Field(default_factory=list)

    # Meta
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
    rationale: str
    insertion_fee_tx_hash: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    status: BidStatus = BidStatus.OPEN


class Settlement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    winning_bid_id: UUID
    dealer_payout_tx: str
    marketplace_cut_tx: str
    reserve_tx: str
    created_at: datetime = Field(default_factory=_utcnow)


class LenderProfile(BaseModel):
    """Configuration for a single lender agent.

    A lender is described by exactly one piece of policy: its
    ``rate_sheet_text``. Free-form text — paste the lender's published rate
    sheet (FICO bands, term tiers, LTV ladder, exclusions, dealer reserve,
    stipulation rules, anything else) verbatim. This text serves two roles:

      * It seeds LoRA training. ``lora_training/synthetic_data.py`` runs a
        teacher LLM with this rate sheet inlined to label synthetic bid
        requests; the LoRA learns to imitate the teacher's decisions.
        After training, the rate sheet is "in the weights" and the LoRA
        receives just the bid request at inference time.
      * It is the fallback prompt. With ``LORA_MODE=prompt`` (no LoRA), the
        underwriter sends ``rate_sheet_text`` to the base model as a system
        prompt — the same text, just used at inference instead of training.

    There is no policy engine, no subscription filter, no pricing strategy
    knobs. Every bid decision is made by the LoRA-fine-tuned underwriter.
    """

    id: str
    name: str
    wallet_id: str | None = None
    rate_sheet_text: str
    lora_alias: str


class Decision(BaseModel):
    """Strict-JSON output of the underwriter LLM — a pricing decision for one
    bid request. The Lender turns this into a Bid by attaching meta
    (insertion-fee tx hash, etc.).
    """

    decision: DecisionType
    apr_bps: int = Field(ge=0, le=10_000)
    term_months: int = Field(ge=12, le=120)
    max_amount_usdc: Decimal = Field(ge=0)
    max_ltv_bps: int = Field(ge=0, le=20_000, default=10_000)
    cash_down_required_usdc: Decimal = Field(ge=0, default=Decimal("0"))
    dealer_reserve_bps: int = Field(ge=-500, le=500, default=0)
    stipulations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


# ----- HTTP request bodies (id / created_at / status set server-side) -----


class BidRequestCreate(BaseModel):
    dealer_id: str
    applicant_fico: int = Field(ge=300, le=850)
    loan_amount: Decimal = Field(gt=0)
    vehicle_type: VehicleType
    term_months: int = Field(ge=12, le=84)
    state: str = Field(min_length=2, max_length=2)
    dealer_reserve_bps: int = Field(ge=-500, le=500)

    @field_validator("state")
    @classmethod
    def _upper_state(cls, v: str) -> str:
        return v.upper()


class BidCreate(BaseModel):
    """Submitted by lenders to POST /apps/{request_id}/bids — the full pricing package."""

    lender_id: str
    decision: DecisionType = DecisionType.APPROVE
    apr_bps: int = Field(ge=0, le=10_000)
    term_months: int = Field(ge=12, le=120)
    max_amount_usdc: Decimal = Field(gt=0)
    max_ltv_bps: int = Field(ge=0, le=20_000, default=10_000)
    cash_down_required_usdc: Decimal = Field(ge=0, default=Decimal("0"))
    dealer_reserve_bps: int = Field(ge=-500, le=500, default=0)
    stipulations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
    rationale: str
    insertion_fee_tx_hash: str | None = None
