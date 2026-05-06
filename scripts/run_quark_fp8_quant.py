"""Run AMD Quark FP8 file-to-file quantization for HF models."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download
from quark.torch import LLMTemplate
from quark.torch.quantization.file2file_quantization import quantize_model_per_safetensor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quantize model to FP8 with AMD Quark")
    parser.add_argument("--repo-id", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--model-type", default="qwen2")
    parser.add_argument(
        "--scheme",
        default="fp8",
        help="Quark quantization scheme (e.g. fp8, ptpc_fp8)",
    )
    parser.add_argument(
        "--kv-cache-scheme",
        default="fp8",
        help="KV-cache quantization scheme",
    )
    parser.add_argument("--source-dir", default="/app/models/qwen2.5-7b")
    parser.add_argument("--output-dir", default="/app/models/qwen2.5-7b-fp8")
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--attention-scheme",
        default=None,
        help="Optional attention scheme override (e.g. fp8) for Q/K/V uniformity",
    )
    parser.add_argument(
        "--disable-output-tensors",
        action="store_true",
        help="Force output_tensors quantization off for vLLM compatibility",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_dir = snapshot_download(
        repo_id=args.repo_id,
        local_dir=str(source_dir),
        local_dir_use_symlinks=False,
    )
    template = LLMTemplate.get(args.model_type)
    config = template.get_config(
        scheme=args.scheme,
        kv_cache_scheme=args.kv_cache_scheme,
        attention_scheme=args.attention_scheme,
    )
    if args.disable_output_tensors:
        config.global_quant_config.output_tensors = None
        for layer_cfg in config.layer_quant_config.values():
            layer_cfg.output_tensors = None

    quantize_model_per_safetensor(
        pretrained_model_path=model_dir,
        quant_config=config,
        save_path=str(output_dir),
        device=args.device,
    )
    print(f"QUANT_DONE repo={args.repo_id} output={output_dir}")


if __name__ == "__main__":
    main()
