"""Train ONE LoRA adapter on top of Qwen2.5-72B-Instruct for a single lender.

Configuration:
  * rank=16, alpha=32, target modules: q_proj, k_proj, v_proj, o_proj
  * BF16 LoRA (no quantization). bitsandbytes 4-bit on ROCm is fragile;
    the MI300X has 192 GB so plain BF16 LoRA fits comfortably.
  * 1 epoch on the synthetic dataset; defaults are tuned for the ~300-row
    per-lender datasets produced by ``synthetic_data.py``.

torch / transformers / peft / datasets / accelerate are imported lazily inside
``train()`` so this module imports fine on a dev machine without ROCm — the
``train_all.py`` orchestrator can run with ``--dry-run`` for validation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from data.bid_policies import LENDER_PROFILES, LORA_ADAPTERS_DIR
from shared.config import get_settings
from shared.logging import get_logger, setup_logging
from shared.models import LenderProfile

logger = get_logger("lora_training.train_lora")


def lora_path_for(profile: LenderProfile) -> Path:
    """Filesystem path where the trained adapter is saved/served from."""
    return Path(LORA_ADAPTERS_DIR) / profile.lora_alias


@dataclass
class TrainConfig:
    profile: LenderProfile
    data_path: Path
    output_dir: Path
    base_model: str
    epochs: int = 1
    rank: int = 16
    alpha: int = 32
    learning_rate: float = 2e-4
    batch_size: int = 4
    grad_accum: int = 4
    max_seq_len: int = 2048


def _profile_by_id(profile_id: str) -> LenderProfile:
    for p in LENDER_PROFILES:
        if p.id == profile_id:
            return p
    raise SystemExit(f"unknown profile id: {profile_id} (known: {[p.id for p in LENDER_PROFILES]})")


def describe(cfg: TrainConfig) -> str:
    return (
        f"profile={cfg.profile.id}  alias={cfg.profile.lora_alias}  "
        f"base={cfg.base_model}  data={cfg.data_path}  out={cfg.output_dir}  "
        f"rank={cfg.rank}  alpha={cfg.alpha}  epochs={cfg.epochs}  "
        f"batch={cfg.batch_size}x{cfg.grad_accum}"
    )


def train(cfg: TrainConfig) -> None:
    """Run BF16 LoRA training. Heavy imports happen here, not at module top."""
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    logger.info("loading base model %s in BF16", cfg.base_model)
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    lora_cfg = LoraConfig(
        r=cfg.rank,
        lora_alpha=cfg.alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    logger.info("loading dataset %s", cfg.data_path)
    raw = load_dataset("json", data_files=str(cfg.data_path), split="train")

    def _format(ex: dict) -> dict:
        text = tokenizer.apply_chat_template(
            ex["messages"], tokenize=False, add_generation_prompt=False
        )
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=cfg.max_seq_len,
            padding=False,
        )
        return tokenized

    tokenized = raw.map(_format, remove_columns=raw.column_names)
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    args = TrainingArguments(
        output_dir=str(cfg.output_dir),
        num_train_epochs=cfg.epochs,
        per_device_train_batch_size=cfg.batch_size,
        gradient_accumulation_steps=cfg.grad_accum,
        learning_rate=cfg.learning_rate,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=1,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    logger.info("starting training: %s", describe(cfg))
    trainer.train()
    logger.info("saving adapter to %s", cfg.output_dir)
    model.save_pretrained(str(cfg.output_dir))
    tokenizer.save_pretrained(str(cfg.output_dir))


def main() -> None:
    setup_logging()
    p = argparse.ArgumentParser()
    p.add_argument("--profile-id", required=True, help="lender id (e.g. prime-bank)")
    p.add_argument("--data-path", type=Path, required=True, help="JSONL file from synthetic_data")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--rank", type=int, default=16)
    p.add_argument("--alpha", type=int, default=32)
    p.add_argument("--dry-run", action="store_true", help="print plan without training")
    args = p.parse_args()

    profile = _profile_by_id(args.profile_id)
    cfg = TrainConfig(
        profile=profile,
        data_path=args.data_path,
        output_dir=lora_path_for(profile),
        base_model=get_settings().vllm_model,
        epochs=args.epochs,
        rank=args.rank,
        alpha=args.alpha,
    )

    if args.dry_run:
        logger.info("DRY RUN: %s", describe(cfg))
        return

    train(cfg)


if __name__ == "__main__":
    main()
