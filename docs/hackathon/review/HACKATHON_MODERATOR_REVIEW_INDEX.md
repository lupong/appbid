# Hackathon Moderator Review Index

This index points reviewers to the highest-signal project evidence from the current build cycle.

## Core project docs

- `../../README.md` — architecture, setup, and system behavior
- `../../CONTEXT.md` — design rationale and problem framing
- `../plans/HACKATHON_PLAN.md` — execution plan and milestones

## Today’s outcome and evidence

- `../recaps/TODAY_2026-05-05_RECAP.md` — concise summary of wins, blockers, and decisions
- `../recaps/TODAY_2026-05-06_RECAP.md` — FP8 quantization/serve outcomes, E2E decision path, and profiling capture
- `../recaps/TODAY_2026-05-07_RECAP.md` — 60-minute eval outcomes, AITER A/B deltas, capacity/economics framing, and DevEx gaps
- `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md` — chronological DevEx findings on AMD Developer Cloud
- `../devex/AMD_VLLM_ROCM_REPRO_MATRIX.md` — reproducible matrix for vLLM+ROCm behavior
- `../devex/AMD_60MIN_TECH_EVAL_MATRIX_2026-05-07.md` — 60-minute eval design + completed run interpretation
- `../devex/AMD_MI300X_VLLM_REPRO_BUNDLE.md` — focused support-style repro notes
- `../devex/AMD_DEV_CLOUD_BOOTSTRAP_COMMANDS.md` — bootstrap command trail used on droplet
- `../runbooks/DEMO_PATH_FRI_SAT.md` — canonical demo runbook for Friday/Saturday
- `../../artifacts/profiling/README_WED_2026-05-06.md` — profiling methodology and artifact index
- `../../artifacts/profiling/README_THU_2026-05-07.md` — Thursday technical evaluation and live smoke evidence index

## Model/training related

- `../../lora_training/README.md` — LoRA pipeline design and execution
- `../../data/bid_policies.py` — lender policy profiles and LoRA alias mapping

## Build-in-public / forward plan

- `../public/BUILD_IN_PUBLIC_POST_2026-05-05.md` — public-facing day summary draft
- `../plans/HACKATHON_PLAN.md` — integrated execution timeline (includes May 6 FP8 objective snapshot)
- `../plans/REST_OF_WEEK_AMD_AI_PLAN_2026-05-07_to_2026-05-09.md` — Wed-Fri AI-focused AMD execution plan (profiling, Optimum-AMD, AITER)

## Notes on scope and transparency

- Current limitation is isolated to the tested vLLM+ROCm serving path for this workload.
- LoRA training and direct PEFT inference were validated separately.
- Documentation in this repo intentionally includes both successful outcomes and blockers for transparent review.
