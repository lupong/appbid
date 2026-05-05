"""Async SQLAlchemy engine, ORM tables, and session factory for the ledger."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.config import get_settings
from shared.models import BidStatus, DecisionType, RequestStatus, VehicleType


class Base(DeclarativeBase):
    pass


class BidRequestRow(Base):
    __tablename__ = "bid_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dealer_id: Mapped[str] = mapped_column(String, nullable=False)
    applicant_fico: Mapped[int] = mapped_column(Integer, nullable=False)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    vehicle_type: Mapped[VehicleType] = mapped_column(SQLEnum(VehicleType), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    dealer_reserve_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        SQLEnum(RequestStatus), nullable=False, default=RequestStatus.OPEN
    )


class BidRow(Base):
    __tablename__ = "bids"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_requests.id"), nullable=False, index=True
    )
    lender_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decision: Mapped[DecisionType] = mapped_column(
        SQLEnum(DecisionType), nullable=False, default=DecisionType.APPROVE
    )
    apr_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    max_amount_usdc: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    max_ltv_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    cash_down_required_usdc: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    dealer_reserve_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stipulations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.9)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    insertion_fee_tx_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BidStatus] = mapped_column(
        SQLEnum(BidStatus), nullable=False, default=BidStatus.OPEN
    )


class SettlementRow(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_requests.id"), nullable=False, index=True
    )
    winning_bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id"), nullable=False
    )
    dealer_payout_tx: Mapped[str] = mapped_column(String, nullable=False)
    marketplace_cut_tx: Mapped[str] = mapped_column(String, nullable=False)
    reserve_tx: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
    return _engine


def set_engine(engine: AsyncEngine) -> None:
    """Override the engine. Used by tests to inject an in-memory SQLite."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session that auto-commits on success, rolls back on exception."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables. Idempotent."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine. Call on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
