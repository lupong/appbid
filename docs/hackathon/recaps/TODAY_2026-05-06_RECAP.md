# Today Recap — 2026-05-06

## What we set out to do

- Validate AMD-specific FP8 value on MI300X for AppBid inference.
- Keep end-to-end demo reliability while preserving transparent blocker reporting.
- Capture judge-ready evidence (performance, quality, stability, and profiling artifacts).

## What worked

- Quark FP8 quantization path landed for Qwen2.5 variants; PTPC FP8 proved the viable serving configuration on this stack.
- 72B FP8 model served on MI300X and outperformed BF16 in measured benchmark runs.
- Quality guardrail set showed parity trend vs BF16 for structured underwriting output.
- Extended stability soak completed with zero request failures on selected operating point.
- Mini E2E achieved full pass in demo-safe mode with:
  - `INSERTION_FEE_USDC=0`
  - `SETTLEMENT_MODE=stub`
- Wednesday profiling evidence was captured and stored under `../../artifacts/profiling/`.

## What blocked live path

- Live x402/CDP settlement remained constrained by wallet spendability/faucet limits.
- Even micro transfer probes from marketplace wallet failed with `Insufficient balance to execute the transaction`.
- This is documented as an external integration/runtime constraint, not an FP8 model-quality issue.

## Decisions made

- Keep a reliable canonical demo path for Friday/Saturday in `../runbooks/DEMO_PATH_FRI_SAT.md`.
- Preserve live settlement codepath (`SETTLEMENT_MODE=live`) and expose stub mode as an explicit runtime switch for controlled demo reliability.
- Prioritize evidence packaging and submission readiness over further payment-path churn today.

## Deliverables produced today

- Code/runtime:
  - `marketplace/x402_middleware.py` (true zero-fee bypass)
  - `shared/config.py` (`settlement_mode`)
  - `marketplace/settler.py` (live vs stub executor selection)
  - `scripts/e2e_test.py` (`E2E_LOAN_AMOUNT` override)
- Docs:
  - `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md` (full chronology)
  - `../runbooks/DEMO_PATH_FRI_SAT.md` (canonical demo runbook)
  - `../../artifacts/profiling/README_WED_2026-05-06.md`
- Artifacts:
  - `../../artifacts/profiling/wed_raw_metrics.csv`
  - `../../artifacts/profiling/wed_utilization.png`
  - `../../artifacts/profiling/wed_bandwidth.png`
  - `../../artifacts/profiling/wed_power_thermals.png`
  - `../../artifacts/profiling/wed_summary.json`
  - `../../artifacts/profiling/wed_concurrency_demo.log`

## Practical status at wrap-up

- FP8 value proposition: validated.
- Demo reliability path: validated.
- Outstanding external risk: live CDP settlement spendability on current project/faucet conditions.

## Historical note (migration of `TOMORROW_PLAN_AMD_QUARK_FP8.md`)

The standalone May 6 FP8 execution plan has been integrated into:

- `../plans/HACKATHON_PLAN.md` (objectives, success criteria, and gate logic)
- `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md` (actual run chronology and outcomes)

This recap is the concise source of truth for what was completed on 2026-05-06.
