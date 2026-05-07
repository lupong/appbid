# LoRA training

This directory builds the per-lender LoRA adapters that vLLM serves on top of
`Qwen/Qwen2.5-72B-Instruct`. **Training runs on the AMD MI300X droplet, not
in CI and not on a laptop.** Synthetic data generation is fast and CPU-only;
actual training is the multi-hour GPU job.

## Layout

```
lora_training/
├── synthetic_data.py   # generate per-lender training pairs from the rate sheet
├── train_lora.py       # train ONE LoRA (CLI: --profile-id, --data-path, ...)
├── train_all.py        # generate data + train all 5 LoRAs sequentially
├── data/               # JSONL datasets land here (gitignored at runtime)
└── README.md           # this file
```

## How the rate sheet becomes a LoRA

A lender's policy is its `rate_sheet_text` (free text on `LenderProfile`).
That single field both seeds training and serves as the inference-time
fallback prompt:

1. `synthetic_data.py` synthesizes bid requests spanning the
   FICO/term/vehicle space.
2. A **teacher** labels each bid request with a target `Decision`. Two
   teachers ship with the codebase:
   - `stub` — deterministic placeholder labels. Useful only for
     `--dry-run` pipeline validation. **Do not train on stub data for
     real** — the LoRA will only learn to emit the placeholder decision.
   - `llm` — calls an OpenAI-compatible endpoint (defaults to the local
     vLLM serving the base model) with the lender's `rate_sheet_text`
     inlined as the system prompt. This is the real teacher.
3. The training row is `{system: DECISION_SCHEMA, user: app, assistant: target}`.
   The system prompt at training time is the bare schema — the rate sheet
   is the teacher's input, not the student's. After training, the LoRA
   replays the teacher's policy from its weights.

There is **no policy engine** generating ground truth in Python — that
codepath was removed. Quality of the LoRA is bounded by the teacher's
quality on each lender's rate sheet.

## Run on the droplet

```bash
# 0. SSH onto the MI300X droplet, clone the repo, pull a recent ROCm-PyTorch.
# 1. Install training-only deps (heavy — torch ROCm + transformers + peft):
.venv/bin/pip install -r requirements-train.txt

# 2. Sanity-check the plan with the stub teacher (no GPU, no LLM calls).
#    Generates JSONL under lora_training/data/ and prints what would be
#    trained. Stub data is not useful for real training.
.venv/bin/python lora_training/train_all.py --dry-run

# 3. Generate real training data with the LLM teacher (vLLM must be up).
#    Then train. ~3-5 hours wall-clock for 5 lenders @ 300 rows each.
.venv/bin/python lora_training/train_all.py --teacher=llm

# 4. Optional: explicitly enable Optimum-backed AMD optimizations.
.venv/bin/python lora_training/train_all.py --teacher=llm --amd-optimize
```

Adapters land at `./lora_adapters/<lora_alias>/` (derived from
`LORA_ADAPTERS_DIR/<alias>` in `data/bid_policies.py`). After training,
start vLLM with `infra/start_vllm.sh`.

For a faster droplet workflow, the wrapper script mirrors these commands:

```bash
infra/devcloud.sh doctor
infra/devcloud.sh train-dry-run
infra/devcloud.sh train
infra/devcloud.sh serve dev   # or: infra/devcloud.sh serve demo
```

## Configuration

| Knob          | Default | Notes |
|---------------|---------|-------|
| LoRA rank     | 16      | Must be `<= --max-lora-rank` in `start_vllm.sh` |
| LoRA alpha    | 32      | Standard 2x rank scaling |
| Target modules| q_proj, k_proj, v_proj, o_proj | Attention only — sufficient for policy steering |
| Epochs        | 1       | 300 rows is small; more epochs overfit |
| Precision     | BF16    | No bitsandbytes — see "ROCm caveats" below |
| Examples / lender | 300 | `--n` to override |
| Teacher       | stub    | `--teacher=llm` for real labels; `stub` is dry-run only |
| AMD optimize  | off     | pass `--amd-optimize`; requires `optimum-amd` |
| Base model    | `$VLLM_MODEL` from settings | Defaults to Qwen2.5-72B-Instruct |

## ROCm caveats

`bitsandbytes` 4-bit quantization has limited / fragile ROCm support. We
deliberately use plain BF16 LoRA training instead — the MI300X has 192 GB,
which fits the 72B base in BF16 plus the rank-16 LoRA's tiny optimizer state
with comfortable margin.

If the BF16 path also hits a ROCm/PEFT incompatibility:

1. Confirm the failure point — is it `peft.get_peft_model`, the trainer
   forward pass, or `model.save_pretrained`?
2. Try pinning `torch==2.4.x` for the matching ROCm minor.
3. As a last resort, fall back to `LORA_MODE=prompt` at runtime — the
   marketplace + agents work fully without LoRA, since the same
   `rate_sheet_text` becomes the system prompt against the base model.

Optimum note:

- `--amd-optimize` depends on `optimum-amd`, which currently pins
  `onnxruntime<1.16` (no py3.12 wheel availability in our tested environment).
- Keep this path optional and treat it as environment-dependent until package
  compatibility catches up.

The `LORA_MODE=prompt` fallback is intentional — a LoRA training issue
mid-week doesn't block the demo.

## Output

Each adapter directory contains:

- `adapter_config.json` (PEFT config — rank, alpha, target modules)
- `adapter_model.safetensors` (the rank-16 weight delta)
- `tokenizer*` (tokenizer copy for convenience)

`infra/start_vllm.sh` mounts each as a `--lora-modules <alias>=<path>` entry.
