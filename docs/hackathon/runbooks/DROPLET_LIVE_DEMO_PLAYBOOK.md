# Droplet Live Demo Playbook

Use this runbook from the DigitalOcean droplet web console to demo:

1. automated multi-dealer request submissions,
2. live bid streaming in the dealer UI,
3. real-time GPU telemetry under load.

## 0) Prep

```bash
cd /root/appbid
source .venv/bin/activate
```

Security hygiene for demo screens:

- do not paste or print `.env` contents in the shared console,
- avoid commands that echo `DO_API_TOKEN`, `CDP_*`, or wallet secrets,
- keep `wallets.json` local to droplet and out of git.

## 1) Start inference on GPU (vLLM)

```bash
docker rm -f appbid-vllm >/dev/null 2>&1 || true
cd /root/appbid
nohup docker run --rm --name appbid-vllm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --ipc=host --shm-size 16G \
  -p 8001:8001 \
  -v /root/appbid:/app -w /app \
  -e VLLM_PROFILE=dev \
  -e VLLM_PORT=8001 \
  -e VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct \
  -e VLLM_ENABLE_LORA=0 \
  rocm/7.0:rocm7.0_ubuntu_22.04_vllm_0.10.1_instinct_20250915 \
  bash /app/infra/start_vllm.sh > /root/appbid/serve-8001.log 2>&1 < /dev/null &
```

Readiness check:

```bash
python3 - <<'PY'
import json, urllib.request, time
url='http://127.0.0.1:8001/v1/models'
for i in range(30):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(json.loads(r.read().decode()))
        break
    except Exception:
        time.sleep(2)
PY
```

Optional: if services were previously running and you want a one-command app reset
(marketplace + runner only), run:

```bash
cd /root/appbid
bash scripts/demo_day_start.sh
```

## 2) Start marketplace API (includes `/gpu/metrics` + `/terminal`)

```bash
pkill -f "uvicorn marketplace.server:app" || true
cd /root/appbid
nohup env \
  MARKETPLACE_HOST=0.0.0.0 \
  MARKETPLACE_PORT=8016 \
  INSERTION_FEE_USDC=0 \
  SETTLEMENT_MODE=stub \
  PAYMENT_MODE=stub \
  X402_FACILITATOR_MODE=local \
  .venv/bin/python -m uvicorn marketplace.server:app --host 0.0.0.0 --port 8016 \
  > /root/appbid/marketplace-8016.log 2>&1 < /dev/null &
```

Quick checks:

```bash
curl -s http://127.0.0.1:8016/healthz
curl -s http://127.0.0.1:8016/gpu/metrics
```

## 3) Start lender runner (wired to GPU inference)

```bash
pkill -f "python -m agents.runner" || true
cd /root/appbid
nohup env \
  MARKETPLACE_HOST=127.0.0.1 \
  MARKETPLACE_PORT=8016 \
  VLLM_URL=http://127.0.0.1:8001/v1 \
  VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct \
  LORA_MODE=prompt \
  PAYMENT_MODE=stub \
  .venv/bin/python -m agents.runner \
  > /root/appbid/runner-8016.log 2>&1 < /dev/null &
```

## 4) Start dealer UI

```bash
pkill -f "streamlit run ui/dealer_app.py" || true
cd /root/appbid
nohup env \
  MARKETPLACE_HOST=127.0.0.1 \
  MARKETPLACE_PORT=8016 \
  .venv/bin/python -m streamlit run ui/dealer_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  > /root/appbid/streamlit-8501.log 2>&1 < /dev/null &
```

## 5) Run live bidding simulation from the application

Primary demo path:

```bash
# open in browser
echo "http://<droplet-ip>:8016/terminal/"
```

Then in **Bid Requests**:

1. click **Run demo now** (continuous request stream starts),
2. watch bids land live,
3. click **Stop demo** when done.

Fallback (CLI-generated stream if you need it):

```bash
cd /root/appbid
while true; do
python3 - <<'PY'
import json, random, urllib.request
base='http://127.0.0.1:8016/apps'
payload={
  'dealer_id': f'DEMO-{random.randint(100,999)}',
  'applicant_fico': random.randint(640,810),
  'loan_amount': str(random.randint(18000,65000)),
  'vehicle_type': random.choice(['new','used','ev']),
  'term_months': random.choice([48,60,72,84]),
  'state': random.choice(['CA','TX','FL','NY','WA','AZ']),
  'dealer_reserve_bps': random.choice([125,150,175,200,225]),
}
req=urllib.request.Request(base,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(req, timeout=10) as r:
    print('created', json.loads(r.read().decode())['id'])
PY
sleep 1
done
```

## 6) Performance commands for web-console narration

### A. Real-time GPU utilization + VRAM + power + temp

```bash
watch -n 1 'rocm-smi --showuse --showmeminfo vram --showtemp --showpower'
```

### B. App-level GPU metrics endpoint (same numbers used by UI GPU tab)

```bash
watch -n 2 'curl -s http://127.0.0.1:8016/gpu/metrics'
```

### C. Throughput/latency benchmark on vLLM endpoint

```bash
cd /root/appbid
.venv/bin/python scripts/benchmark_vllm_stdlib.py \
  --url http://127.0.0.1:8001/v1 \
  --model Qwen/Qwen2.5-7B-Instruct \
  --requests 40 \
  --concurrency 8 \
  --max-tokens 96
```

### D. Show live bid volume growth

```bash
watch -n 2 'curl -s "http://127.0.0.1:8016/treasury"'
```

### E. Tail operational logs while demo runs

```bash
tail -f /root/appbid/runner.log /root/appbid/marketplace-8016.log
```

## 7) Optional: open ports for browser access

If networking policy allows direct browser access:

- Streamlit UI: `http://<droplet-ip>:8501`
- Marketplace API: `http://<droplet-ip>:8016`

