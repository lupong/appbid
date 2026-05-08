#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/appbid"
cd "$ROOT_DIR"
MODEL_PATH="${DEMO_VLLM_MODEL:-/app/models/qwen2.5-72b-ptpc-fp8-vllm}"

echo "[demo-start] restarting marketplace on :8016"
python3 - <<'PY'
import os, signal, subprocess, time

out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
for line in out.splitlines():
    if "uvicorn marketplace.server:app" in line and "--port 8016" in line:
        pid = int(line.strip().split()[0])
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"killed marketplace pid={pid}")
        except ProcessLookupError:
            pass
time.sleep(1)
PY

nohup env \
  MARKETPLACE_HOST=0.0.0.0 \
  MARKETPLACE_PORT=8016 \
  INSERTION_FEE_USDC=0 \
  SETTLEMENT_MODE=stub \
  PAYMENT_MODE=stub \
  X402_FACILITATOR_MODE=local \
  .venv/bin/python -m uvicorn marketplace.server:app --host 0.0.0.0 --port 8016 \
  > /root/appbid/marketplace-8016.log 2>&1 < /dev/null &

echo "[demo-start] ensuring runner is active"
python3 - <<'PY'
import os, signal, subprocess, time

out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
for line in out.splitlines():
    if "python -m agents.runner" in line or "agents.runner" in line:
        pid = int(line.strip().split()[0])
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"killed runner pid={pid}")
        except ProcessLookupError:
            pass
time.sleep(1)
PY

nohup env \
  MARKETPLACE_HOST=127.0.0.1 \
  MARKETPLACE_PORT=8016 \
  MARKETPLACE_URL=http://127.0.0.1:8016 \
  VLLM_URL=http://127.0.0.1:8001/v1 \
  VLLM_MODEL="$MODEL_PATH" \
  LORA_MODE=prompt \
  PAYMENT_MODE=stub \
  .venv/bin/python -m agents.runner \
  > /root/appbid/runner.log 2>&1 < /dev/null &

echo "[demo-start] quick health checks"
python3 - <<'PY'
import json
import urllib.request
import os
import sys

checks = [
    "http://127.0.0.1:8016/healthz",
    "http://127.0.0.1:8016/gpu/metrics",
]
for url in checks:
    with urllib.request.urlopen(url, timeout=10) as r:
        body = r.read().decode()
    preview = body[:220].replace("\n", " ")
    print(f"ok {url} :: {preview}")

expected = os.getenv("DEMO_VLLM_MODEL", "/app/models/qwen2.5-72b-ptpc-fp8-vllm")
with urllib.request.urlopen("http://127.0.0.1:8001/v1/models", timeout=10) as r:
    models = json.loads(r.read().decode())
model_id = models["data"][0]["id"] if models.get("data") else ""
print(f"ok http://127.0.0.1:8001/v1/models :: model_id={model_id}")
if model_id != expected:
    print(f"error expected model_id={expected} but got {model_id}", file=sys.stderr)
    sys.exit(1)

print("demo-start complete")
PY
