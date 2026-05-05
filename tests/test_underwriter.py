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
