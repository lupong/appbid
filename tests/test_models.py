"""Pydantic round-trips and validation for shared.models."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from shared.models import (
    Bid,
    BidCreate,
    BidRequest,
    BidRequestCreate,
    BidStatus,
    Decision,
    DecisionType,
    LenderProfile,
    RequestStatus,
    Settlement,
    VehicleType,
)


# ---------- BidRequest ----------


def test_bid_request_minimal_construction() -> None:
    req = BidRequest(
        dealer_id="dlr-1",
        applicant_fico=720,
        loan_amount=Decimal("25000"),
        vehicle_type=VehicleType.NEW,
        term_months=60,
        state="TX",
        dealer_reserve_bps=200,
    )
    assert isinstance(req.id, UUID)
    assert req.status == RequestStatus.OPEN
    assert req.created_at.tzinfo is timezone.utc
    assert req.state == "TX"


def test_bid_request_state_validator_uppercases() -> None:
    req = BidRequest(
        dealer_id="d",
        applicant_fico=720,
        loan_amount=Decimal("25000"),
        vehicle_type=VehicleType.NEW,
        term_months=60,
        state="tx",
        dealer_reserve_bps=200,
    )
    assert req.state == "TX"


def test_bid_request_json_roundtrip() -> None:
    a = BidRequest(
        dealer_id="d",
        applicant_fico=720,
        loan_amount=Decimal("25000.50"),
        vehicle_type=VehicleType.EV,
        term_months=60,
        state="CA",
        dealer_reserve_bps=180,
    )
    js = a.model_dump_json()
    b = BidRequest.model_validate_json(js)
    assert b.id == a.id
    assert b.loan_amount == Decimal("25000.50")
    assert b.vehicle_type == VehicleType.EV
    assert b.created_at == a.created_at


@pytest.mark.parametrize(
    "field,value",
    [
        ("applicant_fico", 200),  # below 300
        ("applicant_fico", 900),  # above 850
        ("term_months", 6),  # below 12
        ("term_months", 100),  # above 84
        ("dealer_reserve_bps", -1),
        ("dealer_reserve_bps", 600),
        ("loan_amount", Decimal("0")),
        ("loan_amount", Decimal("-1")),
        ("state", "T"),  # too short
        ("state", "TXX"),  # too long
    ],
)
def test_bid_request_validation_rejects(field: str, value: object) -> None:
    base: dict = dict(
        dealer_id="d",
        applicant_fico=720,
        loan_amount=Decimal("25000"),
        vehicle_type=VehicleType.NEW,
        term_months=60,
        state="TX",
        dealer_reserve_bps=200,
    )
    base[field] = value
    with pytest.raises(ValidationError):
        BidRequest(**base)


# ---------- Bid ----------


def test_bid_construction_and_roundtrip() -> None:
    bid = Bid(
        request_id=uuid4(),
        lender_id="prime-bank",
        apr_bps=425,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        rationale="strong",
    )
    assert bid.status == BidStatus.OPEN
    assert bid.insertion_fee_tx_hash is None
    assert bid.decision == DecisionType.APPROVE
    assert bid.stipulations == []
    assert bid.dealer_reserve_bps == 0
    assert bid.cash_down_required_usdc == Decimal("0")
    assert bid.max_ltv_bps == 10_000

    js = bid.model_dump_json()
    bid2 = Bid.model_validate_json(js)
    assert bid2.id == bid.id
    assert bid2.request_id == bid.request_id
    assert bid2.apr_bps == 425
    assert bid2.term_months == 60
    assert bid2.max_amount_usdc == Decimal("25000")


def test_bid_full_pricing_package_roundtrip() -> None:
    bid = Bid(
        request_id=uuid4(),
        lender_id="subprime",
        decision=DecisionType.APPROVE,
        apr_bps=1500,
        term_months=72,
        max_amount_usdc=Decimal("18000"),
        max_ltv_bps=11500,
        cash_down_required_usdc=Decimal("2000"),
        dealer_reserve_bps=200,
        stipulations=["paystub_30d", "gps_tracker"],
        confidence=0.82,
        rationale="subprime tier with required stips",
    )
    js = bid.model_dump_json()
    bid2 = Bid.model_validate_json(js)
    assert bid2.dealer_reserve_bps == 200
    assert bid2.stipulations == ["paystub_30d", "gps_tracker"]
    assert bid2.cash_down_required_usdc == Decimal("2000")
    assert bid2.max_ltv_bps == 11500


@pytest.mark.parametrize(
    "field,value",
    [
        ("apr_bps", -1),
        ("apr_bps", 10_001),
        ("max_amount_usdc", Decimal("0")),
        ("max_amount_usdc", Decimal("-1")),
        ("term_months", 6),
        ("dealer_reserve_bps", 600),
        ("confidence", -0.1),
    ],
)
def test_bid_validation_rejects(field: str, value: object) -> None:
    base: dict = dict(
        request_id=uuid4(),
        lender_id="x",
        apr_bps=500,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        rationale="r",
    )
    base[field] = value
    with pytest.raises(ValidationError):
        Bid(**base)


# ---------- Settlement ----------


def test_settlement_roundtrip() -> None:
    s = Settlement(
        request_id=uuid4(),
        winning_bid_id=uuid4(),
        dealer_payout_tx="0xdeadbeef01",
        marketplace_cut_tx="0xdeadbeef02",
        reserve_tx="0xdeadbeef03",
    )
    js = s.model_dump_json()
    s2 = Settlement.model_validate_json(js)
    assert s2.id == s.id
    assert s2.dealer_payout_tx == "0xdeadbeef01"
    assert s2.created_at == s.created_at


# ---------- LenderProfile ----------


def test_lender_profile_minimal_construction() -> None:
    lp = LenderProfile(
        id="prime",
        name="Prime",
        wallet_id="wallet-abc",
        rate_sheet_text="FICO 720+ new only at 4.25% APR.",
        lora_alias="prime",
    )
    assert lp.id == "prime"
    assert lp.wallet_id == "wallet-abc"
    assert lp.lora_alias == "prime"
    assert "4.25%" in lp.rate_sheet_text


def test_lender_profile_default_wallet_none() -> None:
    lp = LenderProfile(
        id="x",
        name="X",
        rate_sheet_text="all FICO welcome",
        lora_alias="x",
    )
    assert lp.wallet_id is None


def test_lender_profile_json_roundtrip() -> None:
    lp = LenderProfile(
        id="prime",
        name="Prime Bank",
        wallet_id="wallet-abc",
        rate_sheet_text="multi\nline\nrate sheet\nwith special chars: $40,000 @ 5.49%",
        lora_alias="prime_bank",
    )
    js = lp.model_dump_json()
    lp2 = LenderProfile.model_validate_json(js)
    assert lp2.rate_sheet_text == lp.rate_sheet_text
    assert lp2.lora_alias == "prime_bank"
    assert lp2.wallet_id == "wallet-abc"


def test_lender_profile_rejects_missing_rate_sheet() -> None:
    with pytest.raises(ValidationError):
        LenderProfile(id="x", name="X", lora_alias="x")  # type: ignore[call-arg]


# ---------- Decision ----------


def test_decision_roundtrip() -> None:
    d = Decision(
        decision=DecisionType.APPROVE,
        apr_bps=425,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        confidence=0.92,
        rationale="strong fico",
    )
    js = d.model_dump_json()
    d2 = Decision.model_validate_json(js)
    assert d2.decision == DecisionType.APPROVE
    assert d2.confidence == 0.92
    assert d2.term_months == 60


def test_decision_parses_llm_string() -> None:
    raw = (
        '{"decision": "approve", "apr_bps": 425, "term_months": 60, '
        '"max_amount_usdc": 25000, "confidence": 0.92, '
        '"rationale": "strong fico"}'
    )
    d = Decision.model_validate_json(raw)
    assert d.decision == DecisionType.APPROVE
    assert d.max_ltv_bps == 10_000  # default


def test_decision_decline_with_zero_offers() -> None:
    raw = (
        '{"decision": "decline", "apr_bps": 0, "term_months": 60, '
        '"max_amount_usdc": 0, "confidence": 0.9, "rationale": "out of policy"}'
    )
    d = Decision.model_validate_json(raw)
    assert d.decision == DecisionType.DECLINE


def test_decision_full_pricing_package() -> None:
    raw = json.dumps(
        {
            "decision": "approve",
            "apr_bps": 549,
            "term_months": 72,
            "max_amount_usdc": 30000,
            "max_ltv_bps": 11500,
            "cash_down_required_usdc": 1500,
            "dealer_reserve_bps": 200,
            "stipulations": ["proof of insurance"],
            "confidence": 0.91,
            "rationale": "near-prime, comfortable LTV",
        }
    )
    d = Decision.model_validate_json(raw)
    assert d.dealer_reserve_bps == 200
    assert d.stipulations == ["proof of insurance"]
    assert d.cash_down_required_usdc == Decimal("1500")


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "maybe"),
        ("apr_bps", -1),
        ("apr_bps", 10_001),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("term_months", 6),
        ("dealer_reserve_bps", 600),
    ],
)
def test_decision_validation_rejects(field: str, value: object) -> None:
    base: dict = dict(
        decision=DecisionType.APPROVE,
        apr_bps=400,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        confidence=0.5,
        rationale="r",
    )
    base[field] = value
    with pytest.raises(ValidationError):
        Decision(**base)


# ---------- HTTP request bodies ----------


def test_bid_request_create_state_uppercases() -> None:
    body = BidRequestCreate(
        dealer_id="d",
        applicant_fico=700,
        loan_amount=Decimal("20000"),
        vehicle_type=VehicleType.USED,
        term_months=72,
        state="ca",
        dealer_reserve_bps=150,
    )
    assert body.state == "CA"


def test_bid_request_create_to_full_request() -> None:
    body = BidRequestCreate(
        dealer_id="d",
        applicant_fico=700,
        loan_amount=Decimal("20000"),
        vehicle_type=VehicleType.USED,
        term_months=72,
        state="ca",
        dealer_reserve_bps=150,
    )
    full = BidRequest(**body.model_dump())
    assert full.status == RequestStatus.OPEN
    assert isinstance(full.id, UUID)
    assert isinstance(full.created_at, datetime)


def test_bid_create_minimal() -> None:
    body = BidCreate(
        lender_id="x",
        apr_bps=500,
        term_months=60,
        max_amount_usdc=Decimal("10000"),
        rationale="ok",
    )
    assert body.insertion_fee_tx_hash is None
    assert body.decision == DecisionType.APPROVE
    assert body.stipulations == []
    assert body.dealer_reserve_bps == 0


def test_bid_create_validation() -> None:
    with pytest.raises(ValidationError):
        BidCreate(
            lender_id="x",
            apr_bps=20_000,  # > 10000
            term_months=60,
            max_amount_usdc=Decimal("10000"),
            rationale="ok",
        )
