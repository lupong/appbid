"""Sequentially train all 5 lender LoRAs on the AMD MI300X droplet.

Steps per lender:
  1. Generate ``--n`` synthetic training pairs to ``data/<profile>.jsonl``
     using the chosen teacher (default: stub for dry-run; pass
     ``--teacher=llm`` for the real teacher that calls the base model with
     the lender's ``rate_sheet_text`` inlined).
  2. Train a rank-16 BF16 LoRA on top of the configured base model
     (default: ``Qwen/Qwen2.5-72B-Instruct`` from settings).
  3. Save the adapter to ``LORA_ADAPTERS_DIR/<lora_alias>/``.

Total runtime budget on the MI300X: 3-5 hours for 5 lenders @ 300 examples
each. Acceptable. Run with ``--dry-run`` for a no-GPU sanity check that
walks through all profiles and prints what would be trained.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from data.bid_policies import LENDER_PROFILES
from lora_training.synthetic_data import (
    DEFAULT_N_PER_LENDER,
    DEFAULT_OUT_DIR,
    dataset_path,
    generate_training_examples,
    make_teacher,
    write_jsonl,
)
from lora_training.train_lora import TrainConfig, describe, lora_path_for, train
from shared.config import get_settings
from shared.logging import get_logger, setup_logging

console = Console()
logger = get_logger("lora_training.train_all")


def main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(
        description="Train all 5 lender LoRAs (run on the AMD MI300X droplet)"
    )
    p.add_argument("--n", type=int, default=DEFAULT_N_PER_LENDER, help="examples per lender")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--data-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--rank", type=int, default=16)
    p.add_argument("--alpha", type=int, default=32)
    p.add_argument(
        "--teacher",
        choices=["stub", "llm"],
        default="stub",
        help=(
            "stub: deterministic placeholder labels (dry-run only). "
            "llm: real teacher via vLLM with the rate sheet inlined."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="generate synthetic data and print the training plan; skip actual training",
    )
    args = p.parse_args()

    base_model = get_settings().vllm_model
    teacher = make_teacher(args.teacher)
    console.rule(
        f"[bold]LoRA training plan[/]  base={base_model}  teacher={args.teacher}  "
        f"dry_run={args.dry_run}"
    )

    async def _generate(profile, out_path: Path) -> None:
        examples = await generate_training_examples(
            profile, teacher, n=args.n, seed=args.seed
        )
        write_jsonl(examples, out_path)
        console.print(f"  wrote {len(examples)} examples -> {out_path}")

    for profile in LENDER_PROFILES:
        out_path = dataset_path(profile.id, args.data_dir)
        console.print(f"[cyan]==>[/] generating data for [bold]{profile.id}[/]")
        asyncio.run(_generate(profile, out_path))

        cfg = TrainConfig(
            profile=profile,
            data_path=out_path,
            output_dir=lora_path_for(profile),
            base_model=base_model,
            epochs=args.epochs,
            rank=args.rank,
            alpha=args.alpha,
        )

        if args.dry_run:
            console.print(f"  [yellow]DRY RUN[/] {describe(cfg)}")
            continue

        console.print(f"  [green]TRAIN[/] {describe(cfg)}")
        train(cfg)
        console.print(f"  [green]DONE[/]  saved adapter to {cfg.output_dir}")

    console.rule("[bold green]all lenders done[/]")


if __name__ == "__main__":
    main()
