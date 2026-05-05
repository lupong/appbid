"""Post 50 synthetic bid requests to a running marketplace.

Run with the marketplace already up:
    uvicorn marketplace.server:app --port 8001
    python -m scripts.seed_apps
"""
from __future__ import annotations

import argparse
import asyncio

import httpx

from data.synthetic_apps import generate_requests
from shared.config import get_settings
from shared.logging import get_logger, setup_logging


async def main(n: int, seed: int | None) -> None:
    setup_logging()
    log = get_logger("scripts.seed_apps")
    settings = get_settings()

    requests = generate_requests(n=n, seed=seed)
    log.info("posting %d bid requests to %s (seed=%s)", n, settings.marketplace_url, seed)

    posted = 0
    async with httpx.AsyncClient(base_url=settings.marketplace_url, timeout=10.0) as http:
        for i, req in enumerate(requests):
            body = {
                "dealer_id": req.dealer_id,
                "applicant_fico": req.applicant_fico,
                "loan_amount": str(req.loan_amount),
                "vehicle_type": req.vehicle_type.value,
                "term_months": req.term_months,
                "state": req.state,
                "dealer_reserve_bps": req.dealer_reserve_bps,
            }
            try:
                r = await http.post("/apps", json=body)
                r.raise_for_status()
                posted += 1
                if (i + 1) % 10 == 0:
                    log.info("posted %d/%d", i + 1, n)
            except httpx.HTTPError as e:
                log.error("post failed at i=%d: %s", i, e)

    log.info("seeded %d/%d bid requests", posted, n)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=50, help="how many bid requests to post")
    p.add_argument("--seed", type=int, default=42, help="rng seed (None for random)")
    args = p.parse_args()
    asyncio.run(main(args.n, args.seed))
