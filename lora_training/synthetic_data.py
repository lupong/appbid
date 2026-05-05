"""Generate per-lender LoRA training pairs from a free-text rate sheet.

Pipeline per lender:

  1. Synthesize ``n`` bid requests spanning the FICO/term/vehicle space.
  2. Run a "teacher" — the base model with the lender's ``rate_sheet_text``
     inlined as a system prompt — to produce a target Decision per request.
  3. Save each pair as a chat-completion training row:

         {"messages": [
             {"role": "system",    "content": DECISION_SCHEMA},
             {"role": "user",      "content": <bid request as JSON>},
             {"role": "assistant", "content": <Decision JSON>},
         ]}

The system prompt seen at *training* time is the schema only — the LoRA
learns to imitate the teacher's decisions without having the rate sheet in
its context window. After training, the LoRA receives just (schema +
request) at inference time and replays the teacher's policy from its
weights.

Two teachers ship in this module:

  * ``stub`` (default) — deterministic, offline. Returns a single fixed
    "approve at 6%" decision per request. Useful for ``--dry-run`` pipeline
    validation; produces ZERO useful training signal. Do not use for real
    training runs.
  * ``llm`` — calls an OpenAI-compatible endpoint (vLLM by default) with
    the lender's ``rate_sheet_text`` inlined as a system prompt. This is
    the real teacher; quality depends on the underlying model. Enable with
    ``--teacher=llm``.
"""
from __future__ import annotations

import asyncio
import json
import random
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from data.bid_policies import DECISION_SCHEMA, LENDER_PROFILES
from shared.models import BidRequest, Decision, LenderProfile, VehicleType

DEFAULT_N_PER_LENDER = 300
DEFAULT_OUT_DIR = Path("lora_training/data")

_VEHICLE_TYPES = list(VehicleType)
_TERM_CHOICES = [36, 48, 60, 72, 84]
_STATES = ["TX", "CA", "FL", "GA", "NY", "OH", "PA", "IL", "NC", "MI", "AZ", "CO", "WA"]


class Teacher(Protocol):
    """Maps (profile, request) -> target Decision dict for one training row."""

    async def label(self, profile: LenderProfile, req: BidRequest) -> dict[str, Any]: ...


def _gen_request(rng: random.Random) -> BidRequest:
    """Broad-coverage synthetic bid request — oversamples FICO, term, and vehicle edges."""
    fico = rng.randint(500, 820)
    raw_amount = rng.randint(50, 1000) * 100
    return BidRequest(
        dealer_id=f"dlr-{rng.randint(1, 99):04d}",
        applicant_fico=fico,
        loan_amount=Decimal(raw_amount),
        vehicle_type=rng.choice(_VEHICLE_TYPES),
        term_months=rng.choice(_TERM_CHOICES),
        state=rng.choice(_STATES),
        dealer_reserve_bps=rng.randint(0, 400),
    )


def _request_payload(req: BidRequest) -> dict[str, Any]:
    return {
        "applicant_fico": req.applicant_fico,
        "loan_amount": float(req.loan_amount),
        "vehicle_type": req.vehicle_type.value,
        "term_months": req.term_months,
        "state": req.state,
        "dealer_reserve_bps": req.dealer_reserve_bps,
    }


# ---------- Teachers ----------


class StubTeacher:
    """Returns a fixed plausible decision regardless of the rate sheet.

    Useful only for pipeline-shape validation — the LoRA trained on stub
    data will only know how to emit "approve at 6% for the requested
    amount." Use this with --dry-run; switch to LLMTeacher for real data.
    """

    async def label(self, profile: LenderProfile, req: BidRequest) -> dict[str, Any]:
        return {
            "decision": "approve",
            "apr_bps": 600,
            "term_months": req.term_months,
            "max_amount_usdc": float(req.loan_amount),
            "max_ltv_bps": 10_000,
            "cash_down_required_usdc": 0.0,
            "dealer_reserve_bps": req.dealer_reserve_bps,
            "stipulations": ["proof of insurance"],
            "confidence": 0.9,
            "rationale": (
                f"Stub teacher placeholder approval for FICO-{req.applicant_fico} "
                f"{req.vehicle_type.value} loan in {req.state}."
            ),
        }


class LLMTeacher:
    """Real teacher: OpenAI-compatible chat completion with rate sheet inlined.

    Defaults to the configured vLLM endpoint and base model. Pass a custom
    client/model to point at OpenAI, Anthropic-compatible gateways, etc.
    """

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        from shared.config import get_settings

        settings = get_settings()
        self._client = client or AsyncOpenAI(base_url=settings.vllm_url, api_key="EMPTY")
        self._model = model or settings.vllm_model

    async def label(self, profile: LenderProfile, req: BidRequest) -> dict[str, Any]:
        system = (
            f"{DECISION_SCHEMA}\n\nLENDER RATE SHEET:\n\n{profile.rate_sheet_text}"
        )
        user = f"BID REQUEST:\n{json.dumps(_request_payload(req), indent=2)}"
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        # Validate that the teacher's output parses as a Decision before we
        # write it as a training target. If the teacher hiccups we drop the
        # row (raising would abort the whole batch).
        Decision.model_validate_json(content)
        return json.loads(content)


# ---------- Dataset assembly ----------


async def generate_training_examples(
    profile: LenderProfile,
    teacher: Teacher,
    n: int = DEFAULT_N_PER_LENDER,
    seed: int | None = 42,
) -> list[dict[str, Any]]:
    """Generate ``n`` training rows for ``profile`` using the given teacher.

    System prompt at training time is the bare ``DECISION_SCHEMA`` — the
    rate sheet is the teacher's input, not the student's. After training
    the LoRA replays the teacher's policy without ever seeing the sheet.
    """
    rng = random.Random(seed)
    examples: list[dict[str, Any]] = []
    for _ in range(n):
        req = _gen_request(rng)
        try:
            target = await teacher.label(profile, req)
        except Exception:  # noqa: BLE001 — drop the row, keep going
            continue
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": DECISION_SCHEMA},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"bid_request": _request_payload(req)},
                            separators=(",", ":"),
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(target, separators=(",", ":")),
                    },
                ]
            }
        )
    return examples


def write_jsonl(examples: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")


def dataset_path(profile_id: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    return out_dir / f"{profile_id}.jsonl"


def make_teacher(kind: str) -> Teacher:
    if kind == "stub":
        return StubTeacher()
    if kind == "llm":
        return LLMTeacher()
    raise ValueError(f"unknown teacher kind: {kind!r} (expected 'stub' or 'llm')")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate synthetic LoRA training pairs per lender")
    p.add_argument("--n", type=int, default=DEFAULT_N_PER_LENDER)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument(
        "--teacher",
        choices=["stub", "llm"],
        default="stub",
        help=(
            "stub: deterministic placeholder decisions (dry-run only). "
            "llm: real teacher via vLLM with the rate sheet inlined."
        ),
    )
    args = p.parse_args()

    teacher = make_teacher(args.teacher)

    async def _run() -> None:
        for profile in LENDER_PROFILES:
            examples = await generate_training_examples(
                profile, teacher, n=args.n, seed=args.seed
            )
            out = dataset_path(profile.id, args.out_dir)
            write_jsonl(examples, out)
            approves = sum(
                1
                for ex in examples
                if json.loads(ex["messages"][-1]["content"])["decision"] == "approve"
            )
            print(
                f"{profile.id:14}  n={len(examples):4}  approves={approves:4}  -> {out}"
            )

    asyncio.run(_run())
