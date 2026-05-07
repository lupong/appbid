# 60-Min Technical Evaluation Matrix (MI300X)

Goal: run one autonomous 60-minute evaluation pass with minimal SSH chatter and high GPU utilization.

## Scope

- Model: `Qwen/Qwen2.5-7B-Instruct` (evaluation speed / repeatability)
- Server: `vllm` in ROCm container on MI300X
- Primary comparison:
  - AITER ON (`VLLM_ROCM_USE_AITER=1`)
  - AITER OFF (`VLLM_ROCM_USE_AITER=0`)
- Secondary check:
  - `--amd-optimize` training path already assessed as runtime-constrained (not validated transform path).

## Test Blocks

1. **AITER ON startup + readiness**
   - Pass: `/v1/models` returns HTTP 200.

2. **Concurrency sweep (AITER ON)**
   - `c=1,2,4,8` at fixed request shape.
   - Capture: req/s, completion tok/s, p50/p95/max latency.
   - Pass: no request errors.

3. **AITER OFF A/B sample**
   - Single benchmark at `c=4` (same request shape).
   - Capture deltas vs AITER ON.
   - Pass: no request errors and measurable comparison output.

4. **Structured-output guardrail sample**
   - Fixed JSON prompt set (small sample).
   - Capture: parse-success rate.
   - Pass: parse success >= 95%.

5. **Soak phase (remaining time to 60 min)**
   - Repeated benchmark loops at selected operating point.
   - Capture per-loop throughput/latency and error count.
   - Pass: no sustained error trend; no catastrophic latency drift.

## Artifacts

All outputs stored under:

- `artifacts/profiling/60min_eval_<timestamp>/`

Expected files:

- `meta.json`
- `aiter_on_c*.log`
- `aiter_off_c4.log`
- `quality_guardrail.json`
- `soak_loop_*.log`
- `summary.json`

## Decision Rules

- Prefer config with:
  1. highest stable req/s and tok/s,
  2. controlled p95 latency,
  3. no quality regression in JSON parse success.
- If AITER ON materially outperforms AITER OFF at equal error profile, keep AITER ON as default eval/runtime setting.

## Run outcome (completed)

Run directory:

- `../../artifacts/profiling/60min_eval_20260507_163121/`

Result summary:

- Quality guardrail: `20/20` (`parse_success_rate=1.0`)
- AITER ON @ `c=4`: `7.43 req/s`, `327.87 tok/s`, `p95=0.59s`
- AITER OFF @ `c=4`: `6.58 req/s`, `307.56 tok/s`, `p95=0.81s`
- Soak aggregate (120 loops): `avg_req_per_s=7.38775`, `avg_tok_per_s=326.9516`

Interpretation:

- AITER ON outperformed AITER OFF on both throughput and tail latency at equal
  request shape in this run.
- Selected default remains AITER ON for AppBid MI300X runtime.
