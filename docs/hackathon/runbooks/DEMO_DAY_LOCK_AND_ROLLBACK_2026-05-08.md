# Demo-Day Lock, Checklist, and 2-Min Rollback (2026-05-08)

This is the operator-facing runbook for recording and live demo sessions.

It is optimized for:

- continuous bid stream from terminal UI (`Run demo now` / `Stop demo`),
- live GPU telemetry in app and console,
- deterministic restart/rollback if anything degrades.

## 1) One Command Sheet (copy/paste)

Run on droplet web console from `/root/appbid`.

### A. Start/refresh all services (safe restart)

```bash
cd /root/appbid
bash scripts/demo_day_start.sh
```

### B. Verify service health

```bash
cd /root/appbid
python3 - <<'PY'
import urllib.request
for u in [
    "http://127.0.0.1:8001/v1/models",
    "http://127.0.0.1:8016/healthz",
    "http://127.0.0.1:8016/gpu/metrics",
]:
    with urllib.request.urlopen(u, timeout=10) as r:
        print(u, r.status, r.read().decode()[:220])
PY
```

### C. Open demo UI

- `http://<droplet-ip>:8016/terminal/`
- go to **Bid Requests**
- click **Run demo now**

### D. Live narration commands (web console)

```bash
watch -n 1 'curl -s http://127.0.0.1:8016/gpu/metrics'
```

```bash
tail -f /root/appbid/runner.log /root/appbid/marketplace-8016.log
```

```bash
watch -n 1 'rocm-smi --showuse --showmeminfo vram --showtemp --showpower'
```

## 2) Pre-Demo Checklist

### T-15 minutes

- `git status` clean enough for demo (or known local changes only).
- `bash scripts/demo_day_start.sh` completes without errors.
- `curl http://127.0.0.1:8016/healthz` returns `{"status":"ok"}`.
- `curl http://127.0.0.1:8016/gpu/metrics` returns `available: true`.
- `ps -ef | grep agents.runner` shows runner process.

### T-5 minutes

- hard-refresh terminal UI (`Cmd+Shift+R`).
- verify lender names render as friendly names (not raw IDs).
- click **Run demo now**, confirm request count increases.
- confirm bids are arriving on latest requests.
- keep backup tab open at `http://<droplet-ip>:8016/terminal/`.

### T-1 minute

- start console watch command for GPU metrics.
- start log tail command in second pane.
- stop all unrelated heavy jobs in other terminals.

## 3) During Demo

Preferred sequence:

1. show `Bid Requests` page,
2. click **Run demo now**,
3. show requests/bids streaming,
4. show in-app GPU line (util/power),
5. show console `curl /gpu/metrics` or `rocm-smi`,
6. click **Stop demo**.

If load seems low, run this in console while stream is active:

```bash
python3 - <<'PY'
import json, random, urllib.request
for _ in range(8):
    payload={
      "dealer_id": f"BOOST-{random.randint(100,999)}",
      "applicant_fico": random.randint(640,810),
      "loan_amount": str(random.randint(18000,65000)),
      "vehicle_type": random.choice(["new","used","ev"]),
      "term_months": random.choice([48,60,72,84]),
      "state": random.choice(["CA","TX","FL","NY","WA","AZ"]),
      "dealer_reserve_bps": random.choice([125,150,175,200,225]),
    }
    req=urllib.request.Request("http://127.0.0.1:8016/apps",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        print("created", json.loads(r.read().decode())["id"])
PY
```

## 4) 2-Min Rollback Plan (if stream freezes)

Run:

```bash
cd /root/appbid
bash scripts/demo_day_rollback.sh
```

Expected outcome (<2 minutes):

- marketplace restarted on `8016`,
- runner restarted and reconnects to local vLLM endpoint,
- health endpoints return 200,
- UI refresh restores live stream.

Then:

- hard refresh browser,
- click **Run demo now** again.

## 5) Post-Demo Cleanup

```bash
cd /root/appbid
pkill -f "python -m agents.runner" || true
pkill -f "uvicorn marketplace.server:app" || true
docker rm -f appbid-vllm >/dev/null 2>&1 || true
```

## 6) Security Hygiene (recording-safe)

- never print `.env` to shared screen,
- do not echo `DO_API_TOKEN`, `CDP_*`, or wallet secret material,
- avoid opening `wallets.json` during recording,
- prefer health/perf endpoints and logs that contain no credentials.
