"""Settlement route — accept a winning bid and execute the 3-way rev-split."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from marketplace import ledger
from marketplace.settler import (
    SettlementExecutor,
    compute_splits,
    get_settlement_executor,
    resolve_payout_wallets,
)
from shared.config import get_settings
from shared.logging import get_logger
from shared.models import BidStatus, RequestStatus, Settlement

logger = get_logger("marketplace.settle")

router = APIRouter(prefix="/apps/{request_id}", tags=["settle"])


class AcceptBody(BaseModel):
    bid_id: UUID


class SplitDetail(BaseModel):
    win_premium_usdc: Decimal
    dealer_usdc: Decimal
    marketplace_usdc: Decimal
    reserve_usdc: Decimal


class SettlementResponse(BaseModel):
    id: UUID
    dealer_payout_tx: str
    marketplace_cut_tx: str
    reserve_tx: str
    splits: SplitDetail


class AcceptResponse(BaseModel):
    request_id: UUID
    winning_bid_id: UUID
    request_status: RequestStatus
    settlement: SettlementResponse


@router.post("/accept", response_model=AcceptResponse)
async def accept_bid(
    request_id: UUID,
    body: AcceptBody,
    executor: SettlementExecutor = Depends(get_settlement_executor),
) -> AcceptResponse:
    req = await ledger.get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="bid request not found")
    if req.status != RequestStatus.OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"request status is {req.status.value}; cannot accept",
        )
    bid = await ledger.get_bid(body.bid_id)
    if bid is None or bid.request_id != request_id:
        raise HTTPException(status_code=404, detail="bid not found for this request")
    if bid.status != BidStatus.OPEN:
        raise HTTPException(
            status_code=409, detail=f"bid status is {bid.status.value}; cannot accept"
        )

    settings = get_settings()
    win_premium, dealer_share, marketplace_share, reserve_share = compute_splits(
        req.loan_amount, settings.win_premium_rate
    )

    try:
        source_wid, dealer_wid, marketplace_wid, reserve_wid = resolve_payout_wallets()
    except RuntimeError as e:
        logger.error("settle aborted request=%s err=%s", request_id, e)
        raise HTTPException(status_code=503, detail=str(e)) from e

    logger.info(
        "settling request=%s bid=%s win_premium=%s splits=%s/%s/%s",
        request_id, bid.id, win_premium, dealer_share, marketplace_share, reserve_share,
    )

    try:
        txs = await executor.execute(
            source_wid,
            [
                (dealer_wid, dealer_share),
                (marketplace_wid, marketplace_share),
                (reserve_wid, reserve_share),
            ],
        )
    except Exception as e:
        logger.exception("settlement transfer failed request=%s", request_id)
        raise HTTPException(status_code=502, detail=f"settlement transfer failed: {e}") from e

    if len(txs) != 3:
        raise HTTPException(
            status_code=502, detail=f"expected 3 tx hashes, got {len(txs)}"
        )
    dealer_tx, marketplace_tx, reserve_tx = txs

    settlement = Settlement(
        request_id=request_id,
        winning_bid_id=bid.id,
        dealer_payout_tx=dealer_tx,
        marketplace_cut_tx=marketplace_tx,
        reserve_tx=reserve_tx,
    )
    await ledger.save_settlement(settlement)

    await ledger.update_bid_status(bid.id, BidStatus.ACCEPTED)
    for other in await ledger.list_bids_for_request(request_id):
        if other.id != bid.id and other.status == BidStatus.OPEN:
            await ledger.update_bid_status(other.id, BidStatus.LOST)
    await ledger.update_request_status(request_id, RequestStatus.CLOSED)

    return AcceptResponse(
        request_id=request_id,
        winning_bid_id=bid.id,
        request_status=RequestStatus.CLOSED,
        settlement=SettlementResponse(
            id=settlement.id,
            dealer_payout_tx=dealer_tx,
            marketplace_cut_tx=marketplace_tx,
            reserve_tx=reserve_tx,
            splits=SplitDetail(
                win_premium_usdc=win_premium,
                dealer_usdc=dealer_share,
                marketplace_usdc=marketplace_share,
                reserve_usdc=reserve_share,
            ),
        ),
    )


@router.get("/settlement", response_model=Settlement)
async def get_settlement(request_id: UUID) -> Settlement:
    settlement = await ledger.get_settlement_for_request(request_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="no settlement for this request")
    return settlement
