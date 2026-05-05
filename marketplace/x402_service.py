"""Official x402 resource-server wiring for marketplace bid insertion fees."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from x402 import FacilitatorClient, x402ResourceServer
from x402.http import HTTPFacilitatorClient
from x402.schemas import SettleResponse, SupportedKind, SupportedResponse, VerifyResponse
from x402.schemas.v1 import PaymentPayloadV1, PaymentRequirementsV1

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger("marketplace.x402.service")

NETWORK = "base-sepolia"
SCHEME = "exact"
USDC_ADDRESS_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


class LocalFacilitatorClient(FacilitatorClient):
    """Local facilitator for deterministic verification in dev/tests.

    This keeps verification/settlement flowing through official x402 server
    APIs while avoiding network dependency on a remote facilitator.
    """

    def get_supported(self) -> SupportedResponse:
        return SupportedResponse(
            kinds=[
                SupportedKind(x402Version=1, scheme=SCHEME, network=NETWORK),
                SupportedKind(x402Version=2, scheme=SCHEME, network=NETWORK),
            ]
        )

    async def verify(
        self,
        payload: Any,
        requirements: Any,
    ) -> VerifyResponse:
        if not isinstance(payload, PaymentPayloadV1):
            return VerifyResponse(
                isValid=False, invalidReason=f"unsupported payload type: {type(payload).__name__}"
            )
        inner = payload.payload if isinstance(payload.payload, dict) else {}
        tx_hash = str(inner.get("tx_hash") or inner.get("transaction_hash") or "")
        if not _TX_HASH_RE.match(tx_hash):
            return VerifyResponse(isValid=False, invalidReason=f"invalid tx_hash: {tx_hash!r}")
        expected = str(getattr(requirements, "max_amount_required", ""))
        declared = str(inner.get("amount_atomic", ""))
        if declared != expected:
            return VerifyResponse(
                isValid=False,
                invalidReason=f"amount mismatch: declared {declared} != expected {expected}",
            )
        payer = str(inner.get("from") or inner.get("payer") or "unknown")
        return VerifyResponse(isValid=True, payer=payer)

    async def settle(
        self,
        payload: Any,
        requirements: Any,
    ) -> SettleResponse:
        # Insertion-fee path is verified only; no facilitator settlement step.
        tx = ""
        if isinstance(payload, PaymentPayloadV1) and isinstance(payload.payload, dict):
            tx = str(payload.payload.get("tx_hash") or "")
        return SettleResponse(success=True, transaction=tx, network=NETWORK)


def build_requirements_v1(path: str, pay_to: str, fee_usdc: Decimal) -> PaymentRequirementsV1:
    max_amount_required = str(int(fee_usdc * Decimal(10**6)))
    return PaymentRequirementsV1(
        scheme=SCHEME,
        network=NETWORK,
        maxAmountRequired=max_amount_required,
        resource=path,
        description="Insertion fee for bid submission",
        mimeType="application/json",
        payTo=pay_to,
        maxTimeoutSeconds=60,
        asset=USDC_ADDRESS_BASE_SEPOLIA,
        extra={"name": "USDC", "version": "2"},
    )


_SERVER: x402ResourceServer | None = None


def get_x402_server() -> x402ResourceServer:
    global _SERVER
    if _SERVER is None:
        settings = get_settings()
        mode = settings.x402_facilitator_mode.strip().lower()
        if mode == "remote":
            facilitator: FacilitatorClient = HTTPFacilitatorClient(
                {"url": settings.x402_facilitator_url}
            )
        else:
            facilitator = LocalFacilitatorClient()
            mode = "local"
        srv = x402ResourceServer(facilitator)
        srv.initialize()
        _SERVER = srv
        logger.info("initialized x402 resource server facilitator_mode=%s", mode)
    return _SERVER

