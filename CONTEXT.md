# Project Context

Background and design decisions that don't live in the code or README. This
file is for reviewers, future Claude threads, and anyone joining the build.

## Hackathon

- **Event:** AMD x Lablab.ai Developer Hackathon
- **Window:** May 4–10, 2026
- **Submission deadline:** Sunday, May 10, 2026
- **Track:** X402 Payments (naturally adjacent to AI Agents + Financial Operations)
- **Builder:** Solo build (Andrew Pongco)

## Origin

- **2017:** Andrew pitched Credit App+ at the first-ever Cox Automotive
  enterprise hackathon and won. Mark O'Neill (then-Dealertrack CEO) blessed
  the concept.
- **Why it never shipped:** It would have cannibalized Dealertrack's
  per-application revenue. The marketplace structure inverts the existing
  per-app fee economics that Dealertrack monetizes.
- **Why now:** **X402 + AMD MI300X make it buildable in 2026.** Programmable
  USDC payments give you per-bid micropayments and atomic rev-splits that
  weren't practical on card rails. A single 192 GB GPU collapses the
  multi-lender inference cost from per-lender SaaS to one box.

## AMD pitch (the differentiators)

The 192 GB MI300X enables three things together:

1. **72B base + 5 LoRA adapters + KV cache on one GPU.** A single H100 80 GB
   cannot hold this combination. Multi-GPU only adds tensor-parallel
   overhead. One MI300X serves all 5 lender personas concurrently.
2. **On-prem inference with PII never leaving the box.** Compatible with
   Reg B (ECOA), FCRA, and GLBA when the funding-stage credit decision
   happens here. (At the marketplace boundary itself there is zero PII —
   see the Compliance posture section.)
3. **Open stack top to bottom.** ROCm + vLLM + Qwen2.5 weights + PEFT.
   No closed-model dependency, no per-token vendor lock.

## Compliance posture

Stronger than "PII stays on the box." The marketplace tier holds **zero
PII**. A bid request is a PII-free structural proposal (dealer-pulled FICO,
vehicle, term, amount, state, reserve — no name, SSN, or address). Losing
lenders never see PII. The PII-bearing retail installment contract only
moves out-of-band to the *winning* lender's funding desk, where the
regulated credit decision (adverse-action notices, ECOA reason codes,
fair-lending review, SR 11-7 model governance) lives.

Reg B / FCRA / GLBA exposure is concentrated at funding, not at the
marketplace.

## Wallet custody — BYO

Lenders bring their own wallets. The marketplace is **not a custodian** of
lender funds. Marketplace owns only its own platform wallet (insertion-fee
inflows, win-premium routing) and a reserve wallet. Lender keys / wallet
secrets never enter the marketplace.

`scripts/setup_wallets.py` provisions marketplace + reserve + 5 demo lender
wallets for the hackathon walkthrough; in production those 5 are replaced
by lender-controlled wallets.

## Insertion-fee semantics — Option A

- **Amount:** $0.10 USDC per bid
- **Form:** Pure platform fee — **not refundable, not credited toward
  the win premium if the bid wins.**
- **Rationale:** Spam-resistance + revenue at scale. A lender pays the
  $0.10 every time it submits a bid. Losing has no different price than
  winning at the bid stage.

## Win-premium semantics

- **Rate:** 1.5% of accepted loan amount.
- **Split:** 70% dealer / 25% marketplace / 5% reserve.
- **Mechanism:** Three-way rev-split executed at acceptance time via the
  marketplace's CDP wallet. Target end-state is a Coinbase Smart Wallet
  batched call (single atomic on-chain operation); current implementation
  is sequential transfers — see README "Notes / deviations."

## Funding events — out of scope

The funding-stage credit decision (full PII contract, fresh credit pull,
KYC, adverse-action notices) is **explicitly Phase 2**. Hackathon scope
ends at acceptance + rev-split. `RequestStatus.FUNDED_PENDING` is wired
into the schema as a placeholder; no funding-side flow is implemented.

## Lender persona design — five dimensions

Each of the 5 lender personas is differentiated along five axes. The axes
are encoded into the rate-sheet text that seeds LoRA training; the LoRA
learns the lender's behavior on each axis from labeled synthetic
decisions.

1. **Risk appetite** — FICO floor, vehicle-type acceptance, max amount,
   max LTV.
2. **Rate aggressiveness** — APR ladder, willingness to undercut to win.
3. **Dealer-reserve generosity** — bps the lender will let the dealer mark
   up.
4. **Stipulation strictness** — number and burden of conditions
   (paystubs, insurance, residence, PoI types).
5. **Volume hunger** — how aggressively the lender approves marginal deals
   to grow book.

The 5 personas span a deliberate cross-section:

- **Prime Bank** — high FICO floor, low rate, modest reserve, full stips,
  low volume hunger.
- **Mid-Market Credit** — near-prime, generous reserve, moderate stips,
  high volume hunger.
- **Subprime Specialist** — sub-640 focus, high APR, heavy stips.
- **Used-Only Credit Union** — used vehicles only, member-pricing rate
  posture.
- **EV Captive** — EV-only, manufacturer-aligned incentives, LTV
  flexibility.

## Decisions reference

| Decision | Value |
|---|---|
| Insertion fee | $0.10 USDC, Option A (not refundable, not credited) |
| Win premium | 1.5% of accepted loan amount |
| Rev-split | 70 dealer / 25 marketplace / 5 reserve |
| Wallet custody | BYO — marketplace not custodian |
| Funding scope | Out (Phase 2) |
| Track | X402 Payments |
| Compute | Single AMD MI300X 192 GB |
| Base model | Qwen2.5-72B-Instruct (BF16) |
| LoRA serving | vLLM multi-LoRA, 5 adapters |
| Fallback | `LORA_MODE=prompt` — rate sheet inlined to system prompt |

## Inputs from other threads — unmerged

These are concepts surfaced in parallel design threads (Gemini and OpenAI
prompts) that do **not** exist in the current project. Captured here verbatim
so they're not lost; **no attempt has been made to reconcile them with the
current architecture**, and some directly contradict it. Triage before
merging.

### Pre-bid pipeline stages

- Document / OCR extraction
- Entity normalization / feature builder
- LLM intake normalizer (messy dealer JSON + free-text F&I notes →
  canonical "Master Payload")
- Package classifier (what *kind* of package this is)
- Adapter router (picks which LoRA to invoke based on classification)
- GNN fraud check (GraphSAGE / PyG or DGL) running before the auction
- "Power booking" / synthetic identity / dealer collusion signals
- Fraud-block-before-auction state in the orchestration state machine

### Alternate LoRA specialization axis

Current project specializes LoRAs by *lender*. Alternate axis proposed:
LoRA per **package/document pattern**:

- Stip-heavy package review
- Self-employed income documentation
- Document-anomaly review
- Dealer-submission-quality patterns
- High-complexity package review

### Policy / context layer

- RAG layer for lender policy, dealer program rules, document checklists,
  exception-handling guides
- Deterministic post-processor for hard controls, schema validation,
  required-field gating, confidence thresholds, routing triggers

### Intake-triage output framing

- "Ready to ingest / missing info / needs escalation / manual review"
  classification (distinct from bid decisions)
- Confidence thresholds wired to routing triggers
- Acceptance of free-text F&I manager notes at intake

### Multi-tenant infrastructure

- Lender-hosted, containerized, isolated decision engines (the "tenant
  XGBoost containers" pattern)
- Strict CPU vs GPU partitioning policy (VRAM = LLM + GNN only;
  CPU = orchestration + tree models)
- ROCm Docker container deployment topology
- ROCm 6.2 version pin

### Operational layers

- Queue routing layer
- Audit logging
- Human feedback / correction record schema
- Feedback → training dataset loop

### Implementation guidance not currently captured

- PyTorch ROCm as baseline; vLLM treated as later optimization
- Explicit LoRA adapter loading / caching strategy
- VRAM / memory budget plan
- Batching strategy
- Graceful-failure contract for unparseable dealer payloads
  ("must not crash the orchestrator")
