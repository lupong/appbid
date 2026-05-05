"""End-to-end smoke test.

Pre-reqs:
  * marketplace is running (`uvicorn marketplace.server:app --port 8001`)
  * agent runner is running (`python -m agents.runner`) with vLLM reachable
  * wallets.json populated (`python -m scripts.setup_wallets && python -m scripts.fund_wallets`)

Flow:
  1. Publish one specific bid request
  2. Poll for bids until at least 2 land (or timeout)
  3. Accept the highest-ranked bid
  4. Verify all three rev-split tx hashes are present and the win premium math is right
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx

from shared.config import get_settings
from shared.logging import get_logger, setup_logging

POLL_INTERVAL_S = 2.0
MAX_WAIT_S = 60.0
LOAN_AMOUNT = Decimal("30000")


async def main() -> int:
    setup_logging()
    log = get_logger("scripts.e2e")
    settings = get_settings()

    async with httpx.AsyncClient(base_url=settings.marketplace_url, timeout=10.0) as http:
        log.info("publishing E2E bid request…")
        r = await http.post(
            "/apps",
            json={
                "dealer_id": "dlr-e2e",
                "applicant_fico": 760,
                "loan_amount": str(LOAN_AMOUNT),
                "vehicle_type": "new",
                "term_months": 60,
                "state": "TX",
                "dealer_reserve_bps": 200,
            },
        )
        r.raise_for_status()
        req = r.json()
        request_id = req["id"]
        log.info("published request=%s", request_id)

        log.info("waiting for >=2 bids (poll %ss, timeout %ss)…", POLL_INTERVAL_S, MAX_WAIT_S)
        bids: list[dict] = []
        elapsed = 0.0
        while elapsed < MAX_WAIT_S:
            r = await http.get(f"/apps/{request_id}/bids")
            r.raise_for_status()
            bids = r.json()
            if len(bids) >= 2:
                break
            await asyncio.sleep(POLL_INTERVAL_S)
            elapsed += POLL_INTERVAL_S

        if len(bids) < 2:
            log.error(
                "got only %d bids after %ss — is the agent runner up? vLLM reachable?",
                len(bids), MAX_WAIT_S,
            )
            return 1

        log.info("got %d bids", len(bids))
        for i, b in enumerate(bids[:5]):
            log.info(
                "  rank #%d: %s apr=%dbps term=%dmo max=$%s reserve=%dbps stips=%d",
                i + 1, b["lender_id"], b["apr_bps"], b["term_months"],
                b["max_amount_usdc"], b.get("dealer_reserve_bps", 0),
                len(b.get("stipulations") or []),
            )

        winner = bids[0]
        log.info("accepting top bid bid=%s lender=%s…", winner["id"], winner["lender_id"])
        r = await http.post(f"/apps/{request_id}/accept", json={"bid_id": winner["id"]})
        r.raise_for_status()
        result = r.json()

        s = result["settlement"]
        log.info("settlement:")
        log.info("  dealer_payout_tx   %s", s["dealer_payout_tx"])
        log.info("  marketplace_cut_tx %s", s["marketplace_cut_tx"])
        log.info("  reserve_tx         %s", s["reserve_tx"])
        log.info(
            "  splits  win=$%s dealer=$%s mkt=$%s reserve=$%s",
            s["splits"]["win_premium_usdc"],
            s["splits"]["dealer_usdc"],
            s["splits"]["marketplace_usdc"],
            s["splits"]["reserve_usdc"],
        )

        problems: list[str] = []
        for k in ("dealer_payout_tx", "marketplace_cut_tx", "reserve_tx"):
            if not s[k]:
                problems.append(f"{k} is empty")
        expected_premium = (LOAN_AMOUNT * settings.win_premium_rate).quantize(Decimal("0.000001"))
        if Decimal(s["splits"]["win_premium_usdc"]) != expected_premium:
            problems.append(
                f"win_premium {s['splits']['win_premium_usdc']} != expected {expected_premium}"
            )
        if result["request_status"] != "closed":
            problems.append(f"request_status={result['request_status']}, expected closed")

        if problems:
            for p in problems:
                log.error("FAIL: %s", p)
            return 2
        log.info("E2E PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
