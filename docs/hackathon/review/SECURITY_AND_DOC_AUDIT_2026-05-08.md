# Security + Documentation Audit (2026-05-08)

This audit was run before final hackathon demo prep with two goals:

1. identify sensitive-data exposure risks in the repo/runtime setup,
2. ensure demo/runbook docs match the current deployed flow.

## Scope checked

- tracked source/docs for credentials or hardcoded secrets,
- environment and wallet handling patterns (`.env`, `wallets.json`),
- runtime controls for demo endpoints and telemetry,
- runbooks and README commands/ports for current behavior.

## Findings (ordered by severity)

### High

- No tracked hardcoded credentials were found in repository files.

### Medium

- `marketplace/x402_middleware.py` still does format and facilitator verification
  and does not include direct on-chain receipt validation in this demo path.
  This is acceptable for the hackathon simulation mode but should be hardened
  for production payment security.

### Low

- Several docs include example public droplet IPs and SSH key paths.
  This is operationally useful for hackathon debugging but should be rotated or
  removed in public-facing post-hackathon docs.

## Controls already in place

- `.env` is gitignored.
- `wallets.json` is gitignored.
- Demo runbooks default to:
  - `INSERTION_FEE_USDC=0`
  - `SETTLEMENT_MODE=stub`
  - `PAYMENT_MODE=stub`
  - `X402_FACILITATOR_MODE=local`
- Terminal UI and API now expose live but non-secret operational telemetry only
  (`/gpu/metrics`, request/bid counts).

## Documentation updates applied in this pass

- `README.md`
  - updated demo mode section to current May 8 state,
  - documented terminal `Run demo now` / `Stop demo` continuous flow,
  - aligned hero-shot guidance with current in-app controls.

- `docs/hackathon/runbooks/DROPLET_LIVE_DEMO_PLAYBOOK.md`
  - aligned marketplace host/port and terminal route details,
  - made in-app run/stop flow the primary path,
  - kept CLI fallback stream generator,
  - aligned log-tail commands with current runner log filename.

- `docs/hackathon/runbooks/DEMO_PATH_FRI_SAT.md`
  - updated runtime topology and commands to current `8001`/`8016` flow,
  - added explicit in-app continuous stream path.

## Post-hackathon hardening backlog

1. Add deterministic secret scanning in CI (gitleaks/trufflehog baseline).
2. Enforce branch protection check preventing commits that include `.env`-like files.
3. Add on-chain receipt verification for x402 settlement assertions.
4. Split internal ops runbooks (with infra IPs/paths) from public docs.
