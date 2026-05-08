# Build In Public — Day 5 Update (2026-05-08)

Day 5 AMD x lablab.ai developer hackathon. 2 days left.

validated AppBid on AMD MI300X with a strict 72B retest pass after prior 7B automation drift. we re-ran matched AITER ON/OFF comparisons on `Qwen2.5-72B` FP8 PTPC and captured fresh artifacts.

what worked on AMD MI300x (72B path):

- got Qwen2.5-72B running in the viable FP8 PTPC path on MI300X and revalidated AITER behavior with repeated matched runs.
- at `c=4`, AITER ON showed a modest win vs OFF (avg across repeats):
  - req/s: `2.73` vs `2.69` (`+1.5%`)
  - tok/s: `122.33` vs `118.97` (`+2.8%`)
  - p95: `1.56s` vs `1.75s` (`~10.9% lower`)
- AppBid remained demo-ready (simulated x402 + stub settlement path still passes E2E).
- evidence/artifacts are packaged in repo under `artifacts/profiling/72b_retest_tuned_20260508_101732`.

what didn't work:

- recurrent SSH/devcloud reliability issues (connection refused while droplet still reported active).
- some ROCm profiling tools (`omniperf`/`rocprofv2`) remained inconsistent on this image, so `rocm-smi` telemetry stayed the stable source.
- at higher concurrency (`c=8`), AITER ON regressed in this retest vs OFF, so AITER advantage is not universal and needs profile-specific tuning.
- Optimum-AMD runtime path was constrained by package/runtime compatibility on this image (could not claim validated transform acceleration).

next:

- lock serving profile by target concurrency band (`c=4` vs `c=8`) instead of one-size-fits-all AITER claims.
- capture clean hero demo footage showing AppBid concurrency + MI300X telemetry side-by-side.
- keep all performance statements strictly 72B-labeled and include transparent tradeoffs.

tagging:
AMD Developer lablab.ai

thread hashtag
#AppBidAMDHackathon2026

building in public with technical and devex notes here:

https://lnkd.in/epE3vB6y
