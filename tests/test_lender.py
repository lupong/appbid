"""Tests for the Lender agent.

Underwriter is mocked; the marketplace runs in-process via httpx.ASGITransport
so the X402 middleware is exercised end-to-end. A StubPayer satisfies the
402-then-pay handshake without any chain calls.

There is no policy-engine pre-filter — every bid decision (approve, decline,
counter) is the underwriter's call, mocked here. X402 retries use an
enveloped payment payload (x402Version/scheme/network + payload).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from agents.lender import Lender
from agents.payment import StubPayer
from data.bid_policies import LENDER_PROFILES
from shared.db import close_db, init_db, set_engine
from shared.models import BidRequest, Decision, DecisionType, VehicleType

PRIME, MID, SUBPRIME, USED_CU, EV = LENDER_PROFILES
_TX_HASH_PRIME = "0x" + "c" * 64


def _request(**overrides) -> BidRequest:
    base: dict = dict(
        dealer_id="d",
        applicant_fico=720,
        loan_amount=Decimal("25000"),
        vehicle_type=VehicleType.NEW,
        term_months=60,
        state="TX",
        dealer_reserve_bps=200,
    )
    base.update(overrides)
    return BidRequest(**base)


# ---------- end-to-end with mocked underwriter ----------


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    set_engine(
        create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    )
    await init_db()
    from marketplace.server import app as fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await close_db()


def _approve() -> Decision:
    return Decision(
        decision=DecisionType.APPROVE,
        apr_bps=425,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        max_ltv_bps=10_000,
        cash_down_required_usdc=Decimal("0"),
        dealer_reserve_bps=80,
        stipulations=["proof of insurance"],
        confidence=0.92,
        rationale="strong fico, new vehicle",
    )


def _decline() -> Decision:
    return Decision(
        decision=DecisionType.DECLINE,
        apr_bps=0,
        term_months=60,
        max_amount_usdc=Decimal("0"),
        confidence=0.8,
        rationale="out of policy",
    )


async def _publish_request(client: httpx.AsyncClient, **overrides) -> BidRequest:
    body: dict = {
        "dealer_id": "d",
        "applicant_fico": 720,
        "loan_amount": "25000",
        "vehicle_type": "new",
        "term_months": 60,
        "state": "TX",
        "dealer_reserve_bps": 200,
    }
    body.update(overrides)
    r = await client.post("/apps", json=body)
    assert r.status_code == 201, r.text
    return BidRequest.model_validate(r.json())


async def test_lender_pays_x402_and_submits_bid(http_client: httpx.AsyncClient) -> None:
    req = await _publish_request(http_client)

    uw = AsyncMock()
    uw.evaluate.return_value = _approve()
    payer = StubPayer(payer_id="0xprime_lender", tx_hash=_TX_HASH_PRIME)

    lender = Lender(PRIME, uw, "http://testserver", payer=payer)
    bid_id = await lender.evaluate_and_bid(req, http_client)

    assert bid_id is not None
    uw.evaluate.assert_awaited_once()
    args, kwargs = uw.evaluate.call_args
    assert args[0] is PRIME
    assert args[1].id == req.id
    assert kwargs == {}
    assert len(payer.calls) == 1, "payer should have been invoked once on 402"

    paywall = payer.calls[0]
    assert paywall["x402Version"] == 1
    assert paywall["accepts"][0]["network"] == "base-sepolia"

    bids = (await http_client.get(f"/apps/{req.id}/bids")).json()
    assert len(bids) == 1
    assert bids[0]["lender_id"] == "prime-bank"
    assert bids[0]["apr_bps"] == 425
    assert bids[0]["term_months"] == 60
    assert bids[0]["dealer_reserve_bps"] == 80
    assert bids[0]["stipulations"] == ["proof of insurance"]
    assert bids[0]["insertion_fee_tx_hash"] == _TX_HASH_PRIME


async def test_lender_skips_on_underwriter_decline(http_client: httpx.AsyncClient) -> None:
    """Out-of-box requests come back as decline from the underwriter — not as
    a pre-filter. The lender must skip submission and not pay the X402 fee.
    """
    req = await _publish_request(
        http_client,
        applicant_fico=600,
        loan_amount="15000",
        vehicle_type="used",
        term_months=72,
        dealer_reserve_bps=180,
    )

    uw = AsyncMock()
    uw.evaluate.return_value = _decline()
    payer = StubPayer()

    lender = Lender(SUBPRIME, uw, "http://testserver", payer=payer)
    bid_id = await lender.evaluate_and_bid(req, http_client)

    assert bid_id is None
    assert payer.calls == [], "decline should not trigger payment"
    assert (await http_client.get(f"/apps/{req.id}/bids")).json() == []


async def test_lender_swallows_underwriter_failure(http_client: httpx.AsyncClient) -> None:
    from agents.underwriter import UnderwriterError

    req = await _publish_request(http_client)
    uw = AsyncMock()
    uw.evaluate.side_effect = UnderwriterError("LLM down")

    lender = Lender(PRIME, uw, "http://testserver", payer=StubPayer())
    bid_id = await lender.evaluate_and_bid(req, http_client)

    assert bid_id is None
    assert (await http_client.get(f"/apps/{req.id}/bids")).json() == []


async def test_lender_without_payer_fails_open_on_402(http_client: httpx.AsyncClient) -> None:
    req = await _publish_request(http_client)
    uw = AsyncMock()
    uw.evaluate.return_value = _approve()

    lender = Lender(PRIME, uw, "http://testserver", payer=None)
    bid_id = await lender.evaluate_and_bid(req, http_client)

    assert bid_id is None, "no payer + 402 should fail-open, not crash"
    assert (await http_client.get(f"/apps/{req.id}/bids")).json() == []


async def test_lender_evaluates_every_request_no_prefilter(
    http_client: httpx.AsyncClient,
) -> None:
    """Without a Python pre-filter, even out-of-box bid requests reach the
    underwriter — that's the whole architectural point of removing the
    policy engine. The LLM is responsible for declining what doesn't fit.
    """
    # PRIME's rate sheet covers new + FICO 720+ + 60-72mo. Send a used,
    # short-term, low-FICO request — the lender must still call the
    # underwriter.
    req = await _publish_request(
        http_client,
        applicant_fico=580,
        vehicle_type="used",
        term_months=36,
    )
    uw = AsyncMock()
    uw.evaluate.return_value = _decline()

    lender = Lender(PRIME, uw, "http://testserver", payer=StubPayer())
    bid_id = await lender.evaluate_and_bid(req, http_client)

    assert bid_id is None
    uw.evaluate.assert_awaited_once()  # underwriter saw the request despite mismatch
