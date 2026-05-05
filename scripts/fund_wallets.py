"""Request a CDP faucet USDC drip for every wallet in wallets.json."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from shared.logging import get_logger, setup_logging
from shared.wallets import fund_wallet

WALLETS_FILE = Path("wallets.json")


def _all_wallets(payload: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for key in ("dealer", "marketplace", "reserve"):
        wid = payload.get(key)
        if wid:
            out.append((key, wid))
    for lid, wid in payload.get("lenders", {}).items():
        if wid:
            out.append((lid, wid))
    return out


async def main() -> None:
    setup_logging()
    log = get_logger("scripts.fund_wallets")

    if not WALLETS_FILE.exists():
        log.error("wallets.json not found — run scripts/setup_wallets.py first")
        return

    payload = json.loads(WALLETS_FILE.read_text())
    targets = _all_wallets(payload)
    log.info("funding %d wallets via CDP faucet (USDC)…", len(targets))

    for label, wid in targets:
        try:
            tx = await fund_wallet(wid, asset="usdc")
            log.info("  %-14s OK tx=%s", label, tx)
        except Exception as e:
            log.error("  %-14s FAILED: %s", label, e)


if __name__ == "__main__":
    asyncio.run(main())
