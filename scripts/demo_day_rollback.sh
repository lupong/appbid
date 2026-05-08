#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/appbid"
cd "$ROOT_DIR"

echo "[demo-rollback] fast recovery start"
echo "[demo-rollback] restarting marketplace + runner"
bash scripts/demo_day_start.sh

echo "[demo-rollback] verifying latest open request has bid path"
python3 - <<'PY'
import json
import urllib.request

base = "http://127.0.0.1:8016"
with urllib.request.urlopen(base + "/apps?status=open", timeout=10) as r:
    apps = json.loads(r.read().decode())

if not apps:
    print("no open requests yet (this is acceptable)")
else:
    latest = apps[0]["id"]
    with urllib.request.urlopen(f"{base}/apps/{latest}/bids", timeout=10) as r:
        bids = json.loads(r.read().decode())
    print(f"latest_open={latest} bids={len(bids)}")

print("rollback complete")
PY
