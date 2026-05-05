# Tomorrow Plan — AMD Quark FP8 (2026-05-06)

## Objective

Exploit AMD-specific hardware value on MI300X by quantizing `Qwen/Qwen2.5-72B-Instruct` from BF16 to FP8 using AMD Quark, then validate memory and throughput gains in a reproducible benchmark.

## Why this matters

- CDNA3/MI300X has native FP8 matrix acceleration.
- Expected impact:
  - significantly lower model memory footprint
  - materially higher effective concurrency (more KV cache room)
  - improved tokens/sec vs BF16 baseline

## Success criteria

- FP8 model artifact generated and loadable on MI300X.
- Side-by-side benchmark captured:
  - BF16 baseline vs FP8
  - p50/p95 latency
  - req/s or tok/s
  - memory footprint (VRAM used)
- Short findings block added to repo docs for moderators.

## Execution checklist

1. **Environment**
   - Use AMD-supported image/runtime for Quark workflow.
   - Record exact image tags and tool versions.

2. **Baseline capture (BF16)**
   - Run fixed prompt set and fixed concurrency values.
   - Capture VRAM, latency, throughput.

3. **FP8 quantization**
   - Quantize 72B model with Quark (document exact command/config).
   - Save artifact path and metadata.

4. **FP8 serve + benchmark**
   - Serve FP8 artifact on MI300X.
   - Re-run same benchmark harness as baseline.

5. **Compare and publish**
   - Add a concise BF16 vs FP8 comparison section to docs.
   - Note any quality regressions or serving caveats.

## Risks / decision gates

- If FP8 path is blocked by runtime/tooling incompatibility by midday:
  - stop digging
  - publish partial findings + blockers
  - revert to stable demo path for final submission reliability.

## Deliverables by EOD

- Updated docs with:
  - exact commands used
  - benchmark table
  - recommendation for hackathon narrative
- Ready-to-say one-liner:
  - “We validated AMD-specific FP8 leverage on MI300X with measured memory/perf gains.”
