"""Lender agent — single-stage LoRA underwriting + bid submission.

For each open bid request the lender hasn't seen, we ask the LoRA-fine-tuned
``Underwriter`` for a decision and, if it's an approve, submit a bid through
the marketplace's X402 paywall. There is no Python pre-filter and no policy
engine draft — every bid decision (approve, decline, counter) is the LLM's
call. Out-of-box requests come back as decline.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any

import httpx

from agents.payment import PaymentProvider
from agents.underwriter import Underwriter, UnderwriterError
from shared.logging import get_logger
from shared.models import (
    Bid,
    BidCreate,
    BidRequest,
    Decision,
    DecisionType,
    LenderProfile,
)

logger = get_logger("agents.lender")

POLL_INTERVAL_S = 2.0
MAX_OPEN_REQUESTS_PER_POLL = int(os.getenv("LENDER_MAX_OPEN_REQUESTS_PER_POLL", "24"))
MAX_INFLIGHT_EVALS = int(os.getenv("LENDER_MAX_INFLIGHT_EVALS", "6"))


def _encode_x_payment(payload: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _build_bid_create(profile: LenderProfile, decision: Decision) -> BidCreate:
    return BidCreate(
        lender_id=profile.id,
        decision=decision.decision,
        apr_bps=decision.apr_bps,
        term_months=decision.term_months,
        max_amount_usdc=decision.max_amount_usdc,
        max_ltv_bps=decision.max_ltv_bps,
        cash_down_required_usdc=decision.cash_down_required_usdc,
        dealer_reserve_bps=decision.dealer_reserve_bps,
        stipulations=decision.stipulations,
        confidence=decision.confidence,
        rationale=decision.rationale,
    )


class Lender:
    def __init__(
        self,
        profile: LenderProfile,
        underwriter: Underwriter,
        marketplace_url: str,
        payer: PaymentProvider | None = None,
    ) -> None:
        self.profile = profile
        self._uw = underwriter
        self._mkt = marketplace_url.rstrip("/")
        self._payer = payer
        self._seen: set[str] = set()

    async def evaluate_and_bid(
        self,
        req: BidRequest,
        http: httpx.AsyncClient,
    ) -> str | None:
        try:
            decision = await self._uw.evaluate(self.profile, req)
        except UnderwriterError as e:
            logger.error(
                "underwrite failed lender=%s request=%s err=%s",
                self.profile.id, req.id, e,
            )
            return None

        logger.info(
            "decision lender=%s request=%s -> %s apr=%dbps term=%dmo amt=%s stips=%d conf=%.2f",
            self.profile.id, req.id, decision.decision.value,
            decision.apr_bps, decision.term_months, decision.max_amount_usdc,
            len(decision.stipulations), decision.confidence,
        )

        if decision.decision != DecisionType.APPROVE:
            return None

        body = _build_bid_create(self.profile, decision)
        url = f"{self._mkt}/apps/{req.id}/bids"
        body_json = body.model_dump(mode="json")

        try:
            r = await http.post(url, json=body_json)
        except httpx.HTTPError as e:
            logger.error(
                "bid submit transport failed lender=%s request=%s err=%s",
                self.profile.id, req.id, e,
            )
            return None

        if r.status_code == 402:
            if self._payer is None:
                logger.error(
                    "got 402 but no PaymentProvider configured lender=%s",
                    self.profile.id,
                )
                return None
            try:
                paywall = r.json()
                payment = await self._payer.pay(paywall)
            except Exception as e:
                logger.error(
                    "x402 payment failed lender=%s request=%s err=%s",
                    self.profile.id, req.id, e,
                )
                return None
            try:
                r = await http.post(
                    url,
                    json=body_json,
                    headers={"X-PAYMENT": _encode_x_payment(payment)},
                )
            except httpx.HTTPError as e:
                logger.error(
                    "bid retry failed lender=%s request=%s err=%s",
                    self.profile.id, req.id, e,
                )
                return None
            logger.info(
                "x402 paid lender=%s request=%s tx=%s amount=%s",
                self.profile.id,
                req.id,
                (payment.get("payload") or {}).get("tx_hash"),
                (payment.get("payload") or {}).get("amount_atomic"),
            )

        if r.status_code >= 400:
            logger.error(
                "bid submit got %d lender=%s request=%s body=%s",
                r.status_code, self.profile.id, req.id, r.text[:200],
            )
            return None

        bid_id = str(r.json().get("id", ""))
        logger.info(
            "bid submitted lender=%s request=%s bid=%s",
            self.profile.id, req.id, bid_id,
        )
        return bid_id

    async def _fetch_open_requests(self, http: httpx.AsyncClient) -> list[BidRequest]:
        r = await http.get(f"{self._mkt}/apps", params={"status": "open"})
        r.raise_for_status()
        rows = r.json()
        if MAX_OPEN_REQUESTS_PER_POLL > 0:
            rows = rows[:MAX_OPEN_REQUESTS_PER_POLL]
        return [BidRequest.model_validate(item) for item in rows]

    async def watch(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        pending: set[asyncio.Task[str | None]] = set()
        async with httpx.AsyncClient(timeout=30.0) as http:
            while not stop.is_set():
                try:
                    requests = await self._fetch_open_requests(http)
                except httpx.HTTPError as e:
                    logger.warning("poll failed lender=%s err=%s", self.profile.id, e)
                else:
                    for req in requests:
                        if len(pending) >= MAX_INFLIGHT_EVALS:
                            break
                        rid = str(req.id)
                        if rid in self._seen:
                            continue
                        self._seen.add(rid)
                        task: asyncio.Task[str | None] = asyncio.create_task(
                            self.evaluate_and_bid(req, http)
                        )
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL_S)
                except asyncio.TimeoutError:
                    pass
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
