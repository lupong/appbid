# AMD ROCm vLLM Repro Matrix (MI300X)

Date: 2026-05-05  
Droplet: `0.9.2---ROCm-7.0-gpu-mi300x1-192gb-devcloud-atl1`  
Image: `rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915`  
Model: `Qwen/Qwen2.5-7B-Instruct`  
LoRAs (when enabled): `stcu_retail_auto`, `unitus_community_cu`, `exeter_finance`, `family_savings_cu`, `crouse_federal_cu`

## Test Method

- For each case, launch vLLM with one config variant:
  - LoRA off/on
  - compiled/eager
- Probe:
  - `GET /v1/models` readiness
  - plain chat prompt: `Say hello in one short sentence.`
  - JSON prompt: `Return exactly this JSON: {"ok":true,"value":42}`
- Expected:
  - plain: coherent English sentence
  - JSON: valid parseable JSON output

## Case Results

- **Case A (LoRA off, compiled)**
  - Startup: success
  - Models: base model only
  - Plain output: `Hello!`
  - JSON output: valid JSON (`{"ok": true, "value": 42}`)
  - Verdict: **PASS**

- **Case B (LoRA off, eager / `--enforce-eager`)**
  - Startup: success
  - Models: base model only
  - Plain output: garbled/non-linguistic token sequence
  - JSON output: malformed/truncated (`"{                  \n                    "`)
  - Verdict: **FAIL (generation corruption)**

- **Case C (LoRA on, compiled)**
  - Startup: failed (API not available)
  - `GET /v1/models`: connection refused
  - Log evidence: `torch.fx.experimental.symbolic_shapes.ConstraintViolationError`
  - Verdict: **FAIL (engine init crash)**

- **Case D (LoRA on, eager / `--enforce-eager`)**
  - Startup: success
  - Models: base + 5 LoRAs
  - Plain output (LoRA model): repeated `system` tokens, non-semantic
  - JSON output (LoRA model): syntactically odd/semantically empty (`{"\n  \t}"`-style)
  - Verdict: **FAIL (generation corruption under LoRA eager)**

## Key Logs / Signatures

- Compiled + LoRA failure:
  - `ConstraintViolationError: Constraints violated (L['input_ids'].size()[0], L['positions'].size()[0])`
  - followed by `RuntimeError: Engine core initialization failed`
- Eager-mode corruption:
  - server is healthy and routes are up
  - outputs are still semantically corrupted for both plain and structured prompts

## Isolation Notes

- LoRA training completed successfully on MI300X and produced distinct adapter artifacts.
- Direct `transformers + peft` inference (outside vLLM serving path) produced coherent lender-differentiated outputs.
- Therefore, the blocker is isolated to **vLLM serving behavior on this ROCm image/runtime combination**, not app business logic.

## Suggested AMD Follow-up

- Publish known-good matrix for this image:
  - LoRA off/on x compiled/eager
  - expected output sanity checks
- Provide a recommended stable config for MI300X + LoRA serving.
- Investigate eager-mode text corruption and compiled-mode dynamic-shape guard failure.
