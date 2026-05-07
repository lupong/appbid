# Cloud GPU Comparison Note (NVIDIA + AWS) — 2026-05-06

This note captures a quick market comparison against the measured AppBid AMD MI300X baseline from Day 3.

## AppBid measured baseline (current)

- Runtime path: AppBid on MI300X with FP8 serving path selected for stability.
- Sustained equivalent used for planning: ~`780 bids/min` (derived from ~`156 req/min` x `5 lenders`).
- Cost reference in current run context: ~`$1.99/GPU/hr` (MI300X x1 plan class used in execution).
- Cost efficiency reference point:
  - `780 / 1.99` ~= `392 bids/min per $/hr`

## NVIDIA options observed (cloud pages)

### DigitalOcean GPU catalog (NVIDIA entries)

- NVIDIA HGX H100 / H100x8
- NVIDIA HGX H200 / H200x8
- NVIDIA L40S
- NVIDIA RTX 4000 Ada
- NVIDIA RTX 6000 Ada
- NVIDIA HGX B300 / B300x8 (listed in product page rollout context)

### AWS EC2 families (NVIDIA paths)

- P-series: P4 (A100), P5 (H100), P5e/P5en (H200), P6 (Blackwell generation pages)
- G-series: G5 (A10G), G6 (L4), G6e (L40S), G4dn (T4)

## Price-only break-even math vs current MI300X baseline

Important: this section is a **price-normalized planning heuristic**, not a measured cross-hardware benchmark.

Using baseline `392 bids/min per $/hr`, required relative throughput to match economics:

- DO H100 (`$3.39/GPU/hr`): needs about `3.39 / 1.99` ~= **1.70x** per-GPU throughput vs current MI300X run.
- DO H200 (`$3.44/GPU/hr`): needs about `3.44 / 1.99` ~= **1.73x** per-GPU throughput.
- DO H100x8 (`$2.50/GPU/hr`, per-GPU): needs about `2.50 / 1.99` ~= **1.26x** per-GPU throughput.

Interpretation:

- If a candidate GPU does not deliver the needed multiplier above, MI300X remains ahead on this workload's current cost-efficiency point.
- If it exceeds the multiplier, it may be cost-competitive or better for this workload shape.

## Scope and caveats

- No controlled apples-to-apples benchmark has been run yet on AWS or NVIDIA hardware for AppBid.
- Measured values above are from current AppBid stack, model path, and prompt/concurrency shape.
- Region, purchase model (on-demand vs reserved/spot), and networking topology can materially shift economics.

## Source pages used

- DigitalOcean GPU pricing:
  - <https://www.digitalocean.com/pricing/gpu-droplets>
- DigitalOcean GPU product page:
  - <https://www.digitalocean.com/products/gradient/gpu-droplets>
- AWS accelerated computing overview:
  - <https://aws.amazon.com/ec2/instance-types/accelerated-computing/>
- AWS P5 page:
  - <https://aws.amazon.com/ec2/instance-types/p5/>
- AWS G6 page:
  - <https://aws.amazon.com/ec2/instance-types/g6/>

