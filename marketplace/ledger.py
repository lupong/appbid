"""Async ledger persistence — the only path between Pydantic models and SQL.

Every public function uses session_scope() to manage its own transaction.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from shared.db import BidRequestRow, BidRow, SettlementRow, session_scope
from shared.models import (
    Bid,
    BidRequest,
    BidStatus,
    RequestStatus,
    Settlement,
)


# ----- bid requests -----


async def save_request(req: BidRequest) -> BidRequest:
    async with session_scope() as session:
        row = BidRequestRow(
            id=str(req.id),
            dealer_id=req.dealer_id,
            applicant_fico=req.applicant_fico,
            loan_amount=req.loan_amount,
            vehicle_type=req.vehicle_type,
            term_months=req.term_months,
            state=req.state,
            dealer_reserve_bps=req.dealer_reserve_bps,
            created_at=req.created_at,
            status=req.status,
        )
        session.add(row)
    return req


async def get_request(request_id: UUID) -> BidRequest | None:
    async with session_scope() as session:
        row = await session.get(BidRequestRow, str(request_id))
        if row is None:
            return None
        return BidRequest.model_validate(row)


async def list_requests(status: RequestStatus | None = None) -> list[BidRequest]:
    async with session_scope() as session:
        stmt = select(BidRequestRow).order_by(BidRequestRow.created_at.desc())
        if status is not None:
            stmt = stmt.where(BidRequestRow.status == status)
        result = await session.execute(stmt)
        return [BidRequest.model_validate(r) for r in result.scalars().all()]


async def update_request_status(request_id: UUID, status: RequestStatus) -> None:
    async with session_scope() as session:
        row = await session.get(BidRequestRow, str(request_id))
        if row is None:
            raise ValueError(f"bid request {request_id} not found")
        row.status = status


# ----- bids -----


async def save_bid(bid: Bid) -> Bid:
    async with session_scope() as session:
        row = BidRow(
            id=str(bid.id),
            request_id=str(bid.request_id),
            lender_id=bid.lender_id,
            decision=bid.decision,
            apr_bps=bid.apr_bps,
            term_months=bid.term_months,
            max_amount_usdc=bid.max_amount_usdc,
            max_ltv_bps=bid.max_ltv_bps,
            cash_down_required_usdc=bid.cash_down_required_usdc,
            dealer_reserve_bps=bid.dealer_reserve_bps,
            stipulations=list(bid.stipulations),
            confidence=bid.confidence,
            rationale=bid.rationale,
            insertion_fee_tx_hash=bid.insertion_fee_tx_hash,
            created_at=bid.created_at,
            status=bid.status,
        )
        session.add(row)
    return bid


async def get_bid(bid_id: UUID) -> Bid | None:
    async with session_scope() as session:
        row = await session.get(BidRow, str(bid_id))
        if row is None:
            return None
        return Bid.model_validate(row)


async def list_bids_for_request(request_id: UUID) -> list[Bid]:
    async with session_scope() as session:
        stmt = (
            select(BidRow)
            .where(BidRow.request_id == str(request_id))
            .order_by(BidRow.created_at.asc())
        )
        result = await session.execute(stmt)
        return [Bid.model_validate(r) for r in result.scalars().all()]


async def update_bid_status(bid_id: UUID, status: BidStatus) -> None:
    async with session_scope() as session:
        row = await session.get(BidRow, str(bid_id))
        if row is None:
            raise ValueError(f"bid {bid_id} not found")
        row.status = status


# ----- settlements -----


async def save_settlement(settlement: Settlement) -> Settlement:
    async with session_scope() as session:
        row = SettlementRow(
            id=str(settlement.id),
            request_id=str(settlement.request_id),
            winning_bid_id=str(settlement.winning_bid_id),
            dealer_payout_tx=settlement.dealer_payout_tx,
            marketplace_cut_tx=settlement.marketplace_cut_tx,
            reserve_tx=settlement.reserve_tx,
            created_at=settlement.created_at,
        )
        session.add(row)
    return settlement


async def get_settlement_for_request(request_id: UUID) -> Settlement | None:
    async with session_scope() as session:
        stmt = select(SettlementRow).where(SettlementRow.request_id == str(request_id))
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Settlement.model_validate(row)
