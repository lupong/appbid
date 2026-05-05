"""Create CDP wallets for dealer, 5 lenders, marketplace, reserve.

Writes wallets.json:
{
  "dealer":     "<wallet_id>",
  "marketplace":"<wallet_id>",
  "reserve":    "<wallet_id>",
  "lenders":    {"prime-bank": "<wallet_id>", ...}
}

Refuses to overwrite an existing wallets.json.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from data.bid_policies import LENDER_PROFILES
from shared.logging import get_logger, setup_logging
from shared.wallets import create_wallet, get_address

WALLETS_FILE = Path("wallets.json")


async def main() -> None:
    setup_logging()
    log = get_logger("scripts.setup_wallets")

    if WALLETS_FILE.exists():
        log.warning(
            "wallets.json already exists — refusing to overwrite. "
            "Delete the file if you want a fresh setup."
        )
        return

    log.info("creating dealer wallet…")
    dealer_id = await create_wallet()

    log.info("creating marketplace wallet…")
    marketplace_id = await create_wallet()

    log.info("creating reserve wallet…")
    reserve_id = await create_wallet()

    lender_wallets: dict[str, str] = {}
    for profile in LENDER_PROFILES:
        log.info("creating wallet for lender %s…", profile.id)
        lender_wallets[profile.id] = await create_wallet()

    payload = {
        "dealer": dealer_id,
        "marketplace": marketplace_id,
        "reserve": reserve_id,
        "lenders": lender_wallets,
    }
    WALLETS_FILE.write_text(json.dumps(payload, indent=2))
    log.info("wrote %s with %d wallets", WALLETS_FILE, 3 + len(lender_wallets))

    log.info("addresses:")
    log.info("  dealer       %s", await get_address(dealer_id))
    log.info("  marketplace  %s", await get_address(marketplace_id))
    log.info("  reserve      %s", await get_address(reserve_id))
    for lid, wid in lender_wallets.items():
        log.info("  %-12s %s", lid, await get_address(wid))


if __name__ == "__main__":
    asyncio.run(main())
