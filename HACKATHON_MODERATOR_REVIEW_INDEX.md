# Hackathon Moderator Review Index

This index points reviewers to the highest-signal project evidence from the current build cycle.

## Core project docs

- `README.md` — architecture, setup, and system behavior
- `CONTEXT.md` — design rationale and problem framing
- `HACKATHON_PLAN.md` — execution plan and milestones

## Today’s outcome and evidence

- `TODAY_2026-05-05_RECAP.md` — concise summary of wins, blockers, and decisions
- `AMD_DEV_CLOUD_DEVEX_NOTES.md` — chronological DevEx findings on AMD Developer Cloud
- `AMD_VLLM_ROCM_REPRO_MATRIX.md` — reproducible matrix for vLLM+ROCm behavior
- `AMD_MI300X_VLLM_REPRO_BUNDLE.md` — focused support-style repro notes
- `AMD_DEV_CLOUD_BOOTSTRAP_COMMANDS.md` — bootstrap command trail used on droplet

## Model/training related

- `lora_training/README.md` — LoRA pipeline design and execution
- `data/bid_policies.py` — lender policy profiles and LoRA alias mapping

## Build-in-public / forward plan

- `BUILD_IN_PUBLIC_POST_2026-05-05.md` — public-facing day summary draft
- `TOMORROW_PLAN_AMD_QUARK_FP8.md` — planned AMD Quark FP8 workstream

## Notes on scope and transparency

- Current limitation is isolated to the tested vLLM+ROCm serving path for this workload.
- LoRA training and direct PEFT inference were validated separately.
- Documentation in this repo intentionally includes both successful outcomes and blockers for transparent review.
