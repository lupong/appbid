# Rest-of-Week Plan — AMD AI Focus (2026-05-07 to 2026-05-09)

This plan is scoped to AppBid's AI path only (lender LoRA training + inference on AMD MI300X) and excludes x402/payment work.

## Status update (as of 2026-05-06 EOD)

- Wednesday profiling evidence run completed with AppBid workload telemetry capture.
- Artifacts now available under `../../artifacts/profiling/` (CSV + charts + summary).
- Remaining items from this plan are Thursday/Friday objectives (Optimum-AMD path and AITER verification evidence).

## Wednesday — AMD profiling evidence (Omniperf / rocprof)

### Objective
Generate AMD-native performance evidence from AppBid concurrency runs that can be used directly in the hackathon deck.

### Workload
- Run the same multi-request inference/concurrency workload used in the AppBid lender-bid demo.
- Keep prompt mix and concurrency fixed so results are comparable across runs.

### Metrics to capture
- GPU utilization (%) over time
- Memory bandwidth (convert to TB/s where possible)
- Active compute unit proxy / occupancy counters
- Power draw and thermals

### Tools and outputs
- Primary profiler: `rocprof` (counter traces)
- Optional deep dive: `omniperf` (if available on image)
- Hardware telemetry: `rocm-smi`

### Deliverables
- `../../artifacts/profiling/wed_utilization.png`
- `../../artifacts/profiling/wed_bandwidth.png`
- `../../artifacts/profiling/wed_power_thermals.png`
- `../../artifacts/profiling/wed_raw_metrics.csv`

### Deck-ready line template
"Under concurrent AppBid lender-scoring load, MI300X sustained N% GPU utilization at M TB/s memory bandwidth while remaining inside a stable power/thermal envelope."

## Thursday — Optimum-AMD in the training loop

### Objective
Ensure Optimum-AMD is actively used by the LoRA training path (not only installed as a dependency).

### Implementation target
- Wire Optimum-AMD in the active training entrypoint (`lora_training/train_lora.py`) behind a clear runtime flag (example: `--amd-optimize`).
- Emit explicit log lines indicating Optimum-AMD path is enabled.

### Validation
- Run baseline training and Optimum-AMD-enabled training on the same dataset/config.
- Compare:
  - training throughput (samples/sec or tokens/sec)
  - average step time
  - stability and memory behavior

### Deliverables
- Short before/after findings in AMD docs
- Log snippets proving Optimum-AMD path executed

### Deck wording
"AMD-native optimization: Optimum-AMD enabled in our LoRA training loop for ROCm graph/kernal-level acceleration."

## Friday — Verify AITER in vLLM runtime logs

### Objective
Confirm vLLM on ROCm is selecting AMD transformer kernels (AITER) in startup/runtime logs without rebuilding.

### Steps
- Start the known serving path for AppBid inference.
- Capture startup logs and runtime config.
- Confirm AITER signature (for example `attention_backend=AITER` or equivalent AITER backend markers).

### Deliverables
- Add verification note in `../devex/AMD_VLLM_ROCM_REPRO_MATRIX.md`
- Keep a short log excerpt/screenshot for deck evidence

### Deck wording
"Serving path verified to use AMD AITER transformer kernels on MI300X."

## Stretch goals

1. **AMD model source check**
   - Quick due diligence on <https://huggingface.co/amd> for Qwen-family variants relevant to AppBid.
   - Document outcome as "found / not found / not suitable."

2. **ROCm Composable Kernel (CK) awareness**
   - Add a short note that CK is the lower-level fused-op layer under higher-level runtime kernels.
   - Mention this in troubleshooting context for kernel-availability issues.

## AppBid narrative guardrails

- Keep focus on lender-policy LoRAs, inference concurrency, and AMD-native optimization evidence.
- Use measurements from AppBid workload, not synthetic-only benchmarks, for final judge-facing claims.
