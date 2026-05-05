# Today — T-5 · Tuesday May 5, 2026

> Historical planning note: this file is the original morning execution plan.
> Actual outcomes and blockers are captured in `TODAY_2026-05-05_RECAP.md`
> and `AMD_DEV_CLOUD_DEVEX_NOTES.md`.
>
> **Goal of today:** Droplet is alive, repo is on GitHub, wallets are funded, the 72B base model serves a `curl` from vLLM, and `lora_training/data/*.jsonl` exists for all 5 lenders. **No LoRA training today** — that's tomorrow.
>
> **One-line success criterion:** *Tomorrow morning I can wake up, SSH into the droplet, run `python lora_training/train_all.py --teacher=llm` and walk away — there is nothing left to set up.*

---

## How to use this file

There are **two parallel tracks**: one runs on the **laptop** (wallets, GitHub, code), the other runs on the **droplet** (Docker, vLLM, model download). Each block tells you which.

Order is staggered — start the **slow async things first** (droplet request, model download) so they complete in the background while you do the small synchronous steps. Don't read this top-to-bottom; **start blocks A and B simultaneously**.

```
LAPTOP TRACK:        Block B → Block C → Block D
                     (CDP creds) (GitHub) (Wallets)
                          ↓                     ↓
DROPLET TRACK:   Block A → Block E → Block F → Block G → Block H → Block I
                 (req)    (images) (model DL) (vLLM)   (data)    (tests)
```

---

## Block A · Request the MI300X droplet (do this *first*, then walk away from it)

**Track:** Droplet request portal · **Time:** 5 min active, then async wait

1. Log in to AMD Developer Cloud.
2. Provision an **MI300X 192 GB** instance with the **`rocm/vllm:latest`** base image. (Per `infra/README.md`: do **not** start from bare Ubuntu — the ROCm driver/userland match has to be exact.)
3. Add your SSH key during provisioning so you can connect without a password.
4. Note the IP and instance name.

**If queued:** that's expected. Do not wait. Move to Block B.

**Acceptance:** instance is in "provisioning" or "running" state.

**Fallback if AMD Developer Cloud is unavailable today:** RunPod and Modal both have MI300X instances; the architecture is portable since it's all ROCm + vLLM. Don't burn >30 min trying to get into one provider — pivot.

---

## Block B · CDP credentials + `.env` (laptop)

**Track:** Laptop · **Time:** 10 min · **Depends on:** nothing

1. Go to https://portal.cdp.coinbase.com → **API Keys** → **Create API Key** → Server key.
2. Download the JSON. Pull `name` and `privateKey` out of it.
3. In the repo:

   ```bash
   cd ~/Developer/appbid
   cp .env.example .env
   ```

4. Open `.env` and fill in **only these two for now**:

   ```
   CDP_API_KEY_NAME="organizations/.../apiKeys/..."
   CDP_API_KEY_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"
   ```

   (Leave `MARKETPLACE_WALLET_ID` and `RESERVE_WALLET_ID` empty — Block D writes them.)

5. Set `LORA_MODE=prompt` for today (you don't have adapters yet; the marketplace + tests pass without them).

**Acceptance:** `python -c "from shared.config import get_settings; s = get_settings(); print(bool(s.cdp_api_key_name), bool(s.cdp_api_key_private_key))"` prints `True True`.

**Anti-pattern:** Do **not** commit `.env`. `.gitignore` already excludes it; double-check before Block C.

---

## Block C · `git init` + push public repo to GitHub (laptop)

**Track:** Laptop · **Time:** 15 min · **Depends on:** Block B (so `.env` exists and is gitignored before any commit)

The repo is not yet a git repository. Lablab requires a public GitHub URL on the submission form.

```bash
cd ~/Developer/appbid

# 1. Verify nothing dangerous gets committed.
git init
git status | grep -E '\.env$|wallets\.json|adapter_model'    # should be empty

# 2. First commit.
git add -A
git diff --cached --name-only | grep -E '^\.env$|wallets\.json'  # MUST be empty
git commit -m "Initial commit: Credit App+ — reverse-auction marketplace for auto loan bid requests"

# 3. Create the GitHub repo (one of these):
gh repo create appbid-plus --public --source=. --remote=origin --push
# OR via the web UI, then:
# git remote add origin git@github.com:andrewpongco/appbid-plus.git
# git branch -M main
# git push -u origin main

# 4. Tag this state.
git tag v0.1-presubmission -m "Pre-LoRA submission state — code complete, no adapters yet"
git push --tags
```

**Acceptance:** `gh repo view --web` opens the public repo and the README renders. `https://github.com/andrewpongco/appbid-plus` (or whatever name) is reachable from a logged-out browser.

**Sanity check before pushing:** `git ls-files | grep -E '\.env$|wallets\.json|adapter_model'` must return zero rows. If it returns anything, **stop, fix .gitignore, `git rm --cached <file>`, recommit before pushing.**

---

## Block D · Create + fund wallets (laptop)

**Track:** Laptop · **Time:** 10–20 min (faucet drips can be slow) · **Depends on:** Block B

```bash
cd ~/Developer/appbid
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 8 wallets: dealer, marketplace, reserve, 5 lenders.
.venv/bin/python -m scripts.setup_wallets
# Writes wallets.json. Refuses to overwrite — if you ever need a fresh
# setup, `rm wallets.json` first.

# Drip USDC into all 8 from the CDP testnet faucet.
.venv/bin/python -m scripts.fund_wallets
```

After `setup_wallets.py` runs, **paste the marketplace and reserve wallet IDs back into `.env`:**

```
MARKETPLACE_WALLET_ID=<from wallets.json "marketplace">
RESERVE_WALLET_ID=<from wallets.json "reserve">
```

**Acceptance:**
- `wallets.json` exists with 8 wallet IDs.
- `fund_wallets.py` printed `OK tx=0x...` for at least 6 of 8 wallets (the CDP faucet sometimes throttles; one or two retries is fine).
- Open one of the addresses on https://sepolia.basescan.org and see USDC balance > 0.

**Backup:** copy `wallets.json` to a second location *outside the repo* (e.g. iCloud or a 1Password Secure Note). If you delete it, the wallets still exist on Base Sepolia but you've lost the IDs that map them to dealer/marketplace/etc., and you'll have to recreate everything.

---

## Block E · Pull rocm/vllm and rocm/pytorch images on the droplet

**Track:** Droplet (in tmux/screen — NEVER do this in a foreground SSH that might disconnect) · **Time:** 20–40 min, async · **Depends on:** Block A complete

```bash
ssh ubuntu@<droplet-ip>
sudo apt-get update && sudo apt-get install -y tmux htop
tmux new -s setup     # critical — your work survives SSH drops

# Inside tmux:
docker pull rocm/vllm:latest        # ~30 GB
docker pull rocm/pytorch:latest     # ~25 GB

# Verify GPU visibility (run inside the rocm/pytorch image, NOT bare host):
docker run --rm --device=/dev/kfd --device=/dev/dri --group-add=video \
  -v $PWD:/workspace -w /workspace rocm/pytorch:latest \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count(), [torch.cuda.get_device_properties(i).name for i in range(torch.cuda.device_count())])"
```

**Acceptance:** the last line prints `True 1 ['AMD Instinct MI300X']`. If it doesn't, stop and fix — every later block depends on the GPU being visible inside the container.

**Anti-pattern:** *do not* run `pip install torch` on the bare host or pull a non-AMD torch wheel. The rocm/* images come with the right ROCm-compiled torch. Touching it breaks vLLM.

---

## Block F · Download Qwen2.5-72B-Instruct on the droplet

**Track:** Droplet (in tmux) · **Time:** 30–60 min, async · **Depends on:** Block E

```bash
# Still in tmux on droplet:
git clone https://github.com/andrewpongco/appbid-plus.git
cd appbid-plus

# HF download — runs on host, populates ~/.cache/huggingface so all containers see it.
pip install -U huggingface_hub
huggingface-cli download Qwen/Qwen2.5-72B-Instruct \
  --local-dir ~/models/Qwen2.5-72B-Instruct
```

While the model downloads (you can disconnect tmux and come back):

- Copy your `.env` from laptop to droplet — `scp ~/Developer/appbid/.env ubuntu@<ip>:~/appbid-plus/.env`
- Copy `wallets.json` too — `scp ~/Developer/appbid/wallets.json ubuntu@<ip>:~/appbid-plus/wallets.json`

**Acceptance:** `du -sh ~/models/Qwen2.5-72B-Instruct` shows ~145 GB and `ls` shows `*.safetensors` files (10–20 of them).

---

## Block G · Smoke-test vLLM with the base model only (no LoRA)

**Track:** Droplet · **Time:** 15 min · **Depends on:** Block F

This is the moment the AMD-specific path gets exercised for the first time. Failing here is *much* better than failing tomorrow in the middle of LoRA training.

```bash
# In a fresh tmux pane on the droplet:
docker run --rm -it \
  --device=/dev/kfd --device=/dev/dri --group-add=video \
  --shm-size 16G \
  -p 8000:8000 \
  -v ~/models:/models \
  -v $PWD:/app -w /app \
  rocm/vllm:latest \
  vllm serve /models/Qwen2.5-72B-Instruct \
    --port 8000 \
    --dtype bfloat16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.92 \
    --max-num-seqs 64 \
    --tensor-parallel-size 1
```

vLLM takes a few minutes to load the weights. When it logs `Uvicorn running on 0.0.0.0:8000`, in a **second pane**:

```bash
# Sanity 1: it answers /v1/models
curl -s http://localhost:8000/v1/models | jq

# Sanity 2: it answers a chat completion
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/Qwen2.5-72B-Instruct",
    "messages": [{"role":"user","content":"Reply with exactly: ack"}],
    "max_tokens": 5,
    "temperature": 0
  }' | jq -r '.choices[0].message.content'
```

In a **third pane**, watch the GPU:

```bash
bash infra/monitor.sh
```

**Acceptance:**
- `/v1/models` returns the model name.
- The completion returns something containing `ack`.
- `rocm-smi` shows VRAM usage ~145 GB and gfx_activity > 0% during the request.

**If vLLM OOMs:** lower `--gpu-memory-utilization` to 0.85 and `--max-num-seqs` to 32 — you have plenty of headroom on a 192 GB GPU; this should not happen, and if it does it usually means another container is also holding VRAM. `docker ps` and kill stragglers.

**If `/v1/models` returns but completions hang:** check `--max-num-seqs` is set; vLLM with `--enable-lora` flags removed should not hang. If it still hangs, drop `--max-model-len` to 4096.

---

## Block H · Generate LoRA training data with the LLM teacher

**Track:** Droplet · **Time:** 1.5–3 h, async (1500 teacher calls @ ~5 sec each, but vLLM batches concurrent calls efficiently) · **Depends on:** Block G running, vLLM healthy

This produces the JSONL files that tomorrow's training run consumes. **Critical:** vLLM must keep running through this whole step — `LLMTeacher` calls into `settings.vllm_url` (= `http://localhost:8000/v1`), which is the base model you just brought up.

```bash
# In a new pane, with vLLM still running in another:
docker exec -it <vllm-container> bash    # OR a separate rocm/pytorch container with the repo mounted
cd /app
pip install -e ".[dev]"

# Sanity check first — stub teacher, no GPU calls. Should walk all 5 lenders in <30s.
python lora_training/train_all.py --dry-run

# Then the real run with the LLM teacher (vLLM serving the base model).
python lora_training/train_all.py --teacher=llm
```

**Note:** `train_all.py` defaults to `--teacher=stub`, which produces *useless* training data. The `--teacher=llm` flag is mandatory for real datasets. Re-read the warning in `lora_training/synthetic_data.py:StubTeacher.__doc__` if you forget why.

While it runs:
- `tail -f` the train_all output. Each lender prints `wrote 300 examples -> ...`.
- Some teacher calls will fail (JSON parse errors, vLLM hiccups) — `generate_training_examples` drops failed rows silently. As long as each lender's row count is ≥250, you have enough signal. If any lender falls below 200, regenerate just that one with `--n 400`.

**Acceptance:**
```bash
ls -la lora_training/data/
# Expect: prime-bank.jsonl, mid-market.jsonl, subprime.jsonl, used-only.jsonl, ev-captive.jsonl
wc -l lora_training/data/*.jsonl
# Expect: 250-300 lines each.
```

Spot-check one row to confirm the teacher actually reflected the rate sheet:

```bash
head -1 lora_training/data/subprime.jsonl | jq '.messages[-1].content | fromjson'
# Should show high APR (e.g. apr_bps=1800+) for low-FICO requests — that's
# the subprime rate sheet showing through. If every lender's first row
# looks identical, the teacher isn't seeing the rate sheet — abort and
# debug the LLMTeacher system prompt.
```

---

## Block I · Tests pass + EOD standup

**Track:** Droplet (or laptop, your call) · **Time:** 15 min · **Depends on:** Block H

```bash
cd ~/appbid-plus
.venv/bin/pytest tests/ -v 2>&1 | tee test_run_t5.log
```

Existing tests don't touch the GPU or chain — they should pass on either machine.

**Acceptance:** all tests green. If anything fails, *triage now* — these tests covered the last design iteration; a regression today is a regression you don't want surfacing tomorrow morning during LoRA training.

Then write **`STANDUP.md`** in the repo:

```markdown
# T-5 EOD · 2026-05-05

✅ **Done:**
- Droplet up (MI300X 192 GB visible to torch)
- Repo public on GitHub at <url>
- 8 wallets created + funded on Base Sepolia
- Qwen2.5-72B serving on vLLM; sanity-curl returned "ack"
- 5 LoRA training datasets generated (~300 rows each), spot-check shows lender-distinct policies
- All N tests passing

⚠️ **Slipped:**
- (anything)

🎯 **Tomorrow's one thing:**
Train all 5 LoRAs end-to-end and re-launch vLLM with `infra/start_vllm.sh` — multi-LoRA serving working by EOD T-4.
```

Commit and push:

```bash
git add STANDUP.md
git commit -m "T-5 EOD: droplet up, base serving, training data ready"
git push
```

---

## What is *not* on today's list (and why)

- **LoRA training itself.** Tomorrow. Today is data + bring-up.
- **`x402_middleware.py` `eth_getTransactionReceipt` fix.** Thursday (T-3). Don't pre-empt.
- **Coinbase Smart Wallet batched call.** Thursday or cut.
- **Streamlit Cloud public deploy.** Saturday (T-1). Don't deploy a half-broken app early.
- **Slide deck, video, cover image.** Friday (T-2). Don't fight Keynote tonight.
- **Anything from `CONTEXT.md § Inputs from other threads — unmerged`.** All cut.

If you find yourself in any of these tonight, stop and re-read the success criterion at the top of this file.

---

## Hard time budget for today

| Block | Wall clock | Active work |
|---|---|---|
| A · Droplet request | 0 (async) | 5 min |
| B · CDP creds | 0:00–0:10 | 10 min |
| C · GitHub | 0:10–0:25 | 15 min |
| D · Wallets | 0:25–0:45 | 10 min active + 10 min faucet wait |
| E · Docker images | 0:45–1:30 | 5 min active + 30 min pull |
| F · Model download | 1:30–2:30 | 5 min active + 45 min download |
| G · vLLM smoke test | 2:30–2:50 | 20 min |
| H · Training data gen | 2:50–5:00 | 5 min active + 2 h async |
| I · Tests + standup | 5:00–5:30 | 30 min |
| **Total** | **~5.5 h elapsed** | **~2 h hands-on** |

If you're at hour 4 and still on Block E, **stop and re-plan**. The most likely thing that's gone wrong is droplet provisioning — pivot to a different MI300X provider (RunPod / Modal) before sunset.
