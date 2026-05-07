#!/usr/bin/env python3
"""Small baseline vs amd-optimize LoRA training benchmark."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import subprocess
import time
from pathlib import Path

from data.bid_policies import LENDER_PROFILES
from lora_training.synthetic_data import generate_training_examples, make_teacher, write_jsonl


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=32)
    p.add_argument("--profile-id", default="prime-bank")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--timeout-seconds", type=int, default=1800)
    args = p.parse_args()

    profile = next((p for p in LENDER_PROFILES if p.id == args.profile_id), None)
    if profile is None:
        raise SystemExit(f"unknown profile_id={args.profile_id}")

    examples = asyncio.run(
        generate_training_examples(profile, make_teacher("stub"), n=args.rows, seed=42)
    )
    data_path = Path(f"lora_training/data/{args.profile_id}-bench{args.rows}.jsonl")
    write_jsonl(examples, data_path)

    imports: dict[str, str] = {}
    for mod in ("optimum", "optimum.amd", "optimum.bettertransformer"):
        try:
            importlib.import_module(mod)
            imports[mod] = "ok"
        except Exception as exc:  # noqa: BLE001
            imports[mod] = f"fail:{type(exc).__name__}:{str(exc)[:120]}"

    base_env = f"VLLM_MODEL={args.model} "
    runs = [
        (
            "baseline",
            base_env
            + f"python3 lora_training/train_lora.py --profile-id {args.profile_id} "
            + f"--data-path {data_path} --epochs 1",
        ),
        (
            "amd_opt",
            base_env
            + f"python3 lora_training/train_lora.py --profile-id {args.profile_id} "
            + f"--data-path {data_path} --epochs 1 --amd-optimize",
        ),
    ]

    out_dir = Path("artifacts/profiling")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"imports": imports, "runs": []}

    for name, cmd in runs:
        log_path = out_dir / f"{name}_train_bench.log"
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=args.timeout_seconds,
            )
            rc = proc.returncode
            output = proc.stdout
        except subprocess.TimeoutExpired as exc:
            rc = 124
            output = (exc.stdout or "") + "\nTIMEOUT\n"
        dt = round(time.time() - t0, 2)
        log_path.write_text(output)
        cast_runs = summary["runs"]
        assert isinstance(cast_runs, list)
        cast_runs.append(
            {
                "name": name,
                "exit_code": rc,
                "wall_seconds": dt,
                "log": str(log_path),
            }
        )

    out_json = out_dir / "optimum_benchmark_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
