# Support Follow-up Package — Ticket #12151413

Use this checklist when support engineering asks for additional artifacts.

Prepared response draft with exact repro commands/payloads:

- `DIGITALOCEAN_TICKET_12151413_REPRO_RESPONSE.md`

## 1) Case command lines (exact)

Provide exact `docker run` / `vllm serve` commands used for each matrix case:

- Case A: LoRA off + compiled
- Case B: LoRA off + eager
- Case C: LoRA on + compiled
- Case D: LoRA on + eager

Reference: `../devex/AMD_VLLM_ROCM_REPRO_MATRIX.md`

## 2) Failing logs (full)

Attach complete logs, especially:

- `ConstraintViolationError` stack trace (compiled + LoRA)
- eager-mode corrupted-output sessions
- API startup/route logs for cases that "start but produce bad outputs"

## 3) Environment metadata

Include:

- droplet SKU and region
- image names/tags used
- GPU model and VRAM
- model name and LoRA aliases

## 4) Repro prompt payloads

Include exact payloads used for:

- simple plain-text probe
- strict JSON probe (`response_format={"type":"json_object"}`)

## 5) Isolation evidence

Attach concise note that:

- LoRA training succeeded
- adapter files are distinct
- direct `transformers + peft` inference is coherent
- failures isolate to vLLM ROCm serving path

## 6) Requested outcome from engineering

Ask for:

- known-good config matrix (LoRA on/off × eager/compiled)
- stable image/runtime recommendation
- workaround + ETA if bug is known
