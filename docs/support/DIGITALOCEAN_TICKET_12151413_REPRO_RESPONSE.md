# DigitalOcean Support Response Draft — Ticket #12151413

Use this as a copy/paste response to support. It includes exact startup commands, prompts/payloads, and failing log evidence.

## Message to send

Hi team,

Thanks for the follow-up. Below is a reproducible setup from our MI300X AppBid environment.

### Environment

- Droplet image: `0.9.2---ROCm-7.0-gpu-mi300x1-192gb-devcloud-atl1`
- Container image: `rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915`
- GPU: AMD Instinct MI300X VF (`gfx942`)
- Model: `Qwen/Qwen2.5-7B-Instruct`
- LoRA adapters (when enabled): `stcu_retail_auto`, `unitus_community_cu`, `exeter_finance`, `family_savings_cu`, `crouse_federal_cu`

### Exact server start commands used per test case

All cases were launched from repo root (`/root/appbid`) using Docker with `/app` bind-mounted to the repo.

#### Case A: LoRA OFF + compiled (PASS)

```bash
docker run --rm --name appbid-vllm-a \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8001:8001 \
  -v /root/appbid:/app -w /app \
  --entrypoint /bin/bash \
  rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915 \
  -lc 'export VLLM_ROCM_USE_AITER=1; vllm serve Qwen/Qwen2.5-7B-Instruct --port 8001 --dtype bfloat16 --max-model-len 8192 --gpu-memory-utilization 0.90 --max-num-seqs 128 --tensor-parallel-size 1'
```

#### Case B: LoRA OFF + eager (FAIL: corrupted generation)

```bash
docker run --rm --name appbid-vllm-b \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8002:8002 \
  -v /root/appbid:/app -w /app \
  --entrypoint /bin/bash \
  rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915 \
  -lc 'export VLLM_ROCM_USE_AITER=1; vllm serve Qwen/Qwen2.5-7B-Instruct --port 8002 --enforce-eager --dtype bfloat16 --max-model-len 8192 --gpu-memory-utilization 0.90 --max-num-seqs 128 --tensor-parallel-size 1'
```

#### Case C: LoRA ON + compiled (FAIL: startup crash)

```bash
docker run --rm --name appbid-vllm-c \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8003:8003 \
  -v /root/appbid:/app -w /app \
  --entrypoint /bin/bash \
  rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915 \
  -lc 'export VLLM_ROCM_USE_AITER=1; vllm serve Qwen/Qwen2.5-7B-Instruct --port 8003 --enable-lora --max-loras 8 --max-lora-rank 16 --lora-modules stcu_retail_auto=/app/lora_adapters/stcu_retail_auto unitus_community_cu=/app/lora_adapters/unitus_community_cu exeter_finance=/app/lora_adapters/exeter_finance family_savings_cu=/app/lora_adapters/family_savings_cu crouse_federal_cu=/app/lora_adapters/crouse_federal_cu --dtype bfloat16 --max-model-len 8192 --gpu-memory-utilization 0.90 --max-num-seqs 128 --tensor-parallel-size 1'
```

#### Case D: LoRA ON + eager (FAIL: corrupted generation)

```bash
docker run --rm --name appbid-vllm-d \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8004:8004 \
  -v /root/appbid:/app -w /app \
  --entrypoint /bin/bash \
  rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915 \
  -lc 'export VLLM_ROCM_USE_AITER=1; vllm serve Qwen/Qwen2.5-7B-Instruct --port 8004 --enforce-eager --enable-lora --max-loras 8 --max-lora-rank 16 --lora-modules stcu_retail_auto=/app/lora_adapters/stcu_retail_auto unitus_community_cu=/app/lora_adapters/unitus_community_cu exeter_finance=/app/lora_adapters/exeter_finance family_savings_cu=/app/lora_adapters/family_savings_cu crouse_federal_cu=/app/lora_adapters/crouse_federal_cu --dtype bfloat16 --max-model-len 8192 --gpu-memory-utilization 0.90 --max-num-seqs 128 --tensor-parallel-size 1'
```

### Inference prompts and request payloads used

#### Readiness

```bash
curl -sS http://127.0.0.1:8001/v1/models
```

#### Plain-text prompt probe

```bash
curl -sS http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"Qwen/Qwen2.5-7B-Instruct",
    "messages":[{"role":"user","content":"Say hello in one short sentence."}],
    "temperature":0,
    "max_tokens":64
  }'
```

#### Strict JSON output probe

```bash
curl -sS http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"Qwen/Qwen2.5-7B-Instruct",
    "messages":[{"role":"user","content":"Return exactly this JSON: {\"ok\":true,\"value\":42}"}],
    "response_format":{"type":"json_object"},
    "temperature":0,
    "max_tokens":128
  }'
```

#### LoRA-model probe example

```bash
curl -sS http://127.0.0.1:8004/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"stcu_retail_auto",
    "messages":[{"role":"user","content":"Return exactly this JSON: {\"ok\":true,\"value\":42}"}],
    "response_format":{"type":"json_object"},
    "temperature":0,
    "max_tokens":128
  }'
```

### Failing scenario logs

#### 1) Startup crash (Case C, LoRA ON + compiled)

Key traceback signatures observed:

```text
torch.fx.experimental.symbolic_shapes.ConstraintViolationError:
Constraints violated (L['input_ids'].size()[0], L['positions'].size()[0])
...
RuntimeError: Engine core initialization failed
```

Behavior: `/v1/models` is not available; connection refused after process exits.

#### 2) Corrupted output (Case D, LoRA ON + eager)

Server starts and routes respond, but generation is semantically corrupted:

```text
plain output: repeated "system" tokens / non-semantic token stream
JSON probe output: syntactically odd / semantically empty payloads (for example {"\n  \t}"-style)
```

### Notes

- LoRA training itself succeeded on MI300X.
- Direct `transformers + peft` inference with the same adapters produced coherent outputs.
- The failures appear isolated to vLLM serving behavior on this ROCm runtime path.

If useful, we can do a live session and run the above four commands end-to-end while sharing terminal output.

Thanks again.

