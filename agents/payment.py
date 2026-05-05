"""X402 payment providers for the lender agent.

CDPPayer settles a real USDC transfer on Base Sepolia from the lender's CDP
wallet. StubPayer returns a synthetic tx_hash without touching the chain —
used by tests so the X402 middleware sees a "valid" payment header without
real on-chain spend.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from shared.logging import get_logger
from shared.wallets import get_address, transfer_usdc

logger = get_logger("agents.payment")


class PaymentProvider(Protocol):
    async def pay(self, paywall: dict[str, Any]) -> dict[str, Any]:
        """Pay per the X402 paywall body. Returns an X402 payment envelope."""
        ...


class CDPPayer:
    """Real CDP-wallet payer. Used in production."""

    def __init__(self, wallet_id: str) -> None:
        if not wallet_id:
            raise ValueError("CDPPayer requires a non-empty wallet_id")
        self.wallet_id = wallet_id

    async def pay(self, paywall: dict[str, Any]) -> dict[str, Any]:
        accepts = paywall.get("accepts") or []
        if not accepts:
            raise ValueError("paywall missing 'accepts'")
        accept = accepts[0]
        amount_atomic = int(accept["maxAmountRequired"])
        amount_usdc = Decimal(amount_atomic) / Decimal(10**6)
        pay_to = accept["payTo"]
        if not pay_to.startswith("0x"):
            pay_to = await get_address(pay_to)
        tx_hash = await transfer_usdc(self.wallet_id, pay_to, amount_usdc)
        from_address = await get_address(self.wallet_id)
        logger.info(
            "x402 paid wallet=%s amount=%s pay_to=%s tx=%s",
            self.wallet_id, amount_usdc, pay_to, tx_hash,
        )
        return {
            "x402Version": 1,
            "scheme": accept["scheme"],
            "network": accept["network"],
            "payload": {
                "tx_hash": tx_hash,
                "from": from_address,
                "amount_atomic": str(amount_atomic),
            },
        }


class StubPayer:
    """Returns a synthetic X-PAYMENT payload. Tests only."""

    def __init__(self, payer_id: str = "0xtest_payer", tx_hash: str = "0x" + "a" * 64) -> None:
        self.payer_id = payer_id
        self.tx_hash = tx_hash
        self.calls: list[dict[str, Any]] = []

    async def pay(self, paywall: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(paywall)
        accept = paywall["accepts"][0]
        return {
            "x402Version": 1,
            "scheme": accept["scheme"],
            "network": accept["network"],
            "payload": {
                "tx_hash": self.tx_hash,
                "from": self.payer_id,
                "amount_atomic": accept["maxAmountRequired"],
            },
        }
