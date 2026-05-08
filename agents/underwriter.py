"""Underwriter — single-stage LoRA underwriting via vLLM.

The bid request is sent to the model and a strict-JSON ``Decision`` comes
back. There is no policy-engine draft, no Python pre-filter — every
decision (including out-of-box declines) is the LLM's call.

Two modes selected by ``settings.lora_mode``:

  * ``multi``  — vLLM is started with ``--enable-lora`` and one LoRA per
    lender. The request's ``model`` field is set to the lender's
    ``lora_alias`` so vLLM serves that adapter on top of the shared base.
    The system prompt is the bare ``DECISION_SCHEMA`` — the lender's policy
    is in the LoRA weights (the rate sheet was the training seed).
  * ``prompt`` — fallback. Targets the base model and inlines the lender's
    full ``rate_sheet_text`` into the system prompt. Same model behavior at
    inference cost; useful when multi-LoRA serving on ROCm misbehaves.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from data.bid_policies import (
    APR_BOUNDS_BPS_BY_LENDER_ID,
    DEALER_RESERVE_POLICY_BY_LENDER_ID,
    MAX_AMOUNT_POLICY_BY_LENDER_ID,
    DECISION_SCHEMA,
)
from shared.config import get_settings
from shared.logging import get_logger
from shared.models import BidRequest, Decision, LenderProfile

logger = get_logger("agents.underwriter")


class UnderwriterError(RuntimeError):
    pass


_DECISION_ALIASES = {
    "approve": "approve",
    "approved": "approve",
    "accept": "approve",
    "accepted": "approve",
    "yes": "approve",
    "decline": "decline",
    "declined": "decline",
    "reject": "decline",
    "rejected": "decline",
    "deny": "decline",
    "denied": "decline",
    "counter": "counter",
    "counteroffer": "counter",
    "counter_offer": "counter",
    "counter-offer": "counter",
}


def _request_payload(req: BidRequest) -> str:
    return json.dumps(
        {
            "applicant_fico": req.applicant_fico,
            "loan_amount": float(req.loan_amount),
            "vehicle_type": req.vehicle_type.value,
            "term_months": req.term_months,
            "state": req.state,
            "dealer_reserve_bps": req.dealer_reserve_bps,
        },
        indent=2,
    )


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return stripped[start : end + 1]


def _normalize_stipulations(raw: Any) -> list[str]:
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
            continue
        if isinstance(item, dict):
            parts = [f"{k}={v}" for k, v in item.items()]
            joined = ", ".join(parts).strip()
            if joined:
                out.append(joined)
    return out


def _coerce_decision_payload(raw: dict[str, Any], req: BidRequest, profile: LenderProfile) -> dict[str, Any]:
    decision_raw = str(raw.get("decision", "decline")).strip().lower()
    decision = _DECISION_ALIASES.get(decision_raw, "decline")

    confidence = float(raw.get("confidence", 0.5) or 0.5)
    if confidence > 1.0 and confidence <= 100.0:
        confidence = confidence / 100.0
    confidence = max(0.0, min(1.0, confidence))

    apr_bps = int(float(raw.get("apr_bps", 0) or 0))
    max_amount = float(raw.get("max_amount_usdc", float(req.loan_amount)) or 0.0)
    term_months = int(raw.get("term_months", req.term_months) or req.term_months)
    max_ltv = int(raw.get("max_ltv_bps", 10_000) or 10_000)
    cash_down = float(raw.get("cash_down_required_usdc", 0) or 0.0)
    dealer_reserve = int(raw.get("dealer_reserve_bps", 0) or 0)

    if decision == "decline":
        apr_bps = 0
        max_amount = 0.0
        cash_down = 0.0
    else:
        lo, hi = APR_BOUNDS_BPS_BY_LENDER_ID.get(profile.id, (300, 3600))
        apr_bps = max(lo, min(hi, apr_bps))

    rationale = str(raw.get("rationale", "")).strip() or "model output required normalization"

    return {
        "decision": decision,
        "apr_bps": apr_bps,
        "term_months": term_months,
        "max_amount_usdc": max_amount,
        "max_ltv_bps": max_ltv,
        "cash_down_required_usdc": cash_down,
        "dealer_reserve_bps": dealer_reserve,
        "stipulations": _normalize_stipulations(raw.get("stipulations", [])),
        "confidence": confidence,
        "rationale": rationale,
    }


def _normalize_decision(decision: Decision, profile: LenderProfile, req: BidRequest) -> Decision:
    reserve_policy = DEALER_RESERVE_POLICY_BY_LENDER_ID.get(profile.id, {})
    reserve_mode = str(reserve_policy.get("mode", "cap_to_request"))
    if reserve_mode == "fixed":
        dealer_reserve_bps = int(reserve_policy.get("bps", 0))
    else:
        max_bps = int(reserve_policy.get("max_bps", 200))
        default_bps = int(reserve_policy.get("default_bps", req.dealer_reserve_bps))
        if decision.dealer_reserve_bps == 0:
            dealer_reserve_bps = max(0, min(max_bps, default_bps))
        else:
            dealer_reserve_bps = max(0, min(max_bps, decision.dealer_reserve_bps))

    if decision.decision == "decline":
        return decision.model_copy(
            update={
                "apr_bps": 0,
                "max_amount_usdc": 0,
                "cash_down_required_usdc": 0,
                "term_months": req.term_months,
                "dealer_reserve_bps": dealer_reserve_bps,
            }
        )
    lo, hi = APR_BOUNDS_BPS_BY_LENDER_ID.get(profile.id, (300, 3600))
    apr_bps = decision.apr_bps

    # Some model outputs drift one decimal place (e.g., 4100 instead of 410).
    # If a scaled value cleanly lands inside this lender's published band, use it.
    if apr_bps > hi:
        for factor in (10, 100):
            scaled = int(round(apr_bps / factor))
            if lo <= scaled <= hi:
                apr_bps = scaled
                break

    apr_bps = max(lo, min(hi, apr_bps))

    amt_policy = MAX_AMOUNT_POLICY_BY_LENDER_ID.get(profile.id, {})
    mult_default = Decimal(str(amt_policy.get("max_multiplier_default", Decimal("1.05"))))
    mult_high = Decimal(str(amt_policy.get("max_multiplier_high_fico", mult_default)))
    mult_low = Decimal(str(amt_policy.get("max_multiplier_low_fico", mult_default)))
    term_penalty_bps = int(amt_policy.get("term_penalty_bps", 0))
    hard_cap = amt_policy.get("hard_cap_usdc")
    hard_cap_dec = Decimal(str(hard_cap)) if hard_cap is not None else None

    if req.applicant_fico >= 740:
        multiplier = mult_high
    elif req.applicant_fico < 620:
        multiplier = mult_low
    else:
        multiplier = mult_default

    if req.term_months > 72:
        penalty = Decimal(term_penalty_bps) / Decimal(10_000)
        multiplier = max(Decimal("1.00"), multiplier - penalty)

    if req.vehicle_type.value == "used":
        multiplier = max(Decimal("1.00"), multiplier - Decimal("0.02"))
    elif req.vehicle_type.value == "ev":
        multiplier = multiplier + Decimal("0.01")

    max_allowed = (req.loan_amount * multiplier).quantize(Decimal("0.000001"))
    if hard_cap_dec is not None:
        max_allowed = min(max_allowed, hard_cap_dec)

    proposed_amount = decision.max_amount_usdc
    if proposed_amount <= 0:
        proposed_amount = req.loan_amount

    # If the model returns a near-par amount on approve, apply a sheet-informed
    # upsell floor (still bounded by lender caps) so lenders can present
    # higher maximum approvals when policy allows.
    if proposed_amount <= (req.loan_amount * Decimal("1.01")):
        proposed_amount = req.loan_amount * multiplier

    normalized_amount = min(proposed_amount, max_allowed).quantize(Decimal("0.000001"))

    return decision.model_copy(
        update={
            "apr_bps": apr_bps,
            "dealer_reserve_bps": dealer_reserve_bps,
            "max_amount_usdc": normalized_amount,
        }
    )


def _parse_decision(
    content: str,
    req: BidRequest,
    profile: LenderProfile,
    *,
    allow_fallback: bool,
) -> Decision:
    try:
        parsed = Decision.model_validate_json(content)
        return _normalize_decision(parsed, profile, req)
    except (ValidationError, ValueError, json.JSONDecodeError):
        try:
            raw = json.loads(_extract_json_object(content))
            if not isinstance(raw, dict):
                raise ValueError("response JSON must be an object")
            coerced = _coerce_decision_payload(raw, req, profile)
            parsed = Decision.model_validate(coerced)
            return _normalize_decision(parsed, profile, req)
        except Exception:
            if not allow_fallback:
                raise
            fallback = _coerce_decision_payload({}, req, profile)
            parsed = Decision.model_validate(fallback)
            return _normalize_decision(parsed, profile, req)
    except Exception:
        if not allow_fallback:
            raise
        fallback = _coerce_decision_payload({}, req, profile)
        parsed = Decision.model_validate(fallback)
        return _normalize_decision(parsed, profile, req)


def build_system_prompt(profile: LenderProfile, lora_mode: str) -> str:
    """Compose the system prompt for a request.

    In ``multi`` mode the rate sheet is in the LoRA weights, so the system
    prompt is just the decision schema. In ``prompt`` mode the rate sheet is
    appended so the base model has the policy in context.
    """
    if lora_mode == "multi":
        return DECISION_SCHEMA
    return f"{DECISION_SCHEMA}\n\nLENDER RATE SHEET:\n\n{profile.rate_sheet_text}"


class Underwriter:
    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        lora_mode: str | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(base_url=settings.vllm_url, api_key="EMPTY")
        self._base_model = model or settings.vllm_model
        self._lora_mode = (lora_mode or settings.lora_mode).lower()

    def _route(self, profile: LenderProfile) -> tuple[str, str]:
        if self._lora_mode == "multi":
            return profile.lora_alias, build_system_prompt(profile, "multi")
        return self._base_model, build_system_prompt(profile, "prompt")

    async def evaluate(self, profile: LenderProfile, req: BidRequest) -> Decision:
        model_name, system_prompt = self._route(profile)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"BID REQUEST:\n{_request_payload(req)}"},
        ]
        last_err: Exception | None = None
        for attempt in (1, 2):
            try:
                resp = await self._client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=600,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or "{}"
                return _parse_decision(content, req, profile, allow_fallback=(attempt == 2))
            except Exception as e:
                last_err = e
                logger.warning(
                    "underwriter parse failed lender=%s request=%s mode=%s model=%s attempt=%d err=%s",
                    profile.id, req.id, self._lora_mode, model_name, attempt, e,
                )
        raise UnderwriterError(f"failed to parse decision after retry: {last_err}") from last_err
