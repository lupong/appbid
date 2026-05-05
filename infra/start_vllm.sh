#!/usr/bin/env bash
# Start vLLM on the AMD MI300X serving Qwen2.5-72B-Instruct + 5 LoRA adapters.
#
# Run from the repo root after `lora_training/train_all.py` has produced the
# adapters under ./lora_adapters/<alias>/. Exposes an OpenAI-compatible API
# on $VLLM_PORT (default 8000); each lender's adapter is selected by passing
# its alias as the `model` field of a chat-completions request.
#
# ROCm tuning notes:
#   * HSA_OVERRIDE_GFX_VERSION pins the gfx target to the MI300X family. The
#     rocm/vllm base image usually sets this already; we re-export so the
#     script is also runnable outside the image. If you're on a different
#     AMD GPU, override before sourcing.
#   * PYTORCH_HIP_ALLOC_CONF=expandable_segments:True reduces fragmentation
#     for long-running serving with continuous batching.
#   * VLLM_USE_TRITON_FLASH_ATTN=0 — the upstream Triton flash-attn kernels
#     have ROCm regressions; the rocm/vllm image ships AMD's flash-attn.
#   * --max-num-seqs 256 is what makes the concurrency demo land. Lower
#     means smaller batches; higher exhausts KV cache before fully utilizing
#     the GPU.
#   * --max-loras 8 leaves headroom; we currently load 5.
#   * --max-lora-rank 16 must be >= the rank used at training time.
#   * --gpu-memory-utilization 0.92 leaves ~16 GB for OS + KV-cache spill.

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

require_path() {
  if [ ! -d "$1" ]; then
    echo "error: missing LoRA adapter directory: $1" >&2
    exit 1
  fi
}

# Keep gfx override opt-in only; forcing it can break newer ROCm images.
if [ -n "${HSA_OVERRIDE_GFX_VERSION:-}" ]; then
  export HSA_OVERRIDE_GFX_VERSION
fi
# Prefer the current allocator env var name; keep HIP alias for compatibility.
export PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-expandable_segments:True}"
export PYTORCH_HIP_ALLOC_CONF="${PYTORCH_HIP_ALLOC_CONF:-$PYTORCH_ALLOC_CONF}"
export VLLM_USE_TRITON_FLASH_ATTN="${VLLM_USE_TRITON_FLASH_ATTN:-0}"
# ROCm vLLM docs recommend AITER kernels for MI300X-class GPUs.
export VLLM_ROCM_USE_AITER="${VLLM_ROCM_USE_AITER:-1}"

PORT="${VLLM_PORT:-8000}"
MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-72B-Instruct}"
ADAPTERS_DIR="${LORA_ADAPTERS_DIR:-./lora_adapters}"
PROFILE="${VLLM_PROFILE:-demo}" # demo|dev
ENABLE_LORA="${VLLM_ENABLE_LORA:-1}" # 1|0
MAX_LORAS="${VLLM_MAX_LORAS:-8}"
MAX_LORA_RANK="${VLLM_MAX_LORA_RANK:-16}"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"
TENSOR_PARALLEL_SIZE="${VLLM_TENSOR_PARALLEL_SIZE:-1}"

case "$PROFILE" in
  demo)
    GPU_MEMORY_UTIL="${VLLM_GPU_MEMORY_UTILIZATION:-0.95}"
    MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-256}"
    ;;
  dev)
    # Safer defaults for iterative debugging and lower-memory bring-up.
    GPU_MEMORY_UTIL="${VLLM_GPU_MEMORY_UTILIZATION:-0.90}"
    MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-128}"
    ;;
  *)
    echo "error: unsupported VLLM_PROFILE='$PROFILE' (use 'demo' or 'dev')" >&2
    exit 1
    ;;
esac

require_cmd vllm

echo "Starting vLLM on profile=$PROFILE port=$PORT model=$MODEL max_num_seqs=$MAX_NUM_SEQS lora=$ENABLE_LORA"

if [ "$ENABLE_LORA" = "1" ]; then
  require_path "$ADAPTERS_DIR/stcu_retail_auto"
  require_path "$ADAPTERS_DIR/unitus_community_cu"
  require_path "$ADAPTERS_DIR/exeter_finance"
  require_path "$ADAPTERS_DIR/family_savings_cu"
  require_path "$ADAPTERS_DIR/crouse_federal_cu"

  vllm serve "$MODEL" \
    --port "$PORT" \
    --enable-lora \
    --max-loras "$MAX_LORAS" \
    --max-lora-rank "$MAX_LORA_RANK" \
    --lora-modules \
      stcu_retail_auto="$ADAPTERS_DIR/stcu_retail_auto" \
      unitus_community_cu="$ADAPTERS_DIR/unitus_community_cu" \
      exeter_finance="$ADAPTERS_DIR/exeter_finance" \
      family_savings_cu="$ADAPTERS_DIR/family_savings_cu" \
      crouse_federal_cu="$ADAPTERS_DIR/crouse_federal_cu" \
    --dtype bfloat16 \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE"
else
  vllm serve "$MODEL" \
    --port "$PORT" \
    --dtype bfloat16 \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE"
fi
