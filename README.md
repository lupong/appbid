# Credit App+

A reverse-auction marketplace for auto-loan **bid requests**. A dealer
publishes a PII-free structural proposal (dealer-pulled FICO, vehicle, term,
amount, state, reserve — no name, SSN, or address); five autonomous lender
agents — each backed by its own fine-tuned **LoRA adapter** on a shared
Qwen2.5-72B base served by vLLM on the AMD MI300X — underwrite the request
and submit competitive bids. Each bid pays an X402 insertion fee in USDC on
Base Sepolia. When the dealer accepts a winning bid, the marketplace
executes a three-way revenue split (dealer / marketplace / reserve)
through Coinbase CDP wallets. Identity verification, fresh credit pulls,
and KYC happen out-of-band at the funding stage with the winning lender,
not at the marketplace boundary. Built for the AMD x Lablab.ai Developer
Hackathon, May 2026.

## Architecture

```
                     +-------------------------------+
                     |   Streamlit Dealer UI         |
                     |   publish | rank | accept     |
                     |   "Run Concurrency Demo"      |
                     +---------------+---------------+
                                     | HTTP
                     +---------------v---------------+
                     |   FastAPI Marketplace         |
                     |   /apps   /bids   /accept     |
                     |   X402 middleware | ranker    |
                     |   SQLite ledger               |
                     +--+---------------+------------+
                        | poll          | X402 insertion fee
                        |               | + 3-way rev-split
        +---------------v-+             +v------------------+
        | 5 Lender Agents |             | Base Sepolia      |
        | async  CDP      |             | USDC | CDP wallets|
        +---------+-------+             +-------------------+
                  | OpenAI-compat (vLLM, model=<lora_alias>)
        +---------v-------+
        | AMD MI300X 192GB|
        | Qwen2.5-72B BF16|
        |  + 5 rank-16    |
        |    LoRA adapters|
        +-----------------+
```

### Why a 192 GB GPU is required

The default base model is `Qwen/Qwen2.5-72B-Instruct` in BF16 (~144 GB of
weights). vLLM serves it alongside 5 LoRA adapters (rank 16, BF16 — a few
hundred MB each) and reserves the rest for the KV cache that powers
continuous batching across all 5 lender agents. **The AMD MI300X (192 GB
HBM3) is the smallest single GPU that fits this combination**; a single
H100 80 GB cannot. For local iteration without a real GPU, set
`VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct` and `LORA_MODE=prompt`.

### Bid generation, not credit underwriting

What this marketplace models is **bid generation / pricing**, not the
regulated credit decision. A bid is conditional — "if you accept this and
the application checks out at funding, I'll fund $25k at 5.49% with these
stips." The actual credit decision happens later, at the winning lender's
funding desk, after the dealer transmits the full PII-bearing retail
installment contract out-of-band. That's where adverse-action notices,
ECOA reason codes, fair-lending review, and SR 11-7 model governance
live — at *funding*, not at the bid step. The marketplace itself never
holds consumer PII; losing lenders never see it at all.

### Single-stage LoRA underwriting (no Python policy engine)

A lender's policy is exactly one piece of data: its **free-text rate sheet**
(`rate_sheet_text` on `LenderProfile`). Paste a published indirect-auto rate
sheet — FICO bands, term tiers, LTV ladder, exclusions, dealer reserve,
stipulation rules, anything else — verbatim. There is no policy engine, no
subscribed-criteria filter, no pricing-strategy knobs. **Every bid decision
(including out-of-box declines) is the LoRA-fine-tuned underwriter's
call.**

The rate sheet plays two roles, both of which fall out of the same text:

- **Training seed.** `lora_training/synthetic_data.py` runs a teacher LLM
  with `rate_sheet_text` inlined as a system prompt to label synthetic bid
  requests; the LoRA learns to imitate those labels. After training, the
  rate sheet is "in the weights" and at inference time the LoRA sees only
  the bid request + the JSON decision schema.
- **Inference fallback.** With `LORA_MODE=prompt` the underwriter sends
  `rate_sheet_text` directly to the base model as a system prompt — same
  text, used at inference instead of training. The demo degrades
  gracefully if multi-LoRA serving on ROCm misbehaves.

Two modes selected by `LORA_MODE`:

- `multi` (default) — vLLM serves base + 5 LoRAs; agent requests routed by
  `lora_alias` (`stcu_retail_auto`, `unitus_community_cu`,
  `exeter_finance`, `family_savings_cu`, `crouse_federal_cu`). System prompt at inference time is the bare decision
  schema — the rate sheet is in the LoRA weights. Production demo path.
- `prompt` — fallback. Disables LoRA, sends `rate_sheet_text` as the
  system prompt against the base model.

## Setup

```bash
# 1. Install runtime deps
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 2. Configure
cp .env.example .env       # then fill in CDP_API_KEY_NAME, CDP_API_KEY_PRIVATE_KEY, VLLM_URL

# 3. Create + fund CDP wallets on Base Sepolia
.venv/bin/python -m scripts.setup_wallets   # writes wallets.json
.venv/bin/python -m scripts.fund_wallets    # USDC drip from CDP faucet

# 4. (On the AMD MI300X droplet) train LoRAs and start vLLM with multi-LoRA serving
#    — see lora_training/README.md for details.
.venv/bin/pip install -r requirements-train.txt
.venv/bin/python lora_training/train_all.py            # ~3-5h for 5 lenders
infra/devcloud.sh serve dev                  # safer defaults for iterative bring-up
# or: infra/devcloud.sh serve demo           # higher-throughput single-instance profile

# optional quick perf probe while vLLM is running
infra/devcloud.sh benchmark dev
infra/devcloud.sh benchmark demo

# 5. Run the marketplace, lender runner, and dealer UI in three terminals
.venv/bin/uvicorn marketplace.server:app --port 8001
.venv/bin/python -m agents.runner
.venv/bin/streamlit run ui/dealer_app.py

# 6. (Optional) seed 50 synthetic bid requests
.venv/bin/python -m scripts.seed_apps

# 7. End-to-end smoke test (publish 1 request, accept top bid, verify rev-split)
.venv/bin/python -m scripts.e2e_test

# 8. Hero-shot demo: 50 bid requests in ~10s, all 5 lenders bidding concurrently
.venv/bin/python -m scripts.concurrency_demo
#    or: click "Run Concurrency Demo" in the Streamlit sidebar.
```

## Running on AMD MI300X (AMD Developer Cloud)

Designed for a single AMD Instinct MI300X (192 GB HBM3).

### Why AMD

- 72B base + 5 LoRA adapters fit on one GPU. Multi-GPU only on H100.
- All inference on a single device — no tensor parallelism, no cross-device
  KV-cache traffic.
- Fully open stack: ROCm, vLLM, Qwen2.5 weights, PEFT.

### Setup

1. Spin up the MI300X droplet using the **`rocm/vllm`** or **`rocm/pytorch`**
   base image. Don't bootstrap ROCm yourself on bare Ubuntu.
2. Clone repo. Copy `.env.example` → `.env`. Fill in CDP keys + wallet IDs.
3. Confirm GPU visibility: `python scripts/check_gpu.py` (run in the
   `rocm/pytorch` container).
4. Train LoRAs (~3–5 h, one time): `python lora_training/train_all.py`.
5. Start vLLM: `infra/devcloud.sh serve dev` (or `infra/devcloud.sh serve demo`).
   The demo profile raises KV-cache allocation/concurrency (`gpu-memory-utilization`
   and `max-num-seqs`) for MI300X throughput.
6. Start marketplace: `uvicorn marketplace.server:app --port 8001 --host 0.0.0.0`.
7. Start lender agents: `python -m agents.runner`.
8. Start dealer UI: `streamlit run ui/dealer_app.py`.
9. Run the concurrency demo: `python -m scripts.concurrency_demo`.

The `infra/Dockerfile.serving` and `infra/Dockerfile.training` images
package these workflows; see [infra/README.md](infra/README.md).

### Monitoring

In a side terminal: `bash infra/monitor.sh` to watch GPU utilization,
VRAM, temp, and power live (drives `rocm-smi` under `watch`). The
concurrency demo also captures a programmatic GPU snapshot via
`shared/gpu_metrics.py` (uses `amdsmi`) and folds it into the live panel.

## Tests

```bash
.venv/bin/pytest tests/ -v
```

Unit + integration tests covering model validation, ranker math, win-premium
splits, X402 paywall + payment-header verification, the lender's
underwriter-mediated approve/decline flow (no Python pre-filter — every
decision is the LLM's call, mocked in tests), and the full publish → bid →
accept settlement flow with the X402 middleware exercised end-to-end
(settlement executor stubbed so tests don't touch chain).

## Project layout

```
shared/        models · config · async DB · CDP wallet wrappers · rich logger
data/          5 lender profiles (each = a free-text rate sheet) · 50-app generator
marketplace/   FastAPI server · routes (apps/bids/settle/treasury) · ledger ·
               ranker · X402 middleware · settlement executor
agents/        underwriter (vLLM/OpenAI client, LORA_MODE-aware) · lender ·
               payment provider · runner
lora_training/ synthetic_data (rate-sheet → teacher → training pairs) ·
               train_lora · train_all · run-on-droplet README
infra/         start_vllm.sh — vLLM launcher with multi-LoRA flags
ui/            Streamlit dealer dashboard (with concurrency-demo button) ·
               ledger inspector
scripts/       setup_wallets · fund_wallets · seed_apps · e2e_test ·
               concurrency_demo
tests/         test_models · test_marketplace · test_lender
```

## Build steps

The project is built bottom-up; each step's acceptance gate must pass before
the next starts.

| Step | Description | Acceptance |
|------|-------------|------------|
| 1–7  | Bootstrap → shared → data → marketplace (no payment) → lender agents → X402 insertion fee → win-premium + rev-split | covered by existing 66 tests |
| 7.5  | LoRA training pipeline (`lora_training/`) — synthetic data + train_lora + train_all + requirements-train.txt | `python -m lora_training.train_all --dry-run` walks all 5 profiles, generates JSONL, prints plan, no GPU touched |
| 7.6  | Multi-LoRA serving + adapter routing — `infra/start_vllm.sh`, `LORA_MODE` switch in Underwriter | with `LORA_MODE=multi`, vLLM logs show requests routed by adapter alias; with `LORA_MODE=prompt`, same flow works without LoRA |
| 8    | Dealer Streamlit dashboard | publish, rank, accept all work in browser |
| 9    | Scripts (seed, e2e) | `python -m scripts.e2e_test` passes |
| 9.5  | Concurrency demo + Streamlit button | `python -m scripts.concurrency_demo` publishes 50 bid requests in ≤10s, captures bids from matching lenders, prints live + final summary |
| 10   | Tests | full suite green |

## Notes / deviations from the original spec

- **Python**: spec said 3.11; system Python on the build host is 3.14, so
  `requires-python = ">=3.11"`. Code is forward-compatible.
- **Model bump**: default base is now `Qwen/Qwen2.5-72B-Instruct` (was 7B).
  The 7B remains supported via `VLLM_MODEL` for fast local iteration.
- **Bid request, not credit application.** The marketplace shops PII-free
  structural proposals (`BidRequest`). The original spec called these
  "credit applications" — that's misleading because the regulated credit
  decision (PII, KYC, fresh credit pull, adverse-action notices) happens
  later at the winning lender's funding desk, not at the marketplace
  boundary. URL paths are kept at `/apps/...` for backward compatibility
  with the original spec; internally the type is `BidRequest`.
- **Single-stage LoRA underwriting** (replaces both the original
  prompt-per-lender design *and* the earlier hybrid policy-engine + LoRA
  refinement design). A lender is described by exactly one piece of
  data — its `rate_sheet_text` — which seeds LoRA training and serves as
  the system prompt in `LORA_MODE=prompt` fallback. There is no Python
  policy engine and no subscription pre-filter; every bid decision is
  the LoRA's call.
- **`Bid` schema**: the spec listed `bid_price_usdc` but described it as "the
  rate/APR offered to the customer" — split into `apr_bps` (int) and
  `max_amount_usdc` (Decimal) to match the underwriter's `Decision` output
  and give the ranker both inputs.
- **Profile IDs**: existing kebab-case ids (e.g. `prime-bank`) are preserved
  to keep tests stable; LoRA adapter aliases now use lender-specific names
  (e.g. `stcu_retail_auto`). The mapping lives on each profile via
  `lora_alias`.
- **Extra files**: `shared/logging.py` (rich logger setup, kept separate from
  `config.py` per "one concern per file"), `agents/payment.py` (X402 payment
  provider protocol), `marketplace/settler.py` (split math + executor),
  `marketplace/routes/treasury.py` (dashboard aggregates).
- **X402 verification**: middleware decodes the X-PAYMENT header, format-checks
  the tx hash, and verifies declared amount matches the configured insertion
  fee. Full on-chain receipt verification via `eth_getTransactionReceipt`
  against `BASE_SEPOLIA_RPC` is left as a TODO inside `x402_middleware.py`.
- **Smart-Wallet batching**: `shared/wallets.batched_transfer` is sequential
  (3 separate CDP transfers) — adequate for the demo. A real Smart-Wallet
  atomic batched call is a swap-in for production.
- **Training quantization**: `bitsandbytes` 4-bit on ROCm is fragile, so
  LoRA training is plain BF16 (the MI300X has 192 GB to spare). See
  `lora_training/README.md`.

## License

MIT — see [LICENSE](LICENSE).
