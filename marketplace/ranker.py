"""Composite bid scoring for what dealers actually optimize for.

A real dealer doesn't just pick the lowest APR. They balance:
  * the rate the customer will sign at,
  * the dealer incentive economics (discount vs fee),
  * the stipulation burden (each stip is cycle-time + risk of fallout),
  * the lender's confidence in the bid, and
  * the lender's funding-speed reputation.

Lower score wins. The default reputation is 1.0 (perfect); set lower for
lenders that have a track record of slow funding or post-fund chargebacks.
"""
from __future__ import annotations

from shared.models import Bid, BidRequest

_REPUTATION: dict[str, float] = {}


def get_reputation(lender_id: str) -> float:
    return _REPUTATION.get(lender_id, 1.0)


def set_reputation(lender_id: str, value: float) -> None:
    _REPUTATION[lender_id] = max(0.0, min(1.0, value))


def score_bid(bid: Bid, lender_reputation: float | None = None) -> float:
    """Lower score is better. Components are roughly bps-equivalent."""
    rep = get_reputation(bid.lender_id) if lender_reputation is None else lender_reputation
    rate_pen = bid.apr_bps
    cash_down_pen = float(bid.cash_down_required_usdc) * 0.001
    stips_pen = len(bid.stipulations) * 50
    incentive_adjustment = -bid.dealer_reserve_bps * 0.5  # positive fee helps dealer economics
    confidence_factor = (1.0 - bid.confidence) * 100
    reputation_factor = (1.0 - rep) * 200
    return (
        rate_pen
        + cash_down_pen
        + stips_pen
        + incentive_adjustment
        + confidence_factor
        + reputation_factor
    )


def rank_bids(
    bids: list[Bid], _request: BidRequest | None = None
) -> list[tuple[Bid, float]]:
    """Sort bids by composite score, ascending (lower is better).

    ``_request`` is accepted for backward-compatible call sites; the new
    score formula doesn't need it. Ties broken by ``created_at`` ascending
    so earliest bid wins on a tie.
    """
    scored = [(b, score_bid(b)) for b in bids]
    scored.sort(key=lambda x: (x[1], x[0].created_at))
    return scored


if __name__ == "__main__":
    from datetime import datetime, timezone
    from decimal import Decimal

    from shared.models import VehicleType

    req = BidRequest(
        dealer_id="dlr-1",
        applicant_fico=720,
        loan_amount=Decimal("25000"),
        vehicle_type=VehicleType.NEW,
        term_months=60,
        state="TX",
        dealer_reserve_bps=200,
    )
    low_apr = Bid(
        request_id=req.id,
        lender_id="prime-bank",
        apr_bps=400,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        rationale="strong",
        created_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    high_apr = Bid(
        request_id=req.id,
        lender_id="subprime",
        apr_bps=1500,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        rationale="ok",
        created_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    big_reserve = Bid(
        request_id=req.id,
        lender_id="mid-market",
        apr_bps=600,
        term_months=60,
        max_amount_usdc=Decimal("25000"),
        dealer_reserve_bps=250,
        rationale="generous reserve",
        created_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    ranked = rank_bids([high_apr, big_reserve, low_apr], req)
    for b, s in ranked:
        print(
            f"{b.lender_id:14}  apr={b.apr_bps:5}bps  "
            f"reserve={b.dealer_reserve_bps:3}bps  score={s:.2f}"
        )
    print("ranker OK")
