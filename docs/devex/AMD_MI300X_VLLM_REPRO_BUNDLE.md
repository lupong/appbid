# AMD MI300X vLLM Repro Bundle

Purpose: concise support ticket bundle for AMD Developer Cloud hackathon support.

## Environment

- Droplet GPU: AMD Instinct MI300X VF (`gfx942`)
- Host OS: Ubuntu 24.04.4 LTS (`6.8.0-106-generic`)
- Docker: `29.4.2`
- Preloaded images:
  - `vllm/vllm-openai-rocm:v0.17.1`
  - `rocm:latest`

Host GPU check:

```bash
rocm-smi --showproductname --showmeminfo vram --showuse
```

Observed:
- GPU detected
- VRAM Total: `205822885888` bytes (~192 GB)

Container GPU sanity check:

```bash
docker run --rm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --entrypoint /bin/bash vllm/vllm-openai-rocm:v0.17.1 -lc \
  "python3 -c 'import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.device_count())'"
```

Observed:
- torch `2.9.1+git8907517`
- `torch.cuda.is_available() == True`
- `torch.cuda.device_count() == 1`

## Reproduction Steps

From repo root on droplet:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct VLLM_ENABLE_LORA=0 VLLM_PORT=8001 ./infra/devcloud.sh serve dev
```

Underlying Docker run path used by script:

```bash
docker run --rm --name appbid-vllm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8001:8001 \
  -v /root/appbid:/app -w /app \
  --entrypoint /bin/bash \
  vllm/vllm-openai-rocm:v0.17.1 \
  infra/start_vllm.sh
```

## Current Behavior

- Container stays running and host port `8001` is published.
- vLLM logs show successful model download/load for `Qwen/Qwen2.5-7B-Instruct`.
- API does not become ready (`/v1/models` not responding) even after ~5 minutes.
- Log appears to stall at AITER kernel build step:
  - `start build [module_rmsnorm]`
  - no subsequent completion line observed.

## Key Log Snippet

```text
(EngineCore_DP0 pid=143) INFO ... Model loading took 14.37 GiB memory and 12.876351 seconds
(EngineCore_DP0 pid=143) INFO ... Cache the graph of compile range (1, 8192) for later use
(EngineCore_DP0 pid=143) [aiter] start build [module_rmsnorm] under /usr/local/lib/python3.12/dist-packages/aiter/jit/build/module_rmsnorm
```

## Support Ask

1) Is this a known MI300X VF + `vllm/vllm-openai-rocm:v0.17.1` behavior (AITER compile stall)?
2) Is there a recommended launch flag/env override to avoid this startup stall?
3) Is there a known-good image tag + command for fastest hackathon bring-up on MI300X VF?

