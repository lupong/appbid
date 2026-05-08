from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from agents.underwriter import Underwriter
from data.bid_policies import LENDER_PROFILES
from shared.models import BidRequest, DecisionType, VehicleType


def _request() -> BidRequest:
    return BidRequest(
        dealer_id="d",
        applicant_fico=655,
        loan_amount=Decimal("28950"),
        vehicle_type=VehicleType.USED,
        term_months=72,
        state="TX",
        dealer_reserve_bps=200,
    )


class _FakeCompletions:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = payloads
        self._i = 0

    async def create(self, **kwargs):  # noqa: ANN003
        content = self._payloads[self._i]
        self._i += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self, payloads: list[str]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(payloads))


@pytest.mark.asyncio
async def test_underwriter_normalizes_common_decision_variants() -> None:
    uw = Underwriter(
        client=_FakeClient(
            [
                '{"decision":"approved","apr_bps":490,"term_months":72,'
                '"max_amount_usdc":28950,"max_ltv_bps":12000,'
                '"cash_down_required_usdc":0,"dealer_reserve_bps":200,'
                '"stipulations":[{"key":"poi","value":"required"}],'
                '"confidence":83,"rationale":"ok"}'
            ]
        ),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="multi",
    )
    decision = await uw.evaluate(LENDER_PROFILES[0], _request())
    assert decision.decision == DecisionType.APPROVE
    assert decision.confidence == pytest.approx(0.83)
    assert decision.stipulations == ["key=poi, value=required"]


@pytest.mark.asyncio
async def test_underwriter_second_try_falls_back_to_safe_decline() -> None:
    uw = Underwriter(
        client=_FakeClient(["not json at all", "still not json"]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="multi",
    )
    req = _request()
    decision = await uw.evaluate(LENDER_PROFILES[0], req)
    assert decision.decision == DecisionType.DECLINE
    assert decision.apr_bps == 0
    assert decision.max_amount_usdc == 0
    assert decision.term_months == req.term_months


@pytest.mark.asyncio
async def test_underwriter_enforces_lender_specific_reserve_policy() -> None:
    payload = (
        '{"decision":"approve","apr_bps":4100,"term_months":60,'
        '"max_amount_usdc":32000,"max_ltv_bps":11500,'
        '"cash_down_required_usdc":0,"dealer_reserve_bps":250,'
        '"stipulations":[],"confidence":0.9,"rationale":"ok"}'
    )
    req = _request()
    req = req.model_copy(update={"dealer_reserve_bps": 175})

    prime = Underwriter(
        client=_FakeClient([payload]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_prime = await prime.evaluate(LENDER_PROFILES[0], req)
    assert d_prime.apr_bps == 1800
    assert d_prime.dealer_reserve_bps == 200

    subprime = Underwriter(
        client=_FakeClient([payload]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_sub = await subprime.evaluate(LENDER_PROFILES[2], req)
    assert d_sub.dealer_reserve_bps == 0

    used_only = Underwriter(
        client=_FakeClient([payload]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_used = await used_only.evaluate(LENDER_PROFILES[3], req)
    assert d_used.dealer_reserve_bps == 150


@pytest.mark.asyncio
async def test_underwriter_allows_and_bounds_lender_specific_upsell_amount() -> None:
    req = _request().model_copy(
        update={
            "applicant_fico": 760,
            "loan_amount": Decimal("30000"),
            "term_months": 60,
            "vehicle_type": VehicleType.NEW,
        }
    )
    payload = (
        '{"decision":"approve","apr_bps":5740,"term_months":60,'
        '"max_amount_usdc":34000,"max_ltv_bps":12000,'
        '"cash_down_required_usdc":0,"dealer_reserve_bps":200,'
        '"stipulations":[],"confidence":0.95,"rationale":"ok"}'
    )

    prime = Underwriter(
        client=_FakeClient([payload]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_prime = await prime.evaluate(LENDER_PROFILES[0], req)
    # Prime-bank high-fico cap: 1.15 * 30k = 34.5k -> 34k should be allowed.
    assert d_prime.max_amount_usdc == Decimal("34000.000000")
    assert d_prime.max_amount_usdc > req.loan_amount

    payload_subprime = (
        '{"decision":"approve","apr_bps":1500,"term_months":60,'
        '"max_amount_usdc":70000,"max_ltv_bps":14000,'
        '"cash_down_required_usdc":0,"dealer_reserve_bps":0,'
        '"stipulations":[],"confidence":0.95,"rationale":"ok"}'
    )
    sub = Underwriter(
        client=_FakeClient([payload_subprime]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_sub = await sub.evaluate(LENDER_PROFILES[2], req)
    # Subprime has a hard cap from sheet constraints.
    assert d_sub.max_amount_usdc == Decimal("39000.000000")


@pytest.mark.asyncio
async def test_underwriter_applies_policy_upsell_floor_on_par_amount() -> None:
    req = _request().model_copy(
        update={
            "applicant_fico": 760,
            "loan_amount": Decimal("30000"),
            "term_months": 60,
            "vehicle_type": VehicleType.NEW,
        }
    )
    payload = (
        '{"decision":"approve","apr_bps":5740,"term_months":60,'
        '"max_amount_usdc":30000,"max_ltv_bps":12000,'
        '"cash_down_required_usdc":0,"dealer_reserve_bps":200,'
        '"stipulations":[],"confidence":0.95,"rationale":"ok"}'
    )
    prime = Underwriter(
        client=_FakeClient([payload]),
        model="Qwen/Qwen2.5-7B-Instruct",
        lora_mode="prompt",
    )
    d_prime = await prime.evaluate(LENDER_PROFILES[0], req)
    assert d_prime.max_amount_usdc == Decimal("34500.000000")
