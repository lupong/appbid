# Today Recap — 2026-05-05

## What we set out to do

- Validate end-to-end architecture on AMD MI300X.
- Train lender-specific LoRA adapters.
- Serve base + multi-LoRA inference through vLLM on ROCm.
- Capture actionable DevEx findings for the hackathon.

## What worked

- Wallet setup and funding completed (dealer, marketplace, reserve, 5 lenders).
- LoRA training completed on MI300X; adapter outputs were produced for all 5 lenders.
- Adapter artifacts are distinct (hash-verified), confirming lender-specific training outputs.
- Direct inference with `transformers + peft` generated coherent, lender-differentiated outputs.

## What failed

- vLLM serving on the tested ROCm runtime is unstable for this workload:
  - `LoRA off + compiled`: clean output (pass).
  - `LoRA off + eager`: corrupted output (fail).
  - `LoRA on + compiled`: engine init crash (`ConstraintViolationError`) (fail).
  - `LoRA on + eager`: model starts but output is semantically corrupted (fail).

## Root cause (current best assessment)

- This is a serving/runtime issue in the tested AMD ROCm vLLM path, not an app-logic issue.
- LoRA as a method is sound; training and direct PEFT inference worked.

## Assets produced today

- `AMD_DEV_CLOUD_DEVEX_NOTES.md`
- `AMD_VLLM_ROCM_REPRO_MATRIX.md`
- `AMD_MI300X_VLLM_REPRO_BUNDLE.md`
- `AMD_DEV_CLOUD_BOOTSTRAP_COMMANDS.md`

## Practical decision

- Treat current vLLM+ROCm behavior as a platform limitation for this timeline.
- Proceed with stable AMD-backed demo path while preserving this evidence for moderators.
