# Tomorrow Plan — Thursday 2026-05-07

This is the full execution plan for tomorrow, scoped to what most improves submission quality and AppBid proof for judges.

## 1) Tomorrow's objective

Ship one judge-ready narrative day where AppBid shows:

1. real AMD-specific technical evidence,
2. real marketplace behavior (dealer + lender-agent flow),
3. low-risk demo reliability for Friday/Saturday recording and submission.

## 2) How tomorrow directly relates to AppBid

Every block below maps to core AppBid claims:

- **Marketplace credibility:** proving request -> bids -> acceptance behavior under load supports the AppBid reverse-auction story.
- **AMD differentiation:** validating runtime/kernel/tooling evidence on MI300X supports the "why AppBid on AMD" claim.
- **Submission readiness:** producing footage, logs, and concise docs reduces Friday risk and prevents last-minute regressions.
- **Business narrative integrity:** keeping demo-safe toggles explicit (`SETTLEMENT_MODE=stub` where needed) preserves transparency while still demonstrating AppBid product flow.

## 3) Hard constraints for tomorrow

- Do not destabilize the known working demo-safe path.
- Keep payment-path work time-boxed; no open-ended CDP churn.
- Prefer evidence capture over refactoring.
- If a task misses its timebox, cut scope and preserve artifacts.

## 4) Execution schedule (local time)

## 09:00-09:30 — Environment sanity + baseline check

### Tasks

- Confirm services start cleanly in the current known good mode.
- Run one quick smoke of:
  - marketplace API health,
  - lender runner reachability,
  - inference endpoint reachability.
- Confirm docs path consistency after folder reorg.

### Deliverables

- One short sanity log snippet (or note) in `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md`.
- Explicit "green baseline" note for tomorrow's run start.

### AppBid linkage

This proves AppBid's baseline marketplace loop is intact before any optimization or evidence work begins.

---

## 09:30-12:00 — Priority A: x402 receipt verification hardening

### Tasks

- Implement real `eth_getTransactionReceipt` verification in `marketplace/x402_middleware.py`.
- Enforce that fake/unknown tx hashes are rejected.
- Add/update tests in marketplace test suite for:
  - valid receipt pass,
  - invalid receipt fail,
  - wrong recipient/amount fail.

### Timebox and cut rule

- **Timebox: 2.5 hours max.**
- If not complete by 12:00, keep current demo-safe behavior and move this to post-submission backlog.

### Deliverables

- Passing tests for receipt verification path.
- Short implementation note in `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md`.

### AppBid linkage

This strengthens AppBid's real payment-gate integrity and supports the claim that bid insertion fees are verifiable, not just syntactic placeholders.

---

## 12:00-13:00 — Midday checkpoint + decision gate

### Decision gate

- If Priority A is complete, proceed with optional payment-path enhancement.
- If Priority A is incomplete, freeze payment changes and pivot fully to evidence capture and demo media.

### Deliverables

- One explicit gate decision note logged in `../devex/AMD_DEV_CLOUD_DEVEX_NOTES.md`.

### AppBid linkage

Prevents over-investment in one subsystem and protects full AppBid demo readiness.

---

## 13:00-14:30 — Priority B (optional): settlement flow polish

### Tasks

- Evaluate feasibility of a more demoable 3-way settlement call path.
- If low-risk, implement minimal improvement only.
- If medium/high-risk, skip and document as future work.

### Timebox and cut rule

- **Timebox: 90 minutes hard stop.**
- No deadline-day architectural rewrites.

### Deliverables

- Either:
  - small merged improvement with tests, or
  - explicit "deferred" note with rationale.

### AppBid linkage

Improves trust in AppBid's monetization layer, but only if it does not compromise core demo reliability.

---

## 14:30-17:00 — Priority C: AppBid proof capture (hero evidence)

### Tasks

- Run concurrency demo and capture:
  - dealer UI activity,
  - lender responses,
  - AMD telemetry panel (`rocm-smi`).
- Capture one clean E2E run suitable for demo clips.
- Save artifacts under `../../artifacts/profiling/` and referenced demo output paths.

### Deliverables

- Raw footage clips for:
  - concurrency hero shot,
  - E2E flow proof shot.
- Updated notes in `../recaps/TODAY_2026-05-06_RECAP.md` successor context (tomorrow's recap when created).

### AppBid linkage

This is direct visual proof that AppBid's reverse-auction engine performs under concurrent demand on AMD hardware.

---

## 17:00-18:00 — Priority D: Documentation + narrative packaging

### Tasks

- Update `HACKATHON_PLAN.md` and supporting docs with only new facts from today.
- Add concise bullet outcomes:
  - what changed,
  - what evidence was captured,
  - what remains risky.
- Prepare Friday handoff checklist.

### Deliverables

- Clean, reviewer-readable doc updates.
- Friday-ready checklist with no ambiguity.

### AppBid linkage

Makes AppBid's technical work legible to judges: not just code changes, but clear product impact and evidence.

## 5) Acceptance criteria for end of tomorrow

Tomorrow is considered successful only if all are true:

1. AppBid demo-safe path still runs end-to-end.
2. At least one new high-signal technical proof artifact is captured and documented.
3. Payment-path status is clearer than today (implemented or explicitly deferred with reason).
4. Friday recording work starts from prepared assets, not from debugging.

## 6) Risks and mitigations (tomorrow-specific)

- **Risk:** Payment integration churn consumes the day.
  - **Mitigation:** strict timeboxes + midday gate.
- **Risk:** Infra instability interrupts capture windows.
  - **Mitigation:** capture evidence immediately after baseline check.
- **Risk:** Documentation drift from actual runtime state.
  - **Mitigation:** update docs only from completed, reproducible runs.

## 7) Friday handoff checklist (prepared tomorrow EOD)

- [ ] "What worked today" bullets finalized.
- [ ] "What is demo-safe" runtime config explicitly written.
- [ ] All new artifacts linked from docs.
- [ ] Remaining open items ranked by judge impact.

