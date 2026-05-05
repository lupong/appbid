"""Routes for bid submission / listing.

POST is gated by marketplace.x402_middleware: a valid X-PAYMENT lands on
request.state.x402_tx_hash, which is recorded on the persisted Bid.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from marketplace import ledger
from marketplace.ranker import rank_bids
from shared.models import Bid, BidCreate, RequestStatus

router = APIRouter(prefix="/apps/{request_id}/bids", tags=["bids"])


@router.post("", response_model=Bid, status_code=201)
async def create_bid(request_id: UUID, body: BidCreate, request: Request) -> Bid:
    req = await ledger.get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="bid request not found")
    if req.status != RequestStatus.OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"request status is {req.status.value}; cannot accept bids",
        )

    tx_hash = getattr(request.state, "x402_tx_hash", None) or body.insertion_fee_tx_hash
    bid = Bid(
        request_id=request_id,
        lender_id=body.lender_id,
        decision=body.decision,
        apr_bps=body.apr_bps,
        term_months=body.term_months,
        max_amount_usdc=body.max_amount_usdc,
        max_ltv_bps=body.max_ltv_bps,
        cash_down_required_usdc=body.cash_down_required_usdc,
        dealer_reserve_bps=body.dealer_reserve_bps,
        stipulations=body.stipulations,
        confidence=body.confidence,
        rationale=body.rationale,
        insertion_fee_tx_hash=tx_hash,
    )
    return await ledger.save_bid(bid)


@router.get("", response_model=list[Bid])
async def list_bids(request_id: UUID) -> list[Bid]:
    req = await ledger.get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="bid request not found")
    bids = await ledger.list_bids_for_request(request_id)
    ranked = rank_bids(bids, req)
    return [b for b, _score in ranked]
