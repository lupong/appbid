"""Quick side-by-side text generation for lender LoRA adapters.

Runs directly against local HF weights using transformers+peft (no vLLM).
"""

from __future__ import annotations

import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-new-tokens", type=int, default=220)
    args = p.parse_args()

    adapters = {
        "stcu_retail_auto": "/app/lora_adapters/stcu_retail_auto",
        "unitus_community_cu": "/app/lora_adapters/unitus_community_cu",
        "exeter_finance": "/app/lora_adapters/exeter_finance",
        "family_savings_cu": "/app/lora_adapters/family_savings_cu",
        "crouse_federal_cu": "/app/lora_adapters/crouse_federal_cu",
    }

    prompt = (
        "You are an auto-loan underwriter. Return JSON only with keys "
        "decision, apr_bps, term_months, max_amount_usdc, max_ltv_bps, "
        "cash_down_required_usdc, dealer_reserve_bps, stipulations, confidence, rationale.\n"
        'BID REQUEST: {"applicant_fico":655,"loan_amount":28950,'
        '"vehicle_type":"used","term_months":72,"state":"TX","dealer_reserve_bps":200}'
    )

    print("loading tokenizer/base...")
    tok = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model, torch_dtype=torch.bfloat16, device_map="auto"
    )

    for name, path in adapters.items():
        model = PeftModel.from_pretrained(base, path)
        model.eval()
        messages = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=args.max_new_tokens,
                eos_token_id=tok.eos_token_id,
            )
        generated = tok.decode(
            out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()
        print(f"=== {name} ===")
        print(generated[:600])
        del model
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
