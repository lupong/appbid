"""Win-premium computation and three-way rev-split executor.

Splits the win premium 70 / 25 / 5 across (dealer, marketplace, reserve).
The executor is dependency-injected so tests can substitute a stub that
returns synthetic tx hashes without touching the chain.

Wallet IDs are read from wallets.json (written by scripts/setup_wallets.py)
with env vars (MARKETPLACE_WALLET_ID, RESERVE_WALLET_ID) as fallback for
the marketplace and reserve.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger("marketplace.settler")

WALLETS_FILE = Path("wallets.json")
_USDC_PRECISION = Decimal("0.000001")

DEALER_PCT = Decimal("0.70")
MARKETPLACE_PCT = Decimal("0.25")
RESERVE_PCT = Decimal("0.05")


def compute_splits(
    loan_amount: Decimal, win_premium_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Returns (win_premium, dealer_share, marketplace_share, reserve_share).

    Marketplace absorbs sub-microcent rounding so the three shares always
    sum exactly to the win premium.
    """
    win_premium = (loan_amount * win_premium_rate).quantize(_USDC_PRECISION)
    dealer = (win_premium * DEALER_PCT).quantize(_USDC_PRECISION)
    reserve = (win_premium * RESERVE_PCT).quantize(_USDC_PRECISION)
    marketplace = (win_premium - dealer - reserve).quantize(_USDC_PRECISION)
    return win_premium, dealer, marketplace, reserve


def _load_wallets_file() -> dict[str, Any]:
    if not WALLETS_FILE.exists():
        return {}
    return json.loads(WALLETS_FILE.read_text())


def resolve_payout_wallets() -> tuple[str, str, str, str]:
    """Returns (source_wallet_id, dealer_wid, marketplace_wid, reserve_wid).

    Source = marketplace wallet (it pays out the rev-split).
    Marketplace cut tx is a self-transfer to demonstrate batched call.
    """
    settings = get_settings()
    wallets = _load_wallets_file()
    marketplace_wid = settings.marketplace_wallet_id or wallets.get("marketplace") or ""
    reserve_wid = settings.reserve_wallet_id or wallets.get("reserve") or ""
    dealer_wid = wallets.get("dealer") or ""
    if not marketplace_wid:
        raise RuntimeError("marketplace wallet not configured")
    if not reserve_wid:
        raise RuntimeError("reserve wallet not configured")
    if not dealer_wid:
        raise RuntimeError(
            "dealer wallet not configured; run scripts/setup_wallets.py to populate wallets.json"
        )
    return marketplace_wid, dealer_wid, marketplace_wid, reserve_wid


class SettlementExecutor(Protocol):
    async def execute(
        self,
        source_wallet_id: str,
        recipients: list[tuple[str, Decimal]],
    ) -> list[str]:
        """Send each (recipient_wallet_id_or_address, amount) and return tx hashes."""
        ...


class CDPSettlementExecutor:
    async def execute(
        self,
        source_wallet_id: str,
        recipients: list[tuple[str, Decimal]],
    ) -> list[str]:
        from shared.wallets import batched_transfer, get_address

        resolved: list[tuple[str, Decimal]] = []
        for wid_or_addr, amount in recipients:
            addr = wid_or_addr if wid_or_addr.startswith("0x") else await get_address(wid_or_addr)
            resolved.append((addr, amount))
        return await batched_transfer(source_wallet_id, resolved)


class StubSettlementExecutor:
    """Tests only — returns deterministic synthetic tx hashes."""

    def __init__(self, prefix: str = "0xstubsettle") -> None:
        self.prefix = prefix
        self.calls: list[tuple[str, list[tuple[str, Decimal]]]] = []

    async def execute(
        self,
        source_wallet_id: str,
        recipients: list[tuple[str, Decimal]],
    ) -> list[str]:
        self.calls.append((source_wallet_id, recipients))
        return [f"{self.prefix}{i:02d}{'a' * 8}" for i in range(len(recipients))]


def get_settlement_executor() -> SettlementExecutor:
    """FastAPI dependency. Override in tests via app.dependency_overrides."""
    return CDPSettlementExecutor()


if __name__ == "__main__":
    # quick check
    cases = [
        (Decimal("25000"), Decimal("0.015")),
        (Decimal("12345.67"), Decimal("0.015")),
        (Decimal("100000"), Decimal("0.020")),
    ]
    for loan, rate in cases:
        wp, d, m, r = compute_splits(loan, rate)
        assert d + m + r == wp, f"split mismatch loan={loan} rate={rate}"
        print(f"loan={loan:>10}  rate={rate}  wp={wp}  dealer={d}  mkt={m}  res={r}")
    print("compute_splits OK")
