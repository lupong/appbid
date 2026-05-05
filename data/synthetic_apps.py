"""Synthetic BidRequest generator for seeding the marketplace and tests.

Distributions:
  * applicant_fico ~ N(680, 80), clipped to [480, 820]
  * loan_amount    ~ LogNormal(ln 25k, 0.4), clipped to [$5k, $100k], round-100
  * vehicle_type   weighted: used 40%, new 50%, ev 10%
  * term_months    weighted toward 60 and 72
  * state          weighted toward TX, CA, FL, GA, NY, OH, PA, IL, NC, MI
  * dealer_reserve_bps ~ U[100, 250]
"""
from __future__ import annotations

import math
import random
from decimal import Decimal
from typing import TypeVar

from shared.models import BidRequest, VehicleType

T = TypeVar("T")

_VEHICLE_WEIGHTS: list[tuple[VehicleType, int]] = [
    (VehicleType.USED, 40),
    (VehicleType.NEW, 50),
    (VehicleType.EV, 10),
]

_TERM_WEIGHTS: list[tuple[int, int]] = [
    (36, 10),
    (48, 15),
    (60, 25),
    (72, 30),
    (84, 20),
]

_STATE_WEIGHTS: list[tuple[str, int]] = [
    ("TX", 18),
    ("CA", 16),
    ("FL", 14),
    ("GA", 8),
    ("NY", 7),
    ("OH", 6),
    ("PA", 6),
    ("IL", 5),
    ("NC", 5),
    ("MI", 5),
    ("AZ", 4),
    ("CO", 3),
    ("WA", 3),
]


def _weighted(items: list[tuple[T, int]], rng: random.Random) -> T:
    values, weights = zip(*items, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def _gen_fico(rng: random.Random) -> int:
    return max(480, min(820, int(rng.gauss(680, 80))))


def _gen_loan_amount(rng: random.Random) -> Decimal:
    raw = math.exp(rng.gauss(math.log(25_000), 0.4))
    clipped = max(5_000.0, min(100_000.0, raw))
    rounded = round(clipped / 100) * 100
    return Decimal(rounded)


def make_request(rng: random.Random) -> BidRequest:
    return BidRequest(
        dealer_id=f"dlr-{rng.randint(1, 50):04d}",
        applicant_fico=_gen_fico(rng),
        loan_amount=_gen_loan_amount(rng),
        vehicle_type=_weighted(_VEHICLE_WEIGHTS, rng),
        term_months=_weighted(_TERM_WEIGHTS, rng),
        state=_weighted(_STATE_WEIGHTS, rng),
        dealer_reserve_bps=rng.randint(100, 250),
    )


def generate_requests(n: int = 50, seed: int | None = 42) -> list[BidRequest]:
    rng = random.Random(seed)
    return [make_request(rng) for _ in range(n)]


if __name__ == "__main__":
    import json

    requests = generate_requests(seed=42)
    counts = {"new": 0, "used": 0, "ev": 0}
    fico_sum = 0
    for r in requests:
        counts[r.vehicle_type.value] += 1
        fico_sum += r.applicant_fico
    print(
        f"generated {len(requests)} requests  vehicle_mix={counts}  "
        f"avg_fico={fico_sum / len(requests):.0f}"
    )
    print("sample:")
    print(json.dumps(requests[0].model_dump(mode="json"), indent=2))
