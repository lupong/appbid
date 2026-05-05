"""HTTP-level tests for the marketplace.

Uses FastAPI's TestClient against an in-memory SQLite engine wired in via
shared.db.set_engine(). The X402 middleware is the real Step 6 implementation;
tests bypass on-chain verification by sending a synthetic X-PAYMENT header.
The settlement executor is overridden with StubSettlementExecutor so accept
tests don't touch the chain.
"""
from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from marketplace.settler import (
    StubSettlementExecutor,
    compute_splits,
    get_settlement_executor,
)
from shared.db import set_engine

# 0.10 USDC in 6-decimal atomic units
_FEE_ATOMIC = str(int(0.10 * 10**6))
_TX_HASH_OK = "0x" + "a" * 64
_TX_HASH_ALT = "0x" + "b" * 64


def _x_payment_header(tx_hash: str = _TX_HASH_OK) -> dict[str, str]:
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base-sepolia",
        "payload": {
            "tx_hash": tx_hash,
            "from": "0xtest_payer",
            "amount_atomic": _FEE_ATOMIC,
        },
    }
    return {"X-PAYMENT": base64.b64encode(json.dumps(payload).encode()).decode()}


def _make_engine() -> object:
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    set_engine(_make_engine())
    from marketplace.server import app

    stub = StubSettlementExecutor()
    app.dependency_overrides[get_settlement_executor] = lambda: stub

    # Populate wallets.json with stub wallet ids so resolve_payout_wallets succeeds
    import shared.config
    from pathlib import Path

    wf = Path("wallets.json")
    existing = wf.read_text() if wf.exists() else None
    wf.write_text(
        json.dumps(
            {
                "dealer": "wid-dealer-test",
                "marketplace": "wid-marketplace-test",
                "reserve": "wid-reserve-test",
                "lenders": {},
            }
        )
    )

    with TestClient(app) as c:
        c.stub_executor = stub  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()
    if existing is None:
        wf.unlink(missing_ok=True)
    else:
        wf.write_text(existing)


def _publish(client: TestClient, **overrides: object) -> dict:
    body: dict[str, object] = {
        "dealer_id": "dlr-1",
        "applicant_fico": 720,
        "loan_amount": "25000",
        "vehicle_type": "new",
        "term_months": 60,
        "state": "tx",
        "dealer_reserve_bps": 200,
    }
    body.update(overrides)
    r = client.post("/apps", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _post_bid(
    client: TestClient,
    request_id: str,
    lender_id: str,
    apr_bps: int,
    amount_usdc: str,
    tx_hash: str = _TX_HASH_OK,
    *,
    term_months: int = 60,
    dealer_reserve_bps: int = 0,
    stipulations: list[str] | None = None,
    confidence: float = 0.9,
) -> dict:
    r = client.post(
        f"/apps/{request_id}/bids",
        json={
            "lender_id": lender_id,
            "apr_bps": apr_bps,
            "term_months": term_months,
            "max_amount_usdc": amount_usdc,
            "dealer_reserve_bps": dealer_reserve_bps,
            "stipulations": stipulations or [],
            "confidence": confidence,
            "rationale": "test bid",
        },
        headers=_x_payment_header(tx_hash),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------- pure: split math ----------


def test_compute_splits_25k_loan() -> None:
    wp, d, m, r = compute_splits(Decimal("25000"), Decimal("0.015"))
    assert wp == Decimal("375.000000")
    assert d == Decimal("262.500000")
    assert m == Decimal("93.750000")
    assert r == Decimal("18.750000")
    assert d + m + r == wp


def test_compute_splits_rounding_invariant() -> None:
    for loan in [Decimal("12345.67"), Decimal("99999.99"), Decimal("1.05")]:
        wp, d, m, r = compute_splits(loan, Decimal("0.015"))
        assert d + m + r == wp, f"split sum != win_premium for loan={loan}"


# ---------- structural ----------


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_publish_and_fetch_request(client: TestClient) -> None:
    req = _publish(client)
    assert req["state"] == "TX"
    assert req["status"] == "open"
    assert client.get(f"/apps/{req['id']}").json()["id"] == req["id"]
    assert [r["id"] for r in client.get("/apps").json()] == [req["id"]]


def test_get_unknown_request_404(client: TestClient) -> None:
    assert client.get(f"/apps/{uuid.uuid4()}").status_code == 404


def test_bid_to_unknown_request_404(client: TestClient) -> None:
    r = client.post(
        f"/apps/{uuid.uuid4()}/bids",
        json={
            "lender_id": "x",
            "apr_bps": 500,
            "term_months": 60,
            "max_amount_usdc": "10000",
            "rationale": "n/a",
        },
        headers=_x_payment_header(),
    )
    assert r.status_code == 404


# ---------- accept + 3-way rev-split ----------


def test_bid_ranking_and_accept_executes_split(client: TestClient) -> None:
    req = _publish(client)
    request_id = req["id"]

    _post_bid(client, request_id, "prime-bank", 400, "25000")
    _post_bid(client, request_id, "mid-market", 700, "25000")
    _post_bid(client, request_id, "subprime", 1500, "20000")

    bids = client.get(f"/apps/{request_id}/bids").json()
    assert [b["lender_id"] for b in bids] == ["prime-bank", "mid-market", "subprime"]

    winning_id = bids[0]["id"]
    r = client.post(f"/apps/{request_id}/accept", json={"bid_id": winning_id})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["request_status"] == "closed"
    assert body["winning_bid_id"] == winning_id

    settle = body["settlement"]
    assert settle["dealer_payout_tx"].startswith("0xstubsettle00")
    assert settle["marketplace_cut_tx"].startswith("0xstubsettle01")
    assert settle["reserve_tx"].startswith("0xstubsettle02")

    splits = settle["splits"]
    assert Decimal(splits["win_premium_usdc"]) == Decimal("375.000000")
    assert Decimal(splits["dealer_usdc"]) == Decimal("262.500000")
    assert Decimal(splits["marketplace_usdc"]) == Decimal("93.750000")
    assert Decimal(splits["reserve_usdc"]) == Decimal("18.750000")

    bids_after = client.get(f"/apps/{request_id}/bids").json()
    statuses = {b["lender_id"]: b["status"] for b in bids_after}
    assert statuses == {
        "prime-bank": "accepted",
        "mid-market": "lost",
        "subprime": "lost",
    }
    assert client.get(f"/apps/{request_id}").json()["status"] == "closed"


def test_executor_called_with_correct_amounts(client: TestClient) -> None:
    req = _publish(client, loan_amount="40000")
    bid = _post_bid(client, req["id"], "prime-bank", 400, "40000")
    client.post(f"/apps/{req['id']}/accept", json={"bid_id": bid["id"]})

    stub: StubSettlementExecutor = client.stub_executor  # type: ignore[attr-defined]
    assert len(stub.calls) == 1
    source, recipients = stub.calls[0]
    assert source == "wid-marketplace-test"
    addrs = [r[0] for r in recipients]
    amounts = [r[1] for r in recipients]
    # Recipients (dealer, marketplace, reserve)
    assert addrs == ["wid-dealer-test", "wid-marketplace-test", "wid-reserve-test"]
    # 40000 * 0.015 = 600 → 70/25/5
    assert amounts == [Decimal("420.000000"), Decimal("150.000000"), Decimal("30.000000")]


def test_double_accept_is_409(client: TestClient) -> None:
    req = _publish(client)
    bid = _post_bid(client, req["id"], "prime-bank", 400, "25000")
    assert client.post(f"/apps/{req['id']}/accept", json={"bid_id": bid["id"]}).status_code == 200
    assert client.post(f"/apps/{req['id']}/accept", json={"bid_id": bid["id"]}).status_code == 409


def test_bid_after_accept_is_409(client: TestClient) -> None:
    req = _publish(client)
    bid = _post_bid(client, req["id"], "prime-bank", 400, "25000")
    client.post(f"/apps/{req['id']}/accept", json={"bid_id": bid["id"]})
    r = client.post(
        f"/apps/{req['id']}/bids",
        json={
            "lender_id": "late",
            "apr_bps": 500,
            "term_months": 60,
            "max_amount_usdc": "25000",
            "rationale": "too late",
        },
        headers=_x_payment_header(),
    )
    assert r.status_code == 409


def test_filter_by_status(client: TestClient) -> None:
    r1 = _publish(client, dealer_id="dlr-1")
    r2 = _publish(client, dealer_id="dlr-2")
    bid = _post_bid(client, r1["id"], "prime-bank", 400, "25000")
    client.post(f"/apps/{r1['id']}/accept", json={"bid_id": bid["id"]})
    open_requests = client.get("/apps", params={"status": "open"}).json()
    closed = client.get("/apps", params={"status": "closed"}).json()
    assert {x["id"] for x in open_requests} == {r2["id"]}
    assert {x["id"] for x in closed} == {r1["id"]}


# ---------- X402 middleware behavior ----------


def test_bid_without_x_payment_returns_402(client: TestClient) -> None:
    req = _publish(client)
    r = client.post(
        f"/apps/{req['id']}/bids",
        json={
            "lender_id": "no-pay",
            "apr_bps": 500,
            "term_months": 60,
            "max_amount_usdc": "25000",
            "rationale": "tries without paying",
        },
    )
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 1
    assert body["accepts"][0]["network"] == "base-sepolia"
    assert body["accepts"][0]["maxAmountRequired"] == _FEE_ATOMIC
    assert body["accepts"][0]["scheme"] == "exact"
    assert body["accepts"][0]["resource"].endswith("/bids")


def test_bid_with_bad_tx_hash_returns_402(client: TestClient) -> None:
    req = _publish(client)
    bad_payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base-sepolia",
        "payload": {"tx_hash": "not-a-hex", "amount_atomic": _FEE_ATOMIC},
    }
    bad_header = base64.b64encode(json.dumps(bad_payload).encode()).decode()
    r = client.post(
        f"/apps/{req['id']}/bids",
        json={
            "lender_id": "bad",
            "apr_bps": 500,
            "term_months": 60,
            "max_amount_usdc": "25000",
            "rationale": "malformed",
        },
        headers={"X-PAYMENT": bad_header},
    )
    assert r.status_code == 402


def test_bid_with_amount_mismatch_returns_402(client: TestClient) -> None:
    req = _publish(client)
    bad_payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base-sepolia",
        "payload": {"tx_hash": _TX_HASH_ALT, "amount_atomic": "1"},
    }
    bad_header = base64.b64encode(json.dumps(bad_payload).encode()).decode()
    r = client.post(
        f"/apps/{req['id']}/bids",
        json={
            "lender_id": "underpay",
            "apr_bps": 500,
            "term_months": 60,
            "max_amount_usdc": "25000",
            "rationale": "underpaid",
        },
        headers={"X-PAYMENT": bad_header},
    )
    assert r.status_code == 402


def test_bid_records_x402_tx_hash(client: TestClient) -> None:
    req = _publish(client)
    bid = _post_bid(client, req["id"], "prime-bank", 400, "25000", tx_hash=_TX_HASH_ALT)
    assert bid["insertion_fee_tx_hash"] == _TX_HASH_ALT


# ---------- treasury / settlement read endpoints ----------


def test_treasury_empty(client: TestClient) -> None:
    stats = client.get("/treasury").json()
    assert stats["total_bids"] == 0
    assert stats["total_settlements"] == 0
    assert Decimal(stats["insertion_fees_collected_usdc"]) == Decimal("0")
    assert Decimal(stats["win_premium_total_usdc"]) == Decimal("0")


def test_treasury_after_settlement(client: TestClient) -> None:
    req = _publish(client, loan_amount="40000")
    _post_bid(client, req["id"], "prime-bank", 400, "40000")
    _post_bid(client, req["id"], "mid-market", 700, "40000")
    bids = client.get(f"/apps/{req['id']}/bids").json()
    client.post(f"/apps/{req['id']}/accept", json={"bid_id": bids[0]["id"]})

    stats = client.get("/treasury").json()
    assert stats["total_bids"] == 2
    assert stats["total_settlements"] == 1
    # 2 bids * $0.10 = $0.20
    assert Decimal(stats["insertion_fees_collected_usdc"]) == Decimal("0.20")
    # 40000 * 0.015 = 600 win premium; 25% cut = 150
    assert Decimal(stats["win_premium_total_usdc"]) == Decimal("600.000000")
    assert Decimal(stats["marketplace_cut_usdc"]) == Decimal("150.000000")
    assert Decimal(stats["dealer_payouts_usdc"]) == Decimal("420.000000")
    assert Decimal(stats["reserve_payouts_usdc"]) == Decimal("30.000000")


def test_get_settlement_endpoint(client: TestClient) -> None:
    req = _publish(client)
    bid = _post_bid(client, req["id"], "prime-bank", 400, "25000")
    client.post(f"/apps/{req['id']}/accept", json={"bid_id": bid["id"]})

    r = client.get(f"/apps/{req['id']}/settlement")
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["request_id"] == req["id"]
    assert s["winning_bid_id"] == bid["id"]
    assert s["dealer_payout_tx"].startswith("0xstubsettle00")


def test_settlement_endpoint_404_when_unsettled(client: TestClient) -> None:
    req = _publish(client)
    r = client.get(f"/apps/{req['id']}/settlement")
    assert r.status_code == 404
