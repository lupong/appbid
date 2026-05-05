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

## Suggested Structure for Future Entries
- **What I was trying to do**
- **What worked well**
- **What was confusing or slow**
- **What error/message appeared (if any)**
- **How I resolved it**
- **Suggested product/documentation improvement**
