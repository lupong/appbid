# Today Recap — 2026-05-07

## AMD work completed today

- Ran and completed a 60-minute MI300X technical evaluation with AITER A/B and soak.
- Verified AITER runtime evidence in vLLM logs and quantified AITER ON/OFF deltas.
- Completed Optimum-AMD due diligence and benchmark harness work; documented runtime
  constraint that prevented claiming validated Optimum acceleration on this image.
- Implemented a simulated x402 payment mode (`PAYMENT_MODE=stub`) for product-shape
  E2E testing without chain spendability risk.
- Ran live smoke in simulated x402 + stub settlement mode and exposed UI/web access.

## Outcome (what passed)

- 60-minute eval finished with complete artifacts in
  `../../artifacts/profiling/60min_eval_20260507_163121/`.
- Quality guardrail: `20/20` structured JSON parses (`parse_success_rate=1.0`).
- Live product smoke: publish -> multi-bid -> accept -> settlement -> `E2E PASS`.
- Evidence bundle pulled to repo and indexed in
  `../../artifacts/profiling/README_THU_2026-05-07.md`.

## Performance and mode comparisons (AMD MI300X)

At equal settings (`c=4`), AITER ON outperformed AITER OFF:

- Req/s: `7.43` vs `6.58` (**+12.9%**)
- Completion tok/s: `327.87` vs `307.56` (**+6.6%**)
- p95 latency: `0.59s` vs `0.81s` (**27.2% lower**)
- max latency: `0.66s` vs `1.63s` (**59.5% lower**)

Soak operating point (AITER ON, `c=4`, 120 loops):

- `avg_req_per_s=7.38775`
- `avg_tok_per_s=326.9516`
- `avg_p95_s=0.58025`

Burst operating point (AITER ON, `c=8` short run):

- `21.42 req/s`
- `978.23 tok/s`
- `p95=0.49s`

## What this means for AppBid capacity (current measured envelope)

Assuming 5 lender agents evaluate each dealer app request:

- Sustained planning envelope from soak:
  - lender decisions: `7.38775 * 60 = ~443/min`
  - full 5-lender app evaluations: `~88.7 apps/min`
- Burst envelope from `c=8` sample:
  - lender decisions: `21.42 * 60 = ~1,285/min`
  - full 5-lender app evaluations: `~257 apps/min`

Business interpretation:

- Current runtime supports many simultaneous dealers relative to the demo load.
- The practical app-level throughput bound is inference decisions/sec and approval
  mix, not marketplace API overhead.
- AITER ON should remain default for both throughput and tail-latency control.

## AMD vs NVIDIA economics (current evidence-backed framing)

- Current MI300X planning reference in this project:
  - about `$1.99/GPU-hr` (same cloud provider context)
  - see `../plans/CLOUD_GPU_NVIDIA_AWS_COMPARISON_2026-05-06.md`
- Price-normalized break-even from that note:
  - DO H100 (`$3.39/hr`) needs about `1.70x` per-GPU throughput vs current MI300X point
  - DO H200 (`$3.44/hr`) needs about `1.73x`

Why MI300X looks strong for AppBid today:

- Single-GPU memory headroom and stable continuous batching on this workload shape.
- Measured AITER-enabled serving gives good req/s plus better tail latency.
- Cost point plus measured throughput produces favorable bids/min per `$` heuristics.

Important caveat:

- We did not run controlled apples-to-apples NVIDIA hardware benchmarks in this repo.
- Economic statements here are workload-local and price-normalized, not universal.

## Bad DevEx (and where AMD path falls short vs NVIDIA stack today)

- Recurrent SSH instability (`Connection refused` while droplet status remained active).
- Firewall defaults required manual inbound rule changes for app ports (`8501`, `8016`).
- Tooling friction:
  - `omniperf` unavailable on active image
  - `rocprof/rocprofv2` counter persistence inconsistent on this stack
- Python ecosystem friction on this image:
  - `optimum-amd` dependency constraints around `onnxruntime<1.16` and py3.12 wheels
- Operational overhead:
  - required low-pressure SSH command spacing to keep sessions reliable

Where NVIDIA ecosystems are typically stronger (today):

- Wider managed-cloud and wheel compatibility paths
- More mature one-click profiling/instrumentation UX
- Fewer ROCm-specific runtime caveats for common LLM tooling defaults

## Files/code touched today

- `scripts/run_60min_eval.sh` (summary extraction target fix)
- `shared/config.py` (`payment_mode`)
- `agents/runner.py` (`PAYMENT_MODE=stub` path)
- `.env.example` (document mode toggles)
- `README.md` and `../runbooks/DEMO_PATH_FRI_SAT.md` (simulated x402 run mode)

## Final status at day wrap

- AMD technical evaluation objective: completed with evidence.
- Product-shape E2E under demo-safe constraints: completed and reproducible.
- Remaining risk to call out transparently: cloud/GPU droplet DevEx reliability and
  live payment/settlement spendability constraints outside core inference performance.
