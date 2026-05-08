# Demo Path (Fri/Sat) — AppBid + AMD FP8

This is the canonical demo path to use for Friday/Saturday.

It prioritizes reliability for judging/demo while preserving the AMD FP8 inference story.

## Goal

Show a clean, repeatable flow:

1. FP8 model serves on MI300X
2. Multiple lender agents bid on one request
3. Dealer accepts top bid
4. Settlement succeeds (stub mode)

## Why settlement is stubbed

Live CDP settlement is currently blocked by spendability/faucet constraints in the active CDP project.
To keep the end-to-end product demo unblocked, use `SETTLEMENT_MODE=stub` for demo runs.

## Known-good runtime topology

- vLLM endpoint: `http://127.0.0.1:8001/v1`
- Marketplace + terminal UI: `http://127.0.0.1:8016` and `/terminal/`
- Runner (demo): points to `:8016`

## Start commands (on droplet)

From `/root/appbid`:

```bash
# 1) Marketplace in demo-safe mode (no insertion fee + stub settlement)
nohup env INSERTION_FEE_USDC=0 SETTLEMENT_MODE=stub PAYMENT_MODE=stub X402_FACILITATOR_MODE=local \
  .venv/bin/python -m uvicorn marketplace.server:app \
  --host 0.0.0.0 --port 8016 \
  > /root/appbid/marketplace-8016.log 2>&1 &

# 2) Runner against demo marketplace
nohup env MARKETPLACE_HOST=127.0.0.1 MARKETPLACE_PORT=8016 \
  PAYMENT_MODE=stub \
  VLLM_URL=http://127.0.0.1:8001/v1 \
  VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct \
  LORA_MODE=prompt \
  .venv/bin/python -m agents.runner \
  > /root/appbid/runner.log 2>&1 &
```

## Demo verification command

```bash
cd /root/appbid
env MARKETPLACE_HOST=127.0.0.1 MARKETPLACE_PORT=8016 \
  .venv/bin/python scripts/e2e_test.py
```

## Live stream demo path (recommended)

Use the in-app continuous generator:

1. open `http://<droplet-ip>:8016/terminal/`
2. go to **Bid Requests**
3. click **Run demo now**
4. click **Stop demo** to end the stream

## Simulated x402 + simulated settlement (full product-shape E2E)

If you want x402 middleware exercised while still avoiding real chain spend:

```bash
# marketplace (x402 on, settlement stubbed)
nohup env INSERTION_FEE_USDC=0.10 X402_FACILITATOR_MODE=local SETTLEMENT_MODE=stub \
  .venv/bin/python -m uvicorn marketplace.server:app \
  --host 127.0.0.1 --port 8016 \
  > /root/appbid/marketplace-8016.log 2>&1 &

# runner (synthetic payment envelopes)
nohup env MARKETPLACE_HOST=127.0.0.1 MARKETPLACE_PORT=8016 PAYMENT_MODE=stub \
  VLLM_URL=http://127.0.0.1:8003/v1 VLLM_MODEL=/app/models/qwen2.5-72b-ptpc-fp8-vllm \
  LORA_MODE=prompt .venv/bin/python -m agents.runner \
  > /root/appbid/runner-fp8-8016.log 2>&1 &

# smoke test
env MARKETPLACE_HOST=127.0.0.1 MARKETPLACE_PORT=8016 .venv/bin/python scripts/e2e_test.py
```

## Expected success markers

- `got N bids` (typically >= 2)
- `HTTP/1.1 200 OK` on `/accept`
- `dealer_payout_tx   0xstubsettle00...`
- `marketplace_cut_tx 0xstubsettle01...`
- `reserve_tx         0xstubsettle02...`
- `E2E PASS`

## Optional cleanup (after demo)

If you want to keep only the demo stack alive, keep:

- vLLM on `8001`
- marketplace on `8016`
- runner on `8016`

## Other planned items (parked, not dropped)

These were in the broader plan and are intentionally deferred:

1. AMD profiling evidence capture (`rocprof`/`omniperf` + charts)
2. Optimum-AMD integration into LoRA training path behind a runtime flag
3. AITER backend verification evidence from vLLM logs for deck artifacts

Reference plan docs:

- `../plans/HACKATHON_PLAN.md`
- `../plans/REST_OF_WEEK_AMD_AI_PLAN_2026-05-07_to_2026-05-09.md`
