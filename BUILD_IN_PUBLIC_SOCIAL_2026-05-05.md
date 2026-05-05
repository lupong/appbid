# Build in Public Social Drafts (2026-05-05)

## X / Twitter (short)

Built all day on MI300X for Credit App+ (auto-loan reverse auction + x402 + CDP).

Wins:
- 5 lender LoRAs trained
- adapters verified distinct
- direct PEFT inference works on AMD GPU

Blocker:
- vLLM+ROCm serving path unstable in tested configs (documented matrix in repo)

Next:
- AMD Quark FP8 on Qwen2.5-72B tomorrow.

Evidence + docs in repo:
https://github.com/lupong/appbid

## LinkedIn (medium)

Today’s build log for Credit App+ (AMD x Lablab hackathon):

I’m building a reverse-auction marketplace for auto-loan bid requests where 5 lender agents bid concurrently, pay insertion fees via x402, and settle through CDP wallets.

What worked on AMD MI300X:
- End-to-end wallet provisioning/funding
- 5 lender-specific LoRA adapters trained successfully
- adapter artifacts verified distinct
- direct `transformers + peft` inference produced lender-differentiated outputs

What didn’t:
- vLLM+ROCm serving in tested runtime configs showed instability/corrupted generation in most modes (I documented a full repro matrix in the repo).

Takeaway:
- LoRA architecture is sound
- blocker is serving/runtime path, not app logic or training pipeline

Tomorrow’s focus:
- AMD Quark FP8 quantization for Qwen2.5-72B to exploit MI300X hardware more directly.

Repo + evidence trail:
https://github.com/lupong/appbid
