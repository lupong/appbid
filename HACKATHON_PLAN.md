# Credit App+ — Hackathon Plan

AMD x Lablab.ai Developer Hackathon · Track: **X402 Payments** · Solo (Andrew Pongco)

- **Deadline:** Sunday **May 10, 2026** (matches the on-screen countdown)
- **Today:** Tuesday May 5, 2026 — **T-5 days**
- **Submission portal:** https://lablab.ai/ai-hackathons/amd-developer (Submit tab)
- **Goal:** *Submit by Saturday May 9 evening.* Sunday is reserved as bug-fix and re-submit buffer, not as a build day.

---

## 1. Strategy in one paragraph

The product is real, the code is real, the 2017 Cox Automotive win is a real provenance story. The risk in this hackathon is not "can I build it" — it's "can I prove the AMD-stack-specific claim works end-to-end, capture it on video, and tell the story in a way judges remember." So the next 5 days are weighted **40% ship the AMD-specific differentiator (multi-LoRA on a real MI300X), 30% record proof (concurrency demo + video), 20% submission polish, 10% buffer**. Anything that does not move one of those four levers gets cut.

## 2. Judging criteria → moves that score

The hackathon is judged on four axes ([Lablab Rule Book][rules]). Each row below is the *single most-leveraged thing* that scores it.

| Criterion | Highest-leverage move | Where it lands |
|---|---|---|
| **Application of Technology** | Real `LORA_MODE=multi` run on the MI300X with all 5 adapters routed live; one screenshot of `rocm-smi` showing 5 adapters resident; one Base Sepolia tx hash for the rev-split | Demo video minute 0:30–1:30; README "Live demo proof" section |
| **Presentation** | 3-minute video with screen capture of the concurrency demo + voice-over; clean slide deck; cover image | Submission video, slides, cover |
| **Business Value** | Open with the 2017 Cox story (Mark O'Neill blessed it; never shipped because of revenue cannibalization); close with $1.4T US auto-loan market + per-app-fee inversion | Pitch hook + pitch close |
| **Originality** | The "1 GPU does what 8 GPUs do" claim, framed as the *reason this product is now economically possible*. Reverse-auction-with-LoRA-per-lender is genuinely novel — name it | Slide 3, video minute 2:00 |

## 3. Day-by-day timeline

Times are local. Each day has **one acceptance gate**; if it doesn't pass, that day's work isn't done — bump to the morning of the next day. The buffer day is real, not aspirational.

### T-5 · Tue May 5 — Droplet up, data generated

| When | Block | Output |
|---|---|---|
| AM | Spin up MI300X droplet on AMD Developer Cloud (use `rocm/vllm:latest` and `rocm/pytorch:latest` per `infra/README.md` — do **not** bootstrap ROCm on bare Ubuntu) | Droplet alive, `scripts/check_gpu.py` prints MI300X 192 GB |
| AM | Clone repo onto droplet · `cp .env.example .env` · fill `CDP_API_KEY_*`, `MARKETPLACE_WALLET_ID`, `RESERVE_WALLET_ID` | `.env` complete |
| AM | `python -m scripts.setup_wallets` then `scripts.fund_wallets` — drip USDC into all 7 wallets | `wallets.json` populated, faucet shows balances on Base Sepolia |
| PM | Pull base model: `huggingface-cli download Qwen/Qwen2.5-72B-Instruct` (~150 GB — start the download, do something else) | Model cache warm |
| PM | Start vLLM serving the **base model only** (no LoRA yet) — sanity that ROCm + vLLM + Qwen2.5-72B BF16 actually serves chat completions | `curl localhost:8000/v1/models` returns `Qwen2.5-72B-Instruct` |
| PM | `python lora_training/train_all.py --teacher=llm` — the teacher will be the base model you just stood up. Generates JSONL for all 5 lenders. **CPU-bound; do this while base model is downloading if disk allows** | `lora_training/data/<alias>.jsonl` for all 5 lenders, ~300 rows each |
| EOD | `pytest tests/ -v` from droplet to confirm nothing broke during deploy | All tests green |

**Acceptance gate (T-5):** Base model serves; 5 JSONL training files exist; tests pass on droplet.

### T-4 · Wed May 6 — Train all 5 LoRAs

| When | Block | Output |
|---|---|---|
| AM | Kick off `python lora_training/train_all.py --teacher=llm` — the actual training run. ~3–5 h wall-clock for 5 lenders sequential | `lora_adapters/{prime_bank,mid_market,subprime,used_only,ev_captive}/` exist |
| AM | While training: pre-write the **demo video script** (§5 below) so you're not writing it tired on Friday | `demo_script.md` (will move into the deck) |
| PM | When training done: stop the base-only vLLM, restart with `bash infra/start_vllm.sh` (multi-LoRA flags) | vLLM logs show 5 adapters loaded |
| PM | Smoke test adapter routing: 5 manual `curl` calls with `model: prime_bank`, `mid_market`, etc. — confirm each adapter returns visibly different policies on the *same* bid request | Diff'd outputs prove the LoRAs actually learned different lender behavior |
| PM | `python -m scripts.e2e_test` end-to-end: publish 1 bid request → 5 bids → accept → rev-split lands on Base Sepolia | Single tx hash; ledger row matches |
| EOD | `python -m scripts.concurrency_demo` — 50 bid requests in ≤10 s, captured live | Console output saved as `demo_run_t4.txt` |

**Acceptance gate (T-4):** All 5 adapters serve; concurrency demo lands within SLA; one Base Sepolia tx hash exists from `e2e_test`.

> **If LoRA training breaks** (ROCm misbehaves on multi-LoRA, OOM, etc.): fall back to `LORA_MODE=prompt` on the same MI300X. The whole demo still works; you lose the "5 adapters in one GPU" framing in the deck but keep the "72B base on one GPU" framing. Don't burn more than 3 hours fighting LoRA — pivot and move on.

### T-3 · Thu May 7 — Close the two outstanding TODOs + record demo

| When | Block | Output |
|---|---|---|
| AM | **TODO #1 (worth real points): `eth_getTransactionReceipt` verification in `marketplace/x402_middleware.py`.** Today this only format-checks the X-PAYMENT header. Wire actual receipt lookup against `BASE_SEPOLIA_RPC` so a fake hash is rejected. ~2–3 h. | Middleware verifies real chain receipts; new test in `test_marketplace.py` |
| AM | **TODO #2 (nice-to-have): Coinbase Smart Wallet atomic batched 3-way rev-split** (currently sequential transfers in `shared/wallets.batched_transfer`). Single atomic on-chain call is much more demoable. ~2–3 h. **Cut if AM TODO #1 runs long** — the sequential version works fine | Either: real Smart Wallet batched call, or "future work" line in the slide |
| PM | Run the concurrency demo with `monitor.sh` open in a side terminal — capture **screen recording of the Streamlit dealer UI side-by-side with `rocm-smi` showing GPU saturation across all 5 adapters**. This is the hero shot. | Raw screen recording: `demo_raw.mov` (target ≤90 s of useful content) |
| PM | Record a short clean run of `e2e_test.py` showing one BaseScan tx hash being created in real-time | `tx_proof.mov` |
| EOD | Cut a rough video using QuickTime/iMovie — voice-over comes tomorrow | `demo_rough.mov` (no audio yet) |

**Acceptance gate (T-3):** X402 middleware now does real receipt verification (test passes); ≥60 s of usable demo footage captured.

### T-2 · Fri May 8 — Slides, voice-over, README polish

| When | Block | Output |
|---|---|---|
| AM | Slide deck (10 slides, see §6) in Keynote/Slides | `deck.pdf` |
| AM | Cover image (1200×630) — pull a clean shot of the dealer UI with one bid accepted, BaseScan tx visible. Tools: Figma or just Keynote export | `cover.png` |
| PM | Record voice-over against the rough cut. Aim for **2:45–3:00**. Lablab caps videos somewhere short — **verify the exact cap on the submission page before exporting**, but plan for ≤3 min | `demo_final.mp4`, uploaded to YouTube as **unlisted** |
| PM | README polish pass — make sure it answers: *what, why-AMD, how-to-run, demo URL, video URL, license* in the first 60 lines. Reviewer scrolling on a phone should get the pitch | README.md updated |
| PM | Run full test suite one more time, then push a clean tag: `git tag v1.0-hackathon-submission` | Tag pushed |
| EOD | Self-review: open the GitHub repo as if you were a stranger. Does the first screen sell it? | Punch-list of fixes for tomorrow |

**Acceptance gate (T-2):** Deck done; video uploaded; README "first screen" sells the project; clean git tag.

### T-1 · Sat May 9 — Submit

| When | Block | Output |
|---|---|---|
| AM | Knock out the punch-list from yesterday's self-review | Repo polished |
| AM | Deploy the dealer UI somewhere public and stable for 30 days. Streamlit Cloud is the path of least resistance — it speaks Streamlit natively. Use **`LORA_MODE=prompt` + `VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct`** for the public demo (don't expose the MI300X to the internet) | Public demo URL, e.g. `creditapp.streamlit.app` |
| AM | Smoke the public demo from a phone you've never used | Demo works on cold device |
| PM | **Fill the Lablab submission form** (§7 checklist below). Submit. Take a screenshot of the confirmation. | Submission confirmed |
| PM | Post in the hackathon Discord: short "I'm submitted, here's a 1-line demo" — judges sometimes scroll Discord | Visibility |
| EOD | Phone goes on Do Not Disturb. Sleep. | — |

**Acceptance gate (T-1):** Submitted. Confirmation screenshot saved.

### T-0 · Sun May 10 — Buffer

Reserved. If the submission was rejected for a missing field, fix it. If everything's fine, do nothing. Do **not** "improve the demo" today — every change you make under deadline pressure is a regression risk.

## 4. What I'm explicitly NOT doing this week

These are real tradeoffs. List them on a slide as "future work" so judges don't assume they're missing.

- **Funding-stage flow** — out of scope per `CONTEXT.md`, Phase 2.
- **Real on-chain wallet custody for lenders** — using the demo BYO-wallet pattern with the marketplace-provisioned demo wallets. Lenders bring their own in production.
- **GNN fraud check, OCR pipeline, package classifier, intake triage** — listed in `CONTEXT.md § Inputs from other threads — unmerged`. Don't try to merge any of it now. Cut.
- **Per-package LoRA specialization axis** — interesting alternate; not this week.
- **bitsandbytes 4-bit on ROCm** — known fragile per `lora_training/README.md`. BF16 only.

## 5. Demo video — script (3:00 cap)

Read straight off this. Don't ad-lib. Practice it twice; record on the third take.

> **[0:00–0:15] Hook.** "In 2017, this product won Cox Automotive's first-ever enterprise hackathon. Mark O'Neill, then-CEO of Dealertrack, blessed it. It never shipped — because it would have cannibalized Dealertrack's per-application revenue. Two pieces of 2026 technology made it buildable: programmable USDC payments via x402, and one AMD MI300X."

> **[0:15–0:45] Problem.** "Auto-loan origination is a closed garden. A dealer sends an application to lenders one at a time over Dealertrack and RouteOne. Lenders don't compete on price — they compete on relationship. Borrowers eat 50 to 200 basis points of slippage. The platform takes a per-application fee that entrenches the broker, not an auction. Credit App+ inverts it: a reverse auction where 5 lender agents bid on the same PII-free request, and the dealer takes the best APR."

> **[0:45–1:45] Live demo.** *Switch to screen recording.* "This is the dealer dashboard. I publish a bid request — 2024 Toyota Camry, $25,000, 60-month, 720 FICO, Texas. No name, no SSN, no address — the marketplace tier holds zero PII. Each lender agent pays a $0.10 USDC insertion fee via x402 — here's the chain confirmation. Five bids land in under two seconds. The dealer accepts the best APR. The marketplace executes a three-way atomic split: 70% to the dealer, 25% to us, 5% to reserve. Here's the BaseScan transaction." *Pause on tx hash.* "Now I run the concurrency demo: 50 bid requests, all 5 lenders bidding concurrently, in 10 seconds." *Pan to `rocm-smi` panel showing all 5 adapters resident.*

> **[1:45–2:25] Why AMD.** "This is the part that needed the MI300X. The base model is Qwen2.5-72B in BF16 — that's 144 gigabytes of weights. On top of it, vLLM serves five LoRA adapters concurrently, plus the KV cache that powers continuous batching across all 5 lender agents. **One MI300X — 192 gigabytes of HBM3 — fits all of that on a single device. A single H100 with 80 gigabytes cannot. Multi-GPU only adds tensor-parallel overhead.** The whole stack — ROCm, vLLM, Qwen2.5, PEFT — is open. No closed-model dependency."

> **[2:25–3:00] Close.** "The US auto-loan market is $1.4 trillion. Per-application fees are a $250 to $1,000-per-loan tax that doesn't get the borrower a better rate. Credit App+ converts that tax into auction-priced spread, with on-prem PII compliance that fits Reg B, FCRA, and GLBA. Code is on GitHub. The demo is live. I'm Andrew Pongco. Thank you."

**Stage cues:**
- Switch to screen at 0:45 sharp. Talking head before that, screen-only after.
- Hold on the BaseScan tx hash for at least 2 seconds. Judges are skimming — they need a beat to register "this is real money on a real chain."
- The `rocm-smi` panel is the *only* AMD-specific shot — make sure it's legible at 720p.

## 6. Slide deck (10 slides)

1. **Title.** Credit App+ · Reverse-auction marketplace for auto-loan bid requests · Andrew Pongco · AMD x Lablab.ai 2026
2. **The 2017 story.** Won Cox Automotive's first hackathon. Mark O'Neill blessed it. Never shipped — would have cannibalized per-app fees. *(This is the originality + business-value hook.)*
3. **Why now.** x402 micropayments + MI300X 192 GB. Two technologies that didn't exist in 2017.
4. **Architecture diagram.** Same one as `README.md`. Streamlit → FastAPI → 5 lender agents → vLLM → MI300X.
5. **Live demo screenshot.** Concurrency demo + `rocm-smi` panel side-by-side.
6. **Why AMD.** 72B + 5 LoRA + KV cache fit on **one** MI300X. H100 80 GB cannot. ROCm + vLLM + PEFT + Qwen — open stack.
7. **x402 + CDP.** $0.10 insertion fee · 1.5% win premium · 70/25/5 atomic rev-split · Base Sepolia · BaseScan link.
8. **Compliance posture.** Marketplace tier holds zero PII. Funding-stage credit decision out-of-band at the *winning* lender. Reg B / FCRA / GLBA exposure concentrated at funding, not at the bid step.
9. **Market.** $1.4T US auto loans · per-app-fee tax inversion · serves dealers and borrowers, not the broker.
10. **Code · Demo · Video.** Three QR codes. Repo, live demo, YouTube.

## 7. Submission checklist

Lablab requires the following ([per the AMD hackathon page][hack]). Each item has the path/URL where it lives.

- [ ] **Cover image** (1200×630, ≤2 MB) → `submission/cover.png` *(plan to create T-2 AM)*
- [ ] **Video presentation** (YouTube/Vimeo, **unlisted**, ≤lablab cap — verify on submission page) → uploaded T-2 PM
- [ ] **Slide presentation** (PDF, ≤10 MB) → `submission/deck.pdf` *(T-2 AM)*
- [ ] **Public GitHub repo** (MIT-licensed, README explains setup + demo) → `github.com/andrewpongco/appbid-plus` *(verify license file exists; ✅ MIT already in place)*
- [ ] **Demo application platform** (where it runs — Streamlit Cloud) → `creditapp.streamlit.app` *(T-1 AM)*
- [ ] **Application URL** (same as demo platform if single-URL) → same as above
- [ ] **Project title** → "Credit App+: Reverse-Auction Marketplace for Auto Loan Bid Requests"
- [ ] **Tagline** (≤140 chars) → "5 lender agents bid on PII-free auto loan requests. x402 micropayments. One AMD MI300X serves all 5 LoRAs."
- [ ] **Description** (markdown allowed) → reuse README intro paragraphs
- [ ] **Track tag** → **X402 Payments**
- [ ] **Tech stack tags** → AMD MI300X, ROCm, vLLM, Qwen2.5-72B, PEFT/LoRA, x402, Coinbase CDP, FastAPI, Streamlit
- [ ] **Team info** → solo (Andrew Pongco)
- [ ] **License compliance** (MIT, no proprietary deps) → ✅
- [ ] **Discord post** (after submitting) → "submitted, 1-line demo, link to video"

## 8. Risks & cut-lists (in priority order)

1. **MI300X droplet capacity / queue time.** AMD Developer Cloud may put you in line. *Mitigation:* spin it up T-5 morning *first thing*, before doing anything else. If it's not available by EOD T-5, file a support ticket and pivot to running the LoRA training on Modal/RunPod with an MI300X — the architecture is portable.
2. **Multi-LoRA on ROCm misbehaves at serve time.** *Mitigation:* `LORA_MODE=prompt` works without LoRA. The whole pitch survives, you lose one slide. Don't burn >3 hours fighting it.
3. **CDP faucet rate-limited / Base Sepolia congested at demo time.** *Mitigation:* fund wallets generously T-5; pre-record a clean tx for the video so the live demo isn't blocked on chain liveness.
4. **Video runs long.** *Mitigation:* 3:00 cap is firm. If your first take is 4:00, cut the architecture-diagram beat — it's on the slide already, you don't need to narrate it.
5. **Streamlit Cloud cold-start makes the public demo look slow.** *Mitigation:* warm it 30 min before submission and again the morning judges typically review (Mon/Tue post-deadline).

## 9. Daily standup with myself

End each day, write 3 lines in `STANDUP.md`:
- ✅ Done today
- ⚠️ Slipped or blocked
- 🎯 Tomorrow's one-thing

If two days in a row "slipped or blocked" hits the same thing, cut it from scope — don't keep grinding.

---

[hack]: https://lablab.ai/ai-hackathons/amd-developer
[rules]: https://lablab.ai/hackathon-rules
