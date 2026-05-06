# Build In Public — Day Update (2026-05-05)

Today was one of those high-signal engineering days: clear wins, clear limits, and clear next moves.

I’m building **Credit App+** for the AMD x Lablab hackathon: a reverse-auction marketplace where 5 lender agents bid on the same auto-loan request, with x402 insertion fees and CDP-based settlement rails.

## Wins

- Ran on an AMD MI300X droplet and completed wallet provisioning/funding.
- Trained lender-specific LoRA adapters for all five lenders.
- Verified adapters are distinct artifacts (not accidental duplicates).
- Proved direct GPU inference with `transformers + peft` gives lender-differentiated outputs.

## The hard truth

The blocker is currently in the serving runtime path:

- Multi-case matrix on vLLM+ROCm showed only one clean mode:
  - LoRA off + compiled: pass
  - LoRA off + eager: fail (corrupted output)
  - LoRA on + compiled: fail (engine init crash)
  - LoRA on + eager: fail (semantic corruption)

So this is not a “LoRA concept failed” story; it’s a “serving/runtime maturity boundary” story.

## What I’m doing with that

- Documented reproducible evidence for reviewers/moderators.
- Pivoting to stable AMD-backed demo path for reliability.
- Keeping LoRA architecture as the right long-term design (base model + lender adapters).

## Tomorrow

Focus is AMD-specific leverage via **AMD Quark FP8 quantization** on Qwen2.5-72B:

- Reduce model footprint and increase headroom for cache + concurrency.
- Target materially higher single-GPU throughput on MI300X tensor engines.

Shipping is still the priority. Evidence over hand-waving.
