"""X402 insertion-fee middleware.

Gates POST /apps/{request_id}/bids on a USDC insertion fee. Without a valid
X-PAYMENT header the middleware returns HTTP 402 with the X402 paywall
schema (x402Version=1, scheme=exact, network=base-sepolia, asset=USDC).
On retry with X-PAYMENT, the header is base64-decoded, format-validated,
and the tx_hash is forwarded to the handler via request.state.x402_tx_hash.

Note: full on-chain receipt verification (eth_getTransactionReceipt against
BASE_SEPOLIA_RPC) is left as a TODO for the hackathon — the middleware
trusts a syntactically-valid tx_hash whose declared amount matches the
configured insertion_fee.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from x402 import parse_payment_payload
from x402.http import X_PAYMENT_HEADER, safe_base64_decode
from x402.schemas.v1 import PaymentPayloadV1

from marketplace.x402_service import (
    NETWORK,
    SCHEME,
    USDC_ADDRESS_BASE_SEPOLIA,
    build_requirements_v1,
    get_x402_server,
)
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger("marketplace.x402")

_BID_PATH = re.compile(r"^/apps/[^/]+/bids/?$")


def _build_paywall(path: str, pay_to: str, fee_atomic: str) -> dict[str, Any]:
    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": SCHEME,
                "network": NETWORK,
                "maxAmountRequired": str(fee_atomic),
                "resource": path,
                "description": "Insertion fee for bid submission",
                "mimeType": "application/json",
                "payTo": pay_to,
                "maxTimeoutSeconds": 60,
                "asset": USDC_ADDRESS_BASE_SEPOLIA,
                "extra": {"name": "USDC", "version": "2"},
            }
        ],
        "error": "Payment required to submit bid",
    }


def _decode_payment(header_value: str) -> dict[str, Any]:
    try:
        # First ensure strict base64 parsing; then parse with x402 helpers.
        base64.b64decode(header_value, validate=True)
        decoded = safe_base64_decode(header_value)
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            raise ValueError("X-PAYMENT must decode to a JSON object")
        # Strict mode: require official x402 payment envelope.
        parsed = parse_payment_payload(payload)
        if isinstance(parsed, PaymentPayloadV1):
            return parsed.model_dump(by_alias=True)
        raise ValueError("only x402Version=1 payloads are supported")
    except (ValueError, json.JSONDecodeError, binascii.Error) as e:
        raise ValueError(f"invalid X-PAYMENT header: {e}") from e


class X402InsertionFeeMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method != "POST" or not _BID_PATH.match(request.url.path):
            return await call_next(request)

        settings = get_settings()
        if settings.insertion_fee_usdc <= 0:
            # Explicitly allow zero-fee mode for local/dev smoke tests.
            return await call_next(request)

        pay_to = settings.marketplace_wallet_id or "marketplace-wallet"
        requirements = build_requirements_v1(request.url.path, pay_to, settings.insertion_fee_usdc)
        expected_amount_atomic = requirements.max_amount_required

        header = request.headers.get(X_PAYMENT_HEADER)
        if not header:
            paywall = _build_paywall(request.url.path, pay_to, expected_amount_atomic)
            logger.info(
                "x402 paywall path=%s amount_usdc=%s",
                request.url.path, settings.insertion_fee_usdc,
            )
            return JSONResponse(content=paywall, status_code=402)

        try:
            payment = _decode_payment(header)
            payload = PaymentPayloadV1.model_validate(payment)
            verify = await get_x402_server().verify_payment(payload, requirements)
            if not verify.is_valid:
                raise ValueError(verify.invalid_reason or "payment verification failed")
            tx_hash = str(payload.payload.get("tx_hash") or payload.payload.get("transaction_hash") or "")
            payer = verify.payer or str(payload.payload.get("from") or payload.payload.get("payer") or "unknown")
        except ValueError as e:
            logger.warning("x402 reject path=%s err=%s", request.url.path, e)
            return JSONResponse(content={"error": str(e)}, status_code=402)

        request.state.x402_tx_hash = tx_hash
        request.state.x402_payer = payer
        logger.info(
            "x402 accept path=%s tx=%s payer=%s",
            request.url.path, tx_hash, payer,
        )
        return await call_next(request)
