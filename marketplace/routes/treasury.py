"""Treasury aggregates — what the marketplace has earned and paid out."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from shared.config import get_settings
from shared.db import BidRequestRow, BidRow, SettlementRow, session_scope

router = APIRouter(prefix="/treasury", tags=["treasury"])


class TreasuryStats(BaseModel):
    total_bids: int
    total_settlements: int
    insertion_fees_collected_usdc: Decimal
    win_premium_total_usdc: Decimal
    marketplace_cut_usdc: Decimal
    dealer_payouts_usdc: Decimal
    reserve_payouts_usdc: Decimal
    marketplace_wallet_id: str


@router.get("", response_model=TreasuryStats)
async def get_treasury_stats() -> TreasuryStats:
    settings = get_settings()
    rate = settings.win_premium_rate

    async with session_scope() as session:
        bid_count = (await session.execute(select(func.count(BidRow.id)))).scalar_one() or 0
        settlement_count = (
            await session.execute(select(func.count(SettlementRow.id)))
        ).scalar_one() or 0

        loan_sum_stmt = (
            select(func.coalesce(func.sum(BidRequestRow.loan_amount), 0))
            .join(SettlementRow, SettlementRow.request_id == BidRequestRow.id)
        )
        settled_loan_sum = Decimal(
            str((await session.execute(loan_sum_stmt)).scalar_one())
        )

    insertion_fees = Decimal(bid_count) * settings.insertion_fee_usdc
    win_premium_total = (settled_loan_sum * rate).quantize(Decimal("0.000001"))
    dealer_payouts = (win_premium_total * Decimal("0.70")).quantize(Decimal("0.000001"))
    reserve_payouts = (win_premium_total * Decimal("0.05")).quantize(Decimal("0.000001"))
    marketplace_cut = (win_premium_total - dealer_payouts - reserve_payouts).quantize(
        Decimal("0.000001")
    )

    return TreasuryStats(
        total_bids=int(bid_count),
        total_settlements=int(settlement_count),
        insertion_fees_collected_usdc=insertion_fees,
        win_premium_total_usdc=win_premium_total,
        marketplace_cut_usdc=marketplace_cut,
        dealer_payouts_usdc=dealer_payouts,
        reserve_payouts_usdc=reserve_payouts,
        marketplace_wallet_id=settings.marketplace_wallet_id or "",
    )
