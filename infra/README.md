# infra/

Container + GPU tooling for running Credit App+ on the AMD MI300X.

## Use AMD's images, not bare Ubuntu

The MI300X needs a specific ROCm driver/userland match. Don't bootstrap
ROCm yourself — start from an AMD-published base image and add the project
stack on top.

| Workload | Base image | Dockerfile |
|----------|------------|------------|
| vLLM serving (72B + 5 LoRAs) | `rocm/vllm:latest` | `Dockerfile.serving` |
| LoRA fine-tuning | `rocm/pytorch:latest` | `Dockerfile.training` |

Both already include a tested torch + ROCm + flash-attention combination.
Do **not** pull `bitsandbytes`, `unsloth`, `xformers`, or `flash-attn` from
upstream pip — each has known ROCm friction. AMD's images provide compatible
builds.

```bash
# On the MI300X droplet
docker build -t appbid-serve -f infra/Dockerfile.serving .
docker build -t appbid-train -f infra/Dockerfile.training .
```

## Quick droplet workflow (MI300X)

Use the helper script for a faster dev loop on AMD Developer Cloud:

```bash
# 1) One-time project setup
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env

# 2) Validate ROCm + GPU visibility
infra/devcloud.sh doctor

# 3) Optional: dry-run LoRA pipeline (no GPU training yet)
infra/devcloud.sh train-dry-run

# 4) Full train (LLM teacher + 5 adapters)
infra/devcloud.sh train

# 5) Serve with safer bring-up defaults (profile=dev)
infra/devcloud.sh serve dev

# 6) Serve with demo throughput defaults (profile=demo)
infra/devcloud.sh serve demo

# 7) Benchmark active vLLM endpoint (run while serve is up)
infra/devcloud.sh benchmark dev
infra/devcloud.sh benchmark demo
```

`infra/start_vllm.sh` now supports `VLLM_PROFILE=dev|demo` plus env overrides:
`VLLM_MAX_NUM_SEQS`, `VLLM_GPU_MEMORY_UTILIZATION`, `VLLM_MAX_MODEL_LEN`,
`VLLM_MAX_LORAS`, `VLLM_MAX_LORA_RANK`, `VLLM_TENSOR_PARALLEL_SIZE`.

Profile defaults:

- `dev`: `gpu-memory-utilization=0.90`, `max-num-seqs=128` (safer bring-up)
- `demo`: `gpu-memory-utilization=0.95`, `max-num-seqs=256` (single-instance throughput)

These defaults align with recent AMD ROCm vLLM guidance for MI300X
(`gpu-memory-utilization` tuning per instance and `max-num-seqs` as a
memory/throughput lever).

Benchmark knobs (env overrides):

- `VLLM_BENCH_MODEL` (defaults to `VLLM_MODEL`)
- `VLLM_BENCH_REQUESTS` (default `20`)
- `VLLM_BENCH_CONCURRENCY` (defaults: `dev=4`, `demo=8`)
- `VLLM_BENCH_MAX_TOKENS` (default `128`)

## Provision droplets via code (DigitalOcean API)

You can create/manage droplets from code with `scripts/do_gpu_droplet.py`.
It uses a PAT from `DO_API_TOKEN` (see `.env.example`).

```bash
# Export token once per shell (or load from your .env)
export DO_API_TOKEN=...

# Discover required IDs/slugs first
python scripts/do_gpu_droplet.py list-ssh-keys
python scripts/do_gpu_droplet.py list-sizes
python scripts/do_gpu_droplet.py list-images --type application

# Create a droplet (example)
python scripts/do_gpu_droplet.py create \
  --name appbid-mi300x-01 \
  --region nyc3 \
  --size <gpu-size-slug> \
  --image <image-slug-or-id> \
  --ssh-key-id <ssh_key_id> \
  --tag appbid \
  --monitoring

# Inspect / delete
python scripts/do_gpu_droplet.py list --tag appbid
python scripts/do_gpu_droplet.py get <droplet_id>
python scripts/do_gpu_droplet.py delete <droplet_id>
```

PAT notes:
- PATs are created in the DigitalOcean UI and shown once; store in env vars.
- Prefer custom-scoped tokens (least privilege) for automation.

## Local dev without a GPU

You don't need the AMD images for marketplace / agent / UI work. Set:

```env
LORA_MODE=prompt
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

Then point `VLLM_URL` at any OpenAI-compatible endpoint (a real 7B served
locally, an OpenAI mock, or a stub). The lender agents and marketplace work
end-to-end without LoRA.

## Files

- `Dockerfile.serving` — vLLM container for `start_vllm.sh`.
- `Dockerfile.training` — PyTorch container for `lora_training/train_all.py`.
- `start_vllm.sh` — launches vLLM with multi-LoRA flags + ROCm env vars.
- `monitor.sh` — `watch`-driven `rocm-smi` display for live GPU stats.
- `../shared/gpu_metrics.py` — programmatic AMD-SMI snapshot used by the
  concurrency demo's live panel.
