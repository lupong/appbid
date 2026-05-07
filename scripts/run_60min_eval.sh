#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/appbid"
OUT_DIR="$ROOT_DIR/artifacts/profiling/60min_eval_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT_DIR"

DOCKER_IMAGE="rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915"
MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8010
TOTAL_SECONDS=3600
START_EPOCH="$(date +%s)"
END_EPOCH="$((START_EPOCH + TOTAL_SECONDS))"
MAX_SOAK_LOOPS=120

cleanup() {
  docker rm -f eval-vllm >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_ready() {
  local retries=120
  for ((i=1; i<=retries; i++)); do
    if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

run_bench() {
  local label="$1"
  local concurrency="$2"
  local requests="$3"
  local logfile="$OUT_DIR/${label}.log"
  python3 "$ROOT_DIR/scripts/benchmark_vllm_stdlib.py" \
    --url "http://127.0.0.1:${PORT}/v1" \
    --model "$MODEL" \
    --requests "$requests" \
    --concurrency "$concurrency" \
    --max-tokens 128 \
    >"$logfile" 2>&1 || true
}

run_quality_guardrail() {
  python3 - <<'PY' >"$OUT_DIR/quality_guardrail.json"
import json
import urllib.request

url = "http://127.0.0.1:8010/v1/chat/completions"
payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "Return exactly this JSON: {\"ok\":true,\"value\":42}"}],
    "response_format": {"type": "json_object"},
    "temperature": 0.0,
    "max_tokens": 64,
}
ok = 0
total = 20
errors = 0
for _ in range(total):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if parsed.get("ok") is True and "value" in parsed:
            ok += 1
    except Exception:
        errors += 1
print(json.dumps({"total": total, "ok": ok, "errors": errors, "parse_success_rate": ok / total if total else 0.0}, indent=2))
PY
}

extract_summary() {
  OUT_DIR="$OUT_DIR" python3 - <<'PY' >"$OUT_DIR/summary.json"
import json
import os
import re
from pathlib import Path

out = {}
latest = Path(os.environ["OUT_DIR"])

def parse_bench(path: Path):
    txt = path.read_text(errors="ignore")
    def grab(pattern):
        m = re.search(pattern, txt)
        return float(m.group(1)) if m else None
    return {
        "req_per_s": grab(r"req/s:\s*([0-9.]+)"),
        "tok_per_s": grab(r"completion tok/s:\s*([0-9.]+)"),
        "p50_s": grab(r"p50=([0-9.]+)"),
        "p95_s": grab(r"p95=([0-9.]+)"),
        "max_s": grab(r"max=([0-9.]+)"),
    }

# key fixed logs
for name in [
    "aiter_on_c1.log",
    "aiter_on_c2.log",
    "aiter_on_c4.log",
    "aiter_on_c8.log",
    "aiter_off_c4.log",
]:
    p = latest / name
    if p.exists():
        out[name] = parse_bench(p)

# compact soak aggregation
soak = [parse_bench(p) for p in sorted(latest.glob("soak_loop_*.log"))]
soak = [x for x in soak if x["req_per_s"] is not None]
if soak:
    def avg(key):
        vals = [x[key] for x in soak if x[key] is not None]
        return sum(vals) / len(vals) if vals else None
    out["soak_aggregate"] = {
        "loops": len(soak),
        "avg_req_per_s": avg("req_per_s"),
        "avg_tok_per_s": avg("tok_per_s"),
        "avg_p50_s": avg("p50_s"),
        "avg_p95_s": avg("p95_s"),
        "max_of_max_s": max([x["max_s"] for x in soak if x["max_s"] is not None], default=None),
    }

q = latest / "quality_guardrail.json"
if q.exists():
    out["quality_guardrail"] = json.loads(q.read_text())
print(json.dumps(out, indent=2))
PY
}

# metadata
cat >"$OUT_DIR/meta.json" <<EOF
{
  "model": "$MODEL",
  "docker_image": "$DOCKER_IMAGE",
  "start_epoch": $START_EPOCH,
  "end_epoch": $END_EPOCH,
  "target_duration_seconds": $TOTAL_SECONDS
}
EOF

# AITER ON serve
docker rm -f eval-vllm >/dev/null 2>&1 || true
docker run -d --name eval-vllm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p "${PORT}:8000" \
  -v "$ROOT_DIR:/app" -w /app \
  "$DOCKER_IMAGE" \
  /bin/bash -lc "export VLLM_ROCM_USE_AITER=1; vllm serve $MODEL --port 8000 --dtype bfloat16 --gpu-memory-utilization 0.90 --max-num-seqs 128 --max-model-len 8192 --tensor-parallel-size 1" \
  >"$OUT_DIR/aiter_on_server.log" 2>&1

wait_ready

# Concurrency sweep (AITER ON)
run_bench "aiter_on_c1" 1 120
run_bench "aiter_on_c2" 2 120
run_bench "aiter_on_c4" 4 120
run_bench "aiter_on_c8" 8 120
run_quality_guardrail

# AITER OFF A/B sample
docker rm -f eval-vllm >/dev/null 2>&1 || true
docker run -d --name eval-vllm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p "${PORT}:8000" \
  -v "$ROOT_DIR:/app" -w /app \
  "$DOCKER_IMAGE" \
  /bin/bash -lc "export VLLM_ROCM_USE_AITER=0; vllm serve $MODEL --port 8000 --dtype bfloat16 --gpu-memory-utilization 0.90 --max-num-seqs 128 --max-model-len 8192 --tensor-parallel-size 1" \
  >"$OUT_DIR/aiter_off_server.log" 2>&1

wait_ready
run_bench "aiter_off_c4" 4 120

# Soak remainder (AITER ON)
docker rm -f eval-vllm >/dev/null 2>&1 || true
docker run -d --name eval-vllm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p "${PORT}:8000" \
  -v "$ROOT_DIR:/app" -w /app \
  "$DOCKER_IMAGE" \
  /bin/bash -lc "export VLLM_ROCM_USE_AITER=1; vllm serve $MODEL --port 8000 --dtype bfloat16 --gpu-memory-utilization 0.90 --max-num-seqs 128 --max-model-len 8192 --tensor-parallel-size 1" \
  >"$OUT_DIR/soak_server.log" 2>&1

wait_ready
loop=1
while [ "$(date +%s)" -lt "$END_EPOCH" ] && [ "$loop" -le "$MAX_SOAK_LOOPS" ]; do
  run_bench "soak_loop_${loop}" 4 200
  loop=$((loop + 1))
done

extract_summary
echo "$OUT_DIR" >"$ROOT_DIR/artifacts/profiling/60min_eval_latest_path.txt"
