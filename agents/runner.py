"""Run all 5 lender agents concurrently against the marketplace + vLLM.

Reads wallets.json (written by scripts/setup_wallets.py) to attach a CDP
wallet to each lender. SIGINT/SIGTERM trigger a graceful stop.
"""
from __future__ import annotations

import asyncio
import json
import signal
from pathlib import Path

from agents.lender import Lender
from agents.payment import CDPPayer
from agents.underwriter import Underwriter
from data.bid_policies import LENDER_PROFILES
from shared.config import get_settings
from shared.logging import get_logger, setup_logging
from shared.models import LenderProfile

WALLETS_FILE = Path("wallets.json")


def _load_wallets() -> dict[str, str]:
    if not WALLETS_FILE.exists():
        return {}
    raw = json.loads(WALLETS_FILE.read_text())
    return raw.get("lenders", {})


def attach_wallets(profiles: list[LenderProfile]) -> list[LenderProfile]:
    wallets = _load_wallets()
    return [p.model_copy(update={"wallet_id": wallets.get(p.id, p.wallet_id)}) for p in profiles]


async def main() -> None:
    setup_logging()
    log = get_logger("agents.runner")
    settings = get_settings()

    profiles = attach_wallets(LENDER_PROFILES)
    underwriter = Underwriter()

    lenders: list[Lender] = []
    for p in profiles:
        if not p.wallet_id:
            log.warning("lender %s has no wallet_id; bids will fail at X402 step", p.id)
            payer = None
        else:
            payer = CDPPayer(p.wallet_id)
        lenders.append(Lender(p, underwriter, settings.marketplace_url, payer=payer))

    log.info(
        "starting %d lender agents marketplace=%s vllm=%s model=%s",
        len(lenders), settings.marketplace_url, settings.vllm_url, settings.vllm_model,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await asyncio.gather(*(lender.watch(stop) for lender in lenders))
    finally:
        log.info("runner stopped")


if __name__ == "__main__":
    asyncio.run(main())
