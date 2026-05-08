# AMD Developer Cloud DevEx Notes

Purpose: running feedback log during the hackathon for AMD Developer Cloud
experience, friction points, and improvement ideas.

## Timeline

### 2026-05-05 09:40 (local)
- Created MI300X droplet flow and selected GPU/image options.
- Added SSH key in provider UI for droplet access.
- Initial impression: setup flow is straightforward, but there are multiple
  decision points (plan, image version, SSH key path) where concise
  recommendations/help text could reduce hesitation for first-time users.

### 2026-05-05 09:41 (local)
- Received security banner on droplet creation indicating image packages may
  be out of date and recommending immediate system update + reboot.
- Potential DevEx friction: uncertainty about whether upgrading system
  packages can destabilize pre-tuned ROCm/vLLM image dependencies.
- Suggested improvement: provide AMD-validated update guidance per image
  (safe package update scope, packages to avoid upgrading, and a one-command
  "secure baseline" script).

### 2026-05-05 09:42 (local)
- Droplet provisioning completed.
- Feedback: prebuilt GPU images would ideally be security-patched/up-to-date
  at droplet creation time to avoid immediate maintenance uncertainty.
- Connection details captured in local project `.env` for repeatable setup.

### 2026-05-05 09:44-09:46 (local)
- Connected successfully over SSH using dedicated droplet key.
- Applied package updates + rebooted per security warning.
- Post-reboot validation succeeded:
  - Docker available
  - ROCm SMI reports MI300X VF with ~192 GB VRAM
- DevEx feedback: despite successful flow, requiring immediate `apt upgrade`
  on first boot can create uncertainty around image stability for time-boxed
  hackathon usage.

### 2026-05-05 09:49-09:58 (local)
- Ran project bootstrap on the MI300X droplet.
- First blocker: `python3 -m venv .venv` failed because `python3.12-venv` was
  not preinstalled.
  - Resolved with `apt-get install -y python3.12-venv`.
- Second blocker: `infra/devcloud.sh doctor` failed hard because host venv did
  not include `torch` on this vLLM-focused image.
  - Resolved by making doctor warn/continue when `scripts/check_gpu.py` fails
    but `rocm-smi` already confirms GPU visibility.
- Third blocker: `infra/devcloud.sh serve dev` failed because `vllm` was not on
  host PATH (available only via preloaded Docker image).
  - Resolved by adding Docker fallback in `devcloud.sh` that uses
    `vllm/vllm-openai-rocm:v0.17.1`.
- Fourth blocker: start script required LoRA adapters even for first bootstrap.
  - Resolved by adding `VLLM_ENABLE_LORA=0` path in `start_vllm.sh` for
    base-model serve during initial bring-up.
- Current hard blocker: vLLM still exits with `RuntimeError: No HIP GPUs are available`
  during engine init, even though container-level torch check reports
  `torch.cuda.is_available() == True` and `device_count == 1`.
  - This suggests an image/runtime mismatch or launch nuance specific to this
    droplet flavor that needs AMD-side guidance.

### 2026-05-05 10:00-10:06 (local)
- Follow-up revealed an additional bootstrap issue: Docker serve path did not
  publish the API port to host, so local benchmark/health checks could not
  reach vLLM.
  - Resolved by mapping `-p ${VLLM_PORT}:${VLLM_PORT}` in docker fallback.
- After relaunch with published port, vLLM progressed significantly further:
  model downloads and loads, but API readiness still did not complete within
  5+ minutes.
- Latest observed hang point is AITER kernel build:
  `start build [module_rmsnorm]` with no subsequent completion line.
- Created an AMD support repro bundle with exact commands, environment, and log
  evidence: `AMD_MI300X_VLLM_REPRO_BUNDLE.md`.

### 2026-05-05 10:21 (local)
- Critical hackathon blocker for automation: generating a DigitalOcean PAT
  requires adding a payment method on the account.
- This conflicts with hackathon flow expectations where participants are given
  fixed AMD credits and may intentionally avoid attaching a payment method.
- Practical impact: developers are forced back to manual UI provisioning and
  cannot reliably script droplet lifecycle (create/teardown/retry) during
  rapid debugging.

### 2026-05-05 10:24-10:27 (local)
- PAT auth was confirmed working and API lifecycle automation was tested end-to-end.
- Existing MI300X droplet was successfully deleted via API, but replacement
  creation failed across attempted regions with capacity/availability errors:
  - `This size is unavailable.`
  - `Size is not available in this region.`
- Resulting risk during hackathon: automated recovery can leave teams with zero
  active GPU droplets if capacity is not immediately available after teardown.
- DevEx recommendation: provide a "capacity guard" flow in UI/API (reserve
  replacement before delete, or atomic replace operation) for scarce GPU SKUs.

### 2026-05-05 10:57-11:03 (local)
- New ROCm7 (`amd-vllmrocm7`) MI300X droplet was created and reported `active`
  via API with public IP assigned.
- Initial SSH access succeeded, then repeated attempts returned
  `Connection refused` despite no reboot/action events in API.
- Practical impact: automation can stall even when control-plane status is
  `active`; users need console-based fallback guidance to recover SSH quickly.

### 2026-05-05 11:51-13:27 (local) — LoRA training run feedback (good + bad)
- **What worked well**
  - End-to-end LoRA training on MI300X completed for all 5 lenders with strong
    GPU utilization (observed ~88-92% during training).
  - Real teacher-data generation against local vLLM was straightforward once the
    endpoint was healthy; larger datasets were generated successfully.
  - Adapter artifacts were produced and verified as unique (different hash per
    lender adapter), so lender-specific training outputs were preserved.
  - Running training inside the ROCm7 container avoided host-level dependency
    drift and gave predictable torch+ROCm behavior.
- **What was confusing or slow**
  - Installing unpinned training dependencies on host venv pulled CUDA-oriented
    `torch` wheels (`torch==2.11.0` + CUDA deps), which is misleading on AMD
    and wastes time/bandwidth before realizing it is the wrong runtime path.
  - The ROCm7 vLLM container uses Python 3.10, while project metadata requires
    `>=3.11`; `pip install -e .` failed in-container, forcing manual/minimal
    dependency installation as a workaround.
  - vLLM + LoRA serving stability was inconsistent after training:
    - startup required extra stabilization flags (`--enforce-eager`,
      lower `max-num-seqs`, lower `max-model-len`) to avoid engine-init issues.
    - with some settings, engine init failed with dynamic-shape
      `ConstraintViolationError`.
    - when it did start, some responses were malformed/garbled JSON, preventing
      reliable side-by-side lender behavior validation.
  - SSH availability was intermittent during active debugging; multiple periods
    of `Connection refused`/timeouts required API power-cycle/reboot despite
    droplet status remaining `active`.
- **Practical impact**
  - Teams can get to trained adapters on MI300X, but serving-validation loops
    can become fragile and expensive because instability appears late (after
    lengthy training and model load steps).

### 2026-05-05 13:40-13:50 (local) — Root-cause clarification from live validation
- **Summary finding:** the primary blocker is **ROCm vLLM serving correctness** on
  this image/runtime, not application logic and not LoRA training artifact
  generation.
- **Evidence observed**
  - vLLM server starts, base model loads, and all 5 LoRA adapters register.
  - `/v1/chat/completions` returns malformed/garbled text (including simple
    prompts), causing JSON parse failures in the underwriter path.
  - In compiled mode, engine init can fail with dynamic-shape
    `ConstraintViolationError`; eager mode improves startup stability but does
    not eliminate corrupted output generation.
  - Direct `transformers + peft` inference (bypassing vLLM serving) produces
    coherent lender-differentiated outputs from the same adapters, which
    isolates the issue to the serving/runtime layer.
- **Hackathon impact**
  - Teams may falsely attribute failures to app code or training quality when
    the root issue is runtime serving correctness; this can consume hours of
    debugging and credit spend.
- Follow-up artifact with reproducible case matrix:
  - `AMD_VLLM_ROCM_REPRO_MATRIX.md`

### 2026-05-05 17:23 (local) — Lablab.ai community DevEx (reporting channel friction)
- While posting in the Lablab.ai Discord to ask where AMD Developer Cloud /
  ROCm runtime issues should be reported (DigitalOcean ticket vs alternate
  channel), the message was blocked by server content filters.
- User-facing error shown by Discord:
  - "This can't be posted because it contains content blocked by this server."
  - "Only you can see this."
- Practical impact:
  - blocks timely escalation path discovery during a time-boxed hackathon.
  - creates uncertainty on the correct support/reporting channel for platform
    runtime issues found during builds.
- Suggested improvement for Lablab organizers/moderators:
  - pin a clear "Where to report infra/runtime issues" message per partner
    track (AMD, cloud provider, SDK/tooling).
  - ensure filter rules do not block standard support-routing questions.

### 2026-05-05 17:30+ (local) — Support escalation tracking
- DigitalOcean support ticket submitted for AMD single-node MI300X runtime
  instability findings.
- **Ticket number:** `#12151413`
- Scope captured in ticket:
  - vLLM + ROCm mode matrix (LoRA on/off x eager/compiled)
  - compiled+LoRA `ConstraintViolationError`
  - eager-mode output corruption signatures

### 2026-05-05 20:32 (local) — Support response received (DO/AMD path)
- Support acknowledged report quality and confirmed preliminary alignment with
  our diagnosis: issue appears in `vLLM + ROCm` serving path, not training,
  adapter generation, or app business logic.
- Specific failure classes they called out:
  - dynamic shape handling issue in compiled mode with LoRA (`ConstraintViolationError`)
  - incorrect inference behavior/output corruption in eager mode
- They escalated to engineering and stated there is currently no confirmed
  stable config for:
  - multi-LoRA serving on MI300X via vLLM
  - consistent structured JSON output under ROCm
- Requested/possible next artifacts:
  - full command lines per test case
  - complete logs for failing scenarios

### 2026-05-06 08:18 (local) — MI300X capacity exhaustion (portal + API)
- Attempted to create a fresh MI300X single-GPU droplet for hackathon work.
- UI banner reported:
  - "We're out of GPU's right now... GPU resources are at full capacity."
- Reproduced the same issue via API create call with explicit config:
  - region: `atl1`
  - size: `gpu-mi300x1-192gb`
  - image: `221160341` (vLLM 0.17.1 / ROCm 7.2 quick-start image)
  - result: HTTP `422` with `Size is not available in this region.`
- Practical impact:
  - blocks immediate execution even with remaining AMD credits.
  - prevents reliable time-boxed iteration during hackathon windows.
- Suggested improvement:
  - expose real-time per-size regional capacity hints and queue/waitlist flow.
  - support automatic "create when capacity available" reservations for scarce GPU SKUs.

### 2026-05-06 08:30 (local) — Snapshot restore path: UI works, API rebuild path blocked
- Observed behavior difference between control-plane paths:
  - API `rebuild` to snapshot returned validation error requiring SSH key.
  - UI allows creating a new GPU droplet directly from the same snapshot.
- Decision/workaround:
  - destroy the transient newly-created droplet and recreate from snapshot via UI.
- DevEx takeaway:
  - parity gap between API rebuild validation and UI create-from-snapshot flow can
    mislead users into thinking the snapshot is invalid when it is actually usable.
  - docs should explicitly recommend "create new droplet from snapshot" as first
    fallback when in-place rebuild fails with SSH-key/root-password validation.

### 2026-05-06 09:20-09:24 (local) — Lender-specific fallback validated + BF16 baseline captured
- Confirmed lender-specific inference works on MI300X by running all 5 adapters via
  `transformers + peft` (bypassing vLLM LoRA serving path).
- Same bid request produced distinct lender outputs across:
  - `stcu_retail_auto`
  - `unitus_community_cu`
  - `exeter_finance`
  - `family_savings_cu`
  - `crouse_federal_cu`
- This validates that lender-policy artifacts are usable; blocker remains in
  vLLM multi-LoRA serving correctness on ROCm.
- Captured fresh BF16 baseline on snapshot droplet (`Qwen/Qwen2.5-7B-Instruct`,
  vLLM container `rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915`):
  - requests: `40`, concurrency: `4`, max_tokens: `128`
  - req/s: `7.04`
  - completion tok/s: `330.22`
  - latency: `p50=0.57s`, `p95=0.58s`, `max=0.59s`
  - peak VRAM used: `186745118720` bytes
  - peak GPU use: `99%`
- Baseline artifact saved on droplet: `/root/appbid/bf16-baseline.txt`.
- Quark readiness check on this droplet:
  - `quark` CLI not installed (`command not found`)
  - Python `quark` module not installed
- Immediate implication: FP8 phase needs Quark install/runtime provisioning before
  quantization can start.

### 2026-05-06 09:25-09:40 (local) — Quark FP8 quantization succeeded; vLLM load failed
- Implemented Quark quantization runner script:
  - `scripts/run_quark_fp8_quant.py`
- On restored snapshot droplet, copied the script to `/root/appbid/scripts/` before
  execution (snapshot did not include latest local file additions).
- Ran Quark FP8 quantization in ROCm container for `Qwen/Qwen2.5-7B-Instruct` with
  `LLMTemplate.get("qwen2").get_config(scheme="fp8", kv_cache_scheme="fp8")`.
- Quantization completed successfully (`QUANT_DONE`) and artifact was generated:
  - source path: `/root/appbid/models/qwen2.5-7b`
  - fp8 path: `/root/appbid/models/qwen2.5-7b-fp8`
  - source safetensor size: `15231271888` bytes
  - fp8 safetensor size: `8706004648` bytes
  - observed size reduction: ~`42.8%`
- Attempted to serve Quark FP8 artifact with vLLM (`v0.10.1 ROCm7 image`) on port `8002`.
- vLLM engine initialization failed with Quark config compatibility error:
  - `ValueError: Found a different quantization configuration for ['q_proj', 'k_proj', 'v_proj'] ... vLLM requires all to use the same scheme.`
- Practical impact:
  - quantization step itself is validated and reproducible.
  - serving step remains blocked by vLLM/Quark config compatibility (runtime integration issue).

### 2026-05-06 09:44-09:58 (local) — Quark/vLLM compatibility iteration: serve recovered, quality/perf regressed
- Iterated on Quark config to align with vLLM loader constraints:
  - added `attention_scheme=\"fp8\"` so `q_proj/k_proj/v_proj` share a uniform scheme.
  - added `--disable-output-tensors` path to strip `output_tensors` quantization from
    exported config (vLLM error: unsupported when output_tensors are quantized).
- Produced compatibility-focused FP8 artifact:
  - `/root/appbid/models/qwen2.5-7b-fp8-vllm`
- vLLM serving with this artifact succeeded on port `8002` (`/v1/models` ready).
- Benchmark run (same shape as BF16 baseline: requests=40, concurrency=4, max_tokens=128):
  - req/s: `0.77` (vs BF16 `7.04`)
  - completion tok/s: `98.19` (vs BF16 `330.22`)
  - latency: `p50=0.78s`, `p95=44.85s`, `max=44.85s` (heavy tail regression)
  - peak VRAM: `186222710784` bytes (roughly similar to BF16 path)
  - peak GPU use: `99%`
- Output quality sanity probe indicated severe degeneration:
  - prompt: "Say hello in one short sentence."
  - output: repeated punctuation (`!!!!!!!!!!!!!!!!...`) until token limit.
  - finish reason: `length`.
- Practical impact:
  - integration compatibility work can make the model load in vLLM, but quality and
    latency behavior are currently unacceptable for product use.
  - current FP8 path on this stack is not submission-safe without further tuning or
    different runtime/version combinations.

### 2026-05-06 10:10-10:14 (local) — PTPC FP8 variant recovered both quality and performance
- Continued Quark/vLLM iteration using `ptpc_fp8` scheme with compatibility flags:
  - `attention_scheme=fp8`
  - output_tensors disabled in exported config
- Generated artifact:
  - `/root/appbid/models/qwen2.5-7b-ptpc-fp8-vllm`
- vLLM serve succeeded on port `8002`.
- Sanity output quality recovered for simple prompt:
  - prompt: "Say hello in one short sentence."
  - response: `"Hello!"` (clean stop, no punctuation degeneration)
- Benchmark run (same shape as BF16 baseline: requests=40, concurrency=4, max_tokens=128):
  - req/s: `11.15` (BF16 baseline `7.04`)
  - completion tok/s: `454.26` (BF16 baseline `330.22`)
  - latency: `p50=0.28s`, `p95=0.77s`, `max=0.79s`
  - peak VRAM: `186454175744` bytes
  - peak GPU use: `99%`
- Practical impact:
  - there is at least one Quark config variant on this stack that is both serveable
    and materially faster than BF16 for this benchmark shape.
  - this converts FP8 from a hard blocker to a tunable integration path.

### 2026-05-06 10:15+ (local) — 72B PTPC FP8 run initiated
- Started long-running quantization job targeting original plan model:
  - repo: `Qwen/Qwen2.5-72B-Instruct`
  - scheme: `ptpc_fp8`
  - compatibility flags:
    - `attention_scheme=fp8`
    - output_tensors disabled
  - output target: `/root/appbid/models/qwen2.5-72b-ptpc-fp8-vllm`
- Initial smoke check:
  - container is running (`appbid-quark-fp8`)
  - quant log created: `/root/appbid/quark-72b-ptpc-fp8-vllm-quant.log`
- This run is expected to take significantly longer due to model size and first-time
  artifact download/processing.

### 2026-05-06 10:20+ (local) — 72B PTPC FP8 quantization completed and model served
- 72B Quark run completed successfully:
  - `QUANT_DONE repo=Qwen/Qwen2.5-72B-Instruct`
  - output: `/root/appbid/models/qwen2.5-72b-ptpc-fp8-vllm`
- Artifact footprint:
  - source safetensors total: `145412519312` bytes
  - FP8 safetensors total: `75213650328` bytes
  - reduction: ~`48.3%`
- Started vLLM server for 72B FP8 artifact on port `8003` and reached ready state:
  - model listed as `/app/models/qwen2.5-72b-ptpc-fp8-vllm`
- Sanity chat probe:
  - prompt: "Say hello in one short sentence."
  - response: `"Hello!"`
  - finish reason: `stop`
  - first-response latency observed: ~`42.9s` (cold path / heavyweight model startup context)

### 2026-05-06 10:24-10:27 (local) — 72B BF16 vs PTPC-FP8 benchmark comparison captured
- Ran matched benchmark shape for both 72B servers:
  - requests: `20`
  - concurrency: `2`
  - max_tokens: `128`
- **72B PTPC-FP8** (`/app/models/qwen2.5-72b-ptpc-fp8-vllm`, port 8003):
  - req/s: `1.37`
  - completion tok/s: `63.72`
  - latency: `p50=1.43s`, `p95=1.68s`, `max=1.68s`
  - peak VRAM: `184604708864` bytes
- **72B BF16** (`/app/models/qwen2.5-72b`, port 8004):
  - req/s: `0.31`
  - completion tok/s: `14.76`
  - latency: `p50=2.08s`, `p95=45.48s`, `max=45.51s`
  - peak VRAM: `184800964608` bytes
- Observed deltas (FP8 vs BF16 on this run shape):
  - req/s: ~`4.4x` higher
  - completion tok/s: ~`4.3x` higher
  - p95 latency: ~`27x` lower
  - VRAM usage: roughly similar under current server memory-utilization settings
- Artifacts saved:
  - `/root/appbid/fp8-72b-baseline.txt`
  - `/root/appbid/bf16-72b-baseline.txt`

### 2026-05-06 10:32-10:39 (local) — 72B quality guardrail set (BF16 vs FP8)
- Executed identical 20-case deterministic AppBid-style underwriting JSON probes
  against:
  - BF16 endpoint: `http://127.0.0.1:8004/v1`
  - PTPC-FP8 endpoint: `http://127.0.0.1:8003/v1`
- Validation checks per response:
  - HTTP success
  - JSON parse success
  - required-key completeness (`decision`, `apr_bps`, `term_months`, `max_amount_usdc`,
    `max_ltv_bps`, `cash_down_required_usdc`, `dealer_reserve_bps`, `stipulations`,
    `confidence`, `rationale`)
- Results:
  - BF16: `20/20` HTTP, `19/20` parse+keys pass
  - FP8: `20/20` HTTP, `19/20` parse+keys pass
  - both had the same single failing case index (`11`) with truncated JSON-style
    output (parse failure), suggesting prompt/response-length edge behavior rather
    than FP8-specific corruption.
- Latency observations on this guardrail set:
  - BF16 p50/p95: `8.677s / 9.192s`
  - FP8 p50/p95: `5.626s / 6.388s`
  - warm-only (excluding first request) speedup:
    - p50: ~`1.52x` better on FP8
    - p95: ~`1.47x` better on FP8
  - FP8 had a large first-request cold spike (`~52.2s`), after which latency settled.
- Artifacts saved:
  - `/root/appbid/quality-bf16-72b.json`
  - `/root/appbid/quality-fp8-72b.json`

### 2026-05-06 10:51-10:56 (local) — 72B concurrency sweep (operating-point selection)
- Ran matched concurrency sweep for both 72B endpoints with:
  - requests: `20`
  - max_tokens: `128`
  - concurrencies tested: `1`, `2`, `4`
- **72B PTPC-FP8** (`/app/models/qwen2.5-72b-ptpc-fp8-vllm`, `:8003`):
  - c=1: req/s `0.74`, tok/s `34.21`, latency p50/p95 `1.46/1.46`
  - c=2: req/s `1.39`, tok/s `65.24`, latency p50/p95 `1.43/1.54`
  - c=4: req/s `2.46`, tok/s `121.76`, latency p50/p95 `1.56/1.81`
- **72B BF16** (`/app/models/qwen2.5-72b`, `:8004`):
  - c=1: req/s `0.24`, tok/s `11.41`, latency p50/p95 `1.97/2.15` (max spike `44.80`)
  - c=2: req/s `0.97`, tok/s `45.53`, latency p50/p95 `2.06/2.09`
  - c=4: req/s `1.29`, tok/s `61.18`, latency p50/p95 `3.05/3.23`
- Recommended operating point from this sweep:
  - `concurrency=4` for both variants (best throughput in this tested range)
  - FP8 retains latency advantage and provides best throughput at c=4.
- Best-point FP8 vs BF16 deltas (both at c=4):
  - req/s: ~`1.91x` higher (`2.46` vs `1.29`)
  - tok/s: ~`1.99x` higher (`121.76` vs `61.18`)
- Artifacts saved:
  - `/root/appbid/sweep-fp8-72b.json`
  - `/root/appbid/sweep-bf16-72b.json`

### 2026-05-06 10:57-11:00 (local) — FP8 runtime activation + integration smoke + short soak
- Activated FP8 as active runtime and verified endpoint readiness:
  - `http://127.0.0.1:8003/v1`
  - model: `/app/models/qwen2.5-72b-ptpc-fp8-vllm`
- Underwriter integration smoke (real `agents.underwriter.Underwriter` with
  `LORA_MODE=prompt`) succeeded against FP8 endpoint:
  - produced valid `Decision` payload with expected fields and coherent rationale.
- Short soak run at selected operating point (`concurrency=4`):
  - requests: `120`
  - result: `ok=120`, `err=0`
  - req/s: `2.59`
  - completion tok/s: `125.57`
  - latency: `p50=1.52s`, `p95=1.82s`, `max=2.06s`
  - peak VRAM: `184604729344` bytes
  - peak GPU use: `100%`
- Artifact saved:
  - `/root/appbid/soak-fp8-72b-c4.txt`

### 2026-05-06 11:09-11:41 (local) — Extended FP8 stability soak (concurrency 4)
- Ran sustained FP8 load test at selected operating point:
  - endpoint: `http://127.0.0.1:8003/v1`
  - model: `/app/models/qwen2.5-72b-ptpc-fp8-vllm`
  - requests: `5000`
  - concurrency: `4`
  - max_tokens: `128`
- Soak duration:
  - wall time: `1916.92s` (~31.95 minutes)
  - measured elapsed (driver): `1917.84s`
- Outcome:
  - success: `ok=5000`, `err=0` (no request failures)
  - req/s: `2.61`
  - completion tok/s: `126.37`
  - latency: `p50=1.52s`, `p95=1.77s`, `max=2.08s`
- Resource stability:
  - peak VRAM: `184604729344` bytes
  - peak GPU use: `100%`
  - periodic status sampling showed stable peak values throughout the run window.
- Artifact saved:
  - `/root/appbid/soak-fp8-72b-c4-long.txt`

### 2026-05-06 11:58-12:00 (local) — Mini AppBid E2E on FP8 blocked at x402 payment layer
- Started marketplace + lender runner against active FP8 endpoint and executed
  `scripts/e2e_test.py`.
- E2E request publication succeeded, but no bids landed within timeout (`0` bids
  after `60s`).
- Runner logs confirm underwriting is healthy (decisions generated), but bid submit
  fails at insertion-fee payment step:
  - marketplace response on bid post: `HTTP 402 Payment Required`
  - CDP payment error: invalid EVM address in `address` path parameter
    (`must be a valid EVM hex address`).
- Practical impact:
  - model serving/runtime path is healthy.
  - full AppBid e2e currently blocked by x402/CDP payment-address configuration,
    which is separate from FP8 model performance/quality behavior.

### 2026-05-06 12:02-12:04 (local) — E2E retry with insertion-fee override still blocked
- Retried E2E after restarting marketplace with `INSERTION_FEE_USDC=0` to test
  whether bid insertion payment requirement could be bypassed.
- Outcome remained blocked (`0` bids in timeout window) with runner logs showing:
  - bid submission still receives `HTTP 402 Payment Required`
  - x402/CDP payment call still fails with invalid EVM address parameter.
- Conclusion:
  - payment address configuration/path issue is still active even with insertion
    fee override; requires dedicated x402/CDP config fix for full e2e pass.

## Documentation Gaps (DevEx)

- **Security notice ambiguity:** Docs should clarify whether full `apt upgrade`
  is recommended/safe for prebuilt ROCm images, and explicitly call out any
  packages users should avoid upgrading (kernel/driver/ROCm stack guidance).
- **Image version selection guidance:** Need a short decision tree for choosing
  vLLM image versions (latest vs pinned fallback) and when to prefer PyTorch.
- **First-boot checklist:** A single canonical "first 10 minutes" section
  would reduce context switching (SSH key setup, connect, patch, reboot, GPU
  check, Docker check, project bootstrap).
- **Validation expectations:** Docs should provide expected outputs for
  `rocm-smi` and quick health checks so users can quickly tell if setup is
  healthy.
- **Facilitator/network clarity for x402:** A concise note on local vs remote
  facilitator modes and when each is appropriate would help avoid confusion.
- **Hackathon-focused quickstart:** A time-boxed path (fastest route to demo)
  should be separate from full production-style setup.
- **Missing base Python packaging prerequisite:** Add `python3-venv` (or image
  equivalent) to GPU image defaults so Python projects can bootstrap without
  manual apt installs.
- **vLLM launch contract ambiguity:** Clarify whether vLLM should run from host
  binary or Docker only, and provide one canonical command for MI300X VF.
- **Container GPU passthrough troubleshooting:** Add a short "HIP GPUs are not
  available" troubleshooting section with known-good Docker flags and expected
  validation commands.
- **Hackathon automation blocked by billing prerequisite:** If PAT creation
  requires a payment method, hackathon users with credits-only workflows cannot
  use API/CLI automation. Provide a hackathon-safe token issuance path that
  works without requiring card setup.
- **No safe replace workflow for scarce GPU SKUs:** API/UI should support
  create-before-delete or one-click replacement to prevent accidental downtime
  when MI300X capacity is constrained.
- **AMD-oriented Python training baseline missing:** provide a recommended,
  pinned `requirements-train-amd.txt` (or image-level defaults) to prevent
  accidental CUDA wheel installs on AMD droplets.
- **Python-version mismatch across official images:** document Python version per
  image clearly and align hackathon starter templates to the image runtime so
  `pip install -e .` works out of the box.
- **vLLM LoRA stability guidance for ROCm7:** add a known-good MI300X config
  matrix (e.g., eager vs compiled mode, `max-num-seqs`, `max-model-len`) plus
  explicit failure signatures and remediations.
- **Control-plane vs data-plane health gap:** when droplet is `active` but SSH
  is unavailable, docs/UI should provide a first-class "recover SSH" runbook
  (console access, expected wait windows, and safe reboot sequence).
- **Critical diagnostic gap:** publish an AMD-supported vLLM validation matrix
  per image (known-good model sizes, LoRA on/off, eager vs compiled mode, and
  expected output sanity checks) so users can quickly separate app bugs from
  serving-runtime issues.
- **Quark-to-vLLM integration gap:** document known-good Quark FP8 export configs
  that are compatible with vLLM loader expectations (especially QKV merged-layer
  scheme constraints for models like Qwen2) and provide a canonical end-to-end
  "quantize then serve" recipe per image version.

### 2026-05-06 12:58-13:08 (local) — x402 root-cause shift: invalid payTo -> insufficient balance
- Re-ran mini AppBid E2E with an isolated marketplace/runner pair and captured
  detailed runner logs.
- Confirmed previous `invalid EVM hex address` failure was due to paywall `payTo`
  resolving to a placeholder fallback when wallet env was not set.
- After restarting marketplace with a valid `MARKETPLACE_WALLET_ID`, the failure
  mode shifted from address validation to:
  - `ApiError(... error_message=Insufficient balance to execute the transaction.)`
- This isolated the remaining blocker to wallet funding/settlement economics,
  not x402 address formatting.

### 2026-05-06 13:08-13:10 (local) — funded all wallets via CDP faucet
- Ran `scripts/fund_wallets.py` against all wallets in `wallets.json`
  (dealer/marketplace/reserve + 5 lenders).
- Faucet requests succeeded for all 8 wallets and returned tx hashes.
- Payment attempts still reported insufficient balance for insertion-fee transfers,
  indicating faucet amount and/or spendable timing remained insufficient for the
  configured fee/retry window.

### 2026-05-06 13:10-13:12 (local) — middleware fix: true zero-fee bypass
- Implemented a small middleware fix so `INSERTION_FEE_USDC=0` **actually bypasses**
  x402 gating for bid submission instead of still returning HTTP 402.
- File changed:
  - `marketplace/x402_middleware.py`
- Validation:
  - `pytest tests/test_marketplace.py -q` -> `19 passed`.

### 2026-05-06 13:12-13:13 (local) — mini E2E progress with zero-fee mode
- Re-ran mini E2E on isolated port with `INSERTION_FEE_USDC=0`.
- Result:
  - bid publishing succeeded
  - runner produced and submitted multiple bids (>=4 landed)
  - E2E advanced past previous x402 insertion-fee blocker
- New blocker on accept/settlement step:
  - `502 settlement transfer failed`
  - underlying CDP error: `ERC20: transfer amount exceeds balance`
- Interpretation:
  - insertion-fee path is now unblocked in zero-fee mode
  - remaining failure is expected reserve-funding insufficiency for full
    loan-amount settlement transfer.

### 2026-05-06 13:15-13:22 (local) — attempted small-loan full E2E; reserve limits still block settlement
- Added `E2E_LOAN_AMOUNT` override to `scripts/e2e_test.py` so loan size can be
  tuned without editing code each run.
- Synced script to droplet and ran multiple mini-E2E attempts on `:8012`:
  - `E2E_LOAN_AMOUNT=100`: bids observed in one run, but a prior stale run still
    hit old 30k settlement math before sync race resolved.
  - `E2E_LOAN_AMOUNT=1000`: only 1 bid landed; accept still failed with
    `502 settlement transfer failed`.
  - `E2E_LOAN_AMOUNT=250`: 0 bids landed (all lender decisions declined).
- Direct wallet inspection using modern CDP SDK showed reserve balance only
  `4.0 USDC` after two additional faucet drips.
- Repeated faucet top-up attempts then hit hard project limit:
  - `faucet_limit_exceeded` (HTTP 429) for subsequent requests.
- Attempted to transfer USDC from dealer/lender wallets to reserve as fallback;
  all transfers returned `Insufficient balance to execute the transaction.`
- Net: insertion path is working in zero-fee mode, but **full live settlement PASS**
  remains blocked by CDP spendable-balance constraints + faucet/project limits.

### 2026-05-06 13:41-13:45 (local) — micro premium experiments still blocked by CDP spendability
- Launched isolated marketplace stacks with reduced `WIN_PREMIUM_RATE`:
  - `0.0001` (win premium `$3.00` on `$30k` loan)
  - `0.00003` (win premium `$0.90` on `$30k` loan)
- Both runs produced healthy bid volumes (multiple approvals and bids), but accept
  still failed with `502` + CDP `ApiError` (`ERC20: transfer amount exceeds balance`).
- Verified with direct transfer probes from marketplace wallet:
  - attempted sends of `0.01`, `0.05`, `0.10`, `0.50` USDC
  - all failed with `Insufficient balance to execute the transaction.`
- Interpretation: wallet-reported USDC balance is present, but currently not
  spendable for transfer operations (likely faucet/project/account constraints).
  Micro-amount tuning alone cannot bypass this in current CDP state.

### 2026-05-06 13:46-13:47 (local) — switched to stub settlement mode; full mini-E2E PASS
- Added runtime toggle for settlement executor:
  - `SETTLEMENT_MODE=stub` -> uses deterministic stub tx hashes
  - default remains live CDP executor (`SETTLEMENT_MODE=live`).
- Files updated:
  - `shared/config.py` (new `settlement_mode` setting)
  - `marketplace/settler.py` (`get_settlement_executor` selects stub vs live)
- Validation:
  - `pytest tests/test_marketplace.py -q` -> `19 passed`.
- Deployed to droplet and ran marketplace+runner on `:8015` with:
  - `INSERTION_FEE_USDC=0`
  - `SETTLEMENT_MODE=stub`
- Mini E2E result:
  - bids landed (`5` bids)
  - accept succeeded (`HTTP 200`)
  - settlement returned stub tx hashes:
    - `dealer_payout_tx=0xstubsettle00aaaaaaaa`
    - `marketplace_cut_tx=0xstubsettle01aaaaaaaa`
    - `reserve_tx=0xstubsettle02aaaaaaaa`
  - final status: `E2E PASS`

### 2026-05-06 13:58-14:10 (local) — Wednesday AMD profiling evidence capture (AppBid workload)
- Ran AppBid concurrency workload while sampling GPU telemetry at 1s cadence:
  - workload: `scripts.concurrency_demo` against active demo stack (`:8015`)
  - sampler: `rocm-smi --showuse --showpower --showtemp --showmemuse --showbw --json`
- Generated profiling artifacts on droplet:
  - `/root/appbid/artifacts/profiling/wed_raw_metrics.csv`
  - `/root/appbid/artifacts/profiling/wed_utilization.png`
  - `/root/appbid/artifacts/profiling/wed_bandwidth.png`
  - `/root/appbid/artifacts/profiling/wed_power_thermals.png`
  - `/root/appbid/artifacts/profiling/wed_summary.json`
  - `/root/appbid/artifacts/profiling/wed_concurrency_demo.log`
- Captured summary metrics:
  - samples: `56`
  - duration: `59.04s`
  - avg GPU use: `84.12%`
  - peak GPU use: `99%`
  - peak power: `740W`
  - peak junction temp: `61C`
  - peak memory temp: `57C`
- Bandwidth note:
  - `Avg. Memory Bandwidth` from rocm-smi stayed `0` in this run (driver/reporting
    limitation on this image path despite active load); chart is preserved with raw units.
- Tooling note:
  - `omniperf` not present on this image.
  - `rocprof/rocprofv2` invocation is available, but ROCm7 deprecation warning is
    emitted and counter-output persistence is inconsistent on this stack; telemetry
    evidence for this pass uses rocm-smi + workload logs.

### 2026-05-07 07:20-07:35 (local) — AITER runtime evidence verification
- Reconnected to the active MI300X droplet and validated current public IP (`129.212.181.67`) via API + SSH.
- Scanned existing serving logs on droplet (`/root/appbid/*.log`) for backend markers.
- Confirmed repeated AITER signatures in FP8/BF16 logs:
  - `[Aiter] ... VLLM_ROCM_USE_AITER_MHA=True`
  - `[Aiter] ... VLLM_ROCM_USE_AITER_TRITON_FP8_BMM=True`
  - `Using Flash Attention backend on V1 engine.`
- Practical outcome:
  - AITER verification is now evidence-backed for deck/docs without requiring a new rebuild pass.

### 2026-05-07 07:35-07:45 (local) — Optimum-AMD training-path integration + env constraint
- Added explicit training flags for AMD optimization path in code:
  - `lora_training/train_lora.py` -> `--amd-optimize`
  - `lora_training/train_all.py` -> `--amd-optimize`
- Added best-effort Optimum integration hook with explicit log output and hard failure if optimization is requested but no compatible Optimum path is importable.
- Attempted install test on droplet venv (`Python 3.12.3`):
  - `pip install optimum-amd` failed because package pins `onnxruntime<1.16`, and no matching wheel is available for this Python version.
- Practical outcome:
  - Code path is wired; environment/package compatibility remains the blocker on this runtime.

### 2026-05-07 07:45-07:50 (local) — AMD model-source and CK due diligence
- Firecrawl check of `huggingface.co/amd` found multiple Qwen-family artifacts, but no clear direct `Qwen2.5-72B` model target in this pass.
- Captured CK reference from ROCm docs (`Optimizing with Composable Kernel`):
  - CK is AMD's low-level programming model for performance-critical ML kernels and fusion via C++ templates.
- Practical outcome:
  - Can cite CK accurately as lower-level fused-kernel substrate beneath higher-level serving/runtime paths.

### 2026-05-07 07:50-08:33 (local) — Recurrent SSH instability during benchmark automation
- Goal during this window:
  - run a detached on-droplet benchmark job to compare LoRA training baseline vs `--amd-optimize` with minimal chat/tool overhead.
- Observed behavior:
  - control plane remained `active` and public IP stayed assigned (`129.212.181.67`),
    while SSH repeatedly failed with:
    - `Connection refused`
    - intermittent timeouts
  - failures happened during both interactive SSH and SCP file transfer windows.
- Recovery attempts performed:
  - repeated reconnect/retry loops (SSH + SCP + remote launch).
  - API-initiated `reboot` and `power_cycle` actions; SSH recovered briefly and then regressed to refusal state.
  - benchmark runner was adjusted to be detached/automated to reduce dependence on persistent SSH sessions.
- Practical impact:
  - benchmark orchestration could not be completed reliably despite multiple infra recovery attempts.
  - this appears consistent with prior platform instability signatures already documented in this file (active droplet with unstable SSH accessibility).
- Suggested platform improvement:
  - provide a stronger health signal than `active` for GPU droplets (for example, a guest-level SSH readiness heartbeat),
  - and/or expose a recovery workflow that guarantees network/SSH readiness before marking instance healthy.

### 2026-05-07 09:09-09:44 (local) — Optimum benchmark completion on fresh droplet (with spacing discipline)
- Goal:
  - complete baseline vs `--amd-optimize` LoRA training benchmark with low-pressure SSH sequencing.
- Method:
  - required multiple successful SSH probes before action;
  - spaced SCP/SSH commands with 30-40s delays;
  - launched benchmark detached via `/root/appbid_optimum_bench.sh`.
- Environment/result notes:
  - benchmark summary completed with both runs passing at process level:
    - baseline: `exit_code=0`, wall ~`29.19s`
    - amd_opt: `exit_code=0`, wall ~`18.11s`
  - trainer metrics from logs:
    - baseline: `train_runtime=8.1444`, `train_samples_per_second=3.929`, `train_steps_per_second=0.246`
    - amd_opt: `train_runtime=7.2168`, `train_samples_per_second=4.434`, `train_steps_per_second=0.277`
  - critical caveat:
    - `optimum` and `optimum.amd` import successfully, but expected transform modules
      (`optimum.amd.bettertransformer`, `optimum.bettertransformer`) are not present in this runtime.
    - `--amd-optimize` therefore completes without applying a confirmed Optimum transform for MI300X training.
- Practical interpretation:
  - this run is useful as a process/comparison sanity check,
  - but should not be claimed as validated Optimum-AMD training acceleration evidence.
- Deck-safe line:
  - "Optimum-AMD package is detected in our training runtime, but a compatible MI300X training transform was not exposed in this environment; we retained the stable BF16 training path and documented the gap transparently."

### 2026-05-07 12:48-13:06 (local) — 60-minute eval completion + product-shape smoke
- 60-minute evaluation run completed with artifacts under:
  - `/root/appbid/artifacts/profiling/60min_eval_20260507_163121/`
- Initial `summary.json` was empty due to extractor selecting the wrong target path.
  - Fixed by binding extractor to the run-local `OUT_DIR`.
  - Regenerated `summary.json` from captured logs.
- Measured AITER A/B (`c=4`) result:
  - ON: `7.43 req/s`, `327.87 tok/s`, `p95=0.59s`
  - OFF: `6.58 req/s`, `307.56 tok/s`, `p95=0.81s`
  - outcome: AITER ON kept as default.
- Added lender-side runtime toggle `PAYMENT_MODE=stub` to simulate x402 payment
  envelopes while keeping insertion-fee middleware active.
- Live smoke executed in simulated payment + stub settlement mode:
  - publish -> bids -> accept -> settlement
  - result: `E2E PASS`
  - settlement tx hashes: deterministic stub values (`0xstubsettle00/01/02...`).

### 2026-05-07 13:33-13:36 (local) — web exposure blocker and fix
- Symptom:
  - Streamlit process was healthy and listening on `0.0.0.0:8501`, but browser access
    to `http://<droplet-ip>:8501` timed out.
- Root cause:
  - host firewall (`ufw`) allowed only `22/80/443`; app/demo ports were blocked.
- Fix:
  - opened inbound rules for `8501/tcp` and `8016/tcp`.
- Validation:
  - external `curl` to `http://<droplet-ip>:8501` returned `HTTP/1.1 200 OK`.
  - user confirmed browser path worked afterward.

### 2026-05-07 13:51-14:26 (local) — evidence pull, snapshot rollover, and GPU teardown
- Pulled final evidence artifacts from droplet to repo:
  - `artifacts/profiling/60min_eval_20260507_163121/`
  - `artifacts/profiling/e2e-8016.log`
  - `artifacts/profiling/runner-8016.log`
  - `artifacts/profiling/streamlit-8501.log`
- Created final snapshot before teardown:
  - new snapshot: `appbid-final-20260507-1855` (image id `227675728`)
  - observed extended `pending` period before becoming `available`.
- Deleted previous snapshot after new snapshot availability:
  - deleted image id `227555448` (`appbid-final-20260506-150705`).
- Destroyed active MI300X droplet:
  - droplet id `569562698` deleted (`204` API response).
  - post-check: no active droplets in project account at wrap-up.

### 2026-05-08 04:26-05:15 (local) — strict 72B retest after 7B automation drift
- Context:
  - user requested that no further benchmark narrative rely on 7B.
  - objective was to re-run AITER ON/OFF comparisons on `Qwen2.5-72B` FP8 PTPC only.
- Fresh droplet used:
  - id `569722031`
  - public IP `129.212.183.183`
- Retest packs executed:
  - `72b_retest_20260508_092743` (initial revalidation)
  - `72b_retest_pack_20260508_094115` (repeat pack + quality checks)
  - `72b_retest_tuned_20260508_101732` (tuned serve profile: `max-num-seqs=128`)
- Key measured outcomes:
  - Initial repeat pack (`72b_retest_pack_20260508_094115`):
    - `c=2`: AITER ON underperformed OFF on req/s and p95.
    - `c=4`: AITER ON near parity on throughput and modest p95 improvement.
    - quality: both ON and OFF `20/20` JSON parse pass.
  - Tuned pack (`72b_retest_tuned_20260508_101732`):
    - `c=4` avg (2 repeats): ON vs OFF
      - req/s: `2.73` vs `2.69` (`+1.5%`)
      - tok/s: `122.33` vs `118.97` (`+2.8%`)
      - p95: `1.56s` vs `1.75s` (`~10.9% lower`)
    - `c=8` avg (2 repeats): ON vs OFF
      - req/s: `4.90` vs `5.27` (`-7.0%`)
      - tok/s: `223.75` vs `230.06` (`-2.7%`)
      - p95: `1.91s` vs `1.62s` (`~17.9% worse`)
- Interpretation:
  - AITER benefit is profile-dependent for this 72B stack:
    - favorable at moderate concurrency (`c=4`) in tuned settings,
    - not favorable at higher tested concurrency (`c=8`) in this run.
  - final narrative must remain 72B-scoped and avoid universal AITER-win claims.

## Suggested Structure for Future Entries
- **What I was trying to do**
- **What worked well**
- **What was confusing or slow**
- **What error/message appeared (if any)**
- **How I resolved it**
- **Suggested product/documentation improvement**
