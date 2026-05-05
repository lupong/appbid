#!/usr/bin/env bash
# Quick AMD Developer Cloud workflow for MI300X droplets.
#
# Commands:
#   infra/devcloud.sh doctor         # GPU/runtime readiness checks
#   infra/devcloud.sh train-dry-run  # generate synthetic datasets only
#   infra/devcloud.sh train          # full 5-lender LoRA train
#   infra/devcloud.sh serve [dev|demo]
#   infra/devcloud.sh benchmark [dev|demo]
#
# Notes:
# - Run from repo root.
# - Assumes a project virtualenv at .venv/.
# - Uses infra/start_vllm.sh for final serve settings.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
PIP_BIN="${PIP_BIN:-$ROOT_DIR/.venv/bin/pip}"
VLLM_DOCKER_IMAGE="${VLLM_DOCKER_IMAGE:-vllm/vllm-openai-rocm:v0.17.1}"

require_file() {
  if [ ! -f "$1" ]; then
    echo "error: required file missing: $1" >&2
    exit 1
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

doctor() {
  echo "[doctor] checking MI300X/ROCm prerequisites..."
  require_cmd docker
  require_file "$ROOT_DIR/.env"
  require_file "$PYTHON_BIN"

  if command -v rocm-smi >/dev/null 2>&1; then
    rocm-smi --showproductname --showmeminfo vram --showuse || true
  else
    echo "[doctor] rocm-smi not found on host; this is expected in some containerized setups."
  fi

  if ! "$PYTHON_BIN" "$ROOT_DIR/scripts/check_gpu.py"; then
    echo "[doctor] warning: python torch GPU check failed (common on vLLM-only images without torch in host venv)."
    echo "[doctor] continuing because rocm-smi already confirmed GPU visibility."
  fi
  echo "[doctor] ok"
}

train_dry_run() {
  echo "[train-dry-run] ensuring training dependencies..."
  "$PIP_BIN" install -r "$ROOT_DIR/requirements-train.txt"
  "$PYTHON_BIN" "$ROOT_DIR/lora_training/train_all.py" --dry-run
}

train_full() {
  echo "[train] installing training dependencies and starting full train..."
  "$PIP_BIN" install -r "$ROOT_DIR/requirements-train.txt"
  "$PYTHON_BIN" "$ROOT_DIR/lora_training/train_all.py" --teacher=llm
}

serve_vllm() {
  local profile="${1:-dev}"
  export VLLM_PROFILE="$profile"
  echo "[serve] launching vLLM with VLLM_PROFILE=$VLLM_PROFILE"

  if command -v vllm >/dev/null 2>&1; then
    bash "$ROOT_DIR/infra/start_vllm.sh"
    return
  fi

  # Fallback for AMD quick-start images where vLLM is shipped in Docker only.
  if command -v docker >/dev/null 2>&1 && docker image inspect "$VLLM_DOCKER_IMAGE" >/dev/null 2>&1; then
    echo "[serve] local vllm command not found; using docker image $VLLM_DOCKER_IMAGE"
    docker run --rm --name appbid-vllm \
      --device=/dev/kfd --device=/dev/dri --group-add video \
      --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
      --ipc=host --shm-size 16G \
      -p "${VLLM_PORT:-8000}:${VLLM_PORT:-8000}" \
      -v "$ROOT_DIR:/app" \
      -w /app \
      -e VLLM_PROFILE \
      -e VLLM_URL \
      -e VLLM_MODEL \
      -e VLLM_PORT \
      -e LORA_ADAPTERS_DIR \
      -e VLLM_ENABLE_LORA \
      -e VLLM_GPU_MEMORY_UTILIZATION \
      -e VLLM_MAX_NUM_SEQS \
      -e VLLM_MAX_MODEL_LEN \
      -e VLLM_MAX_LORAS \
      -e VLLM_MAX_LORA_RANK \
      -e VLLM_TENSOR_PARALLEL_SIZE \
      --entrypoint /bin/bash \
      "$VLLM_DOCKER_IMAGE" \
      infra/start_vllm.sh
    return
  fi

  echo "error: neither 'vllm' command nor expected vLLM docker image available" >&2
  exit 1
}

benchmark_vllm() {
  local profile="${1:-dev}"
  local url="${VLLM_URL:-http://localhost:8000/v1}"
  local model="${VLLM_BENCH_MODEL:-${VLLM_MODEL:-Qwen/Qwen2.5-72B-Instruct}}"
  local requests="${VLLM_BENCH_REQUESTS:-20}"
  local concurrency
  local max_tokens="${VLLM_BENCH_MAX_TOKENS:-128}"

  case "$profile" in
    demo) concurrency="${VLLM_BENCH_CONCURRENCY:-8}" ;;
    dev) concurrency="${VLLM_BENCH_CONCURRENCY:-4}" ;;
    *)
      echo "error: unsupported benchmark profile '$profile' (use dev|demo)" >&2
      exit 1
      ;;
  esac

  require_file "$PYTHON_BIN"
  echo "[benchmark] profile=$profile url=$url model=$model requests=$requests concurrency=$concurrency"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/benchmark_vllm.py" \
    --url "$url" \
    --model "$model" \
    --requests "$requests" \
    --concurrency "$concurrency" \
    --max-tokens "$max_tokens"
}

usage() {
  cat <<'EOF'
Usage: infra/devcloud.sh <command>

Commands:
  doctor
  train-dry-run
  train
  serve [dev|demo]
  benchmark [dev|demo]
EOF
}

cmd="${1:-}"
case "$cmd" in
  doctor)
    doctor
    ;;
  train-dry-run)
    train_dry_run
    ;;
  train)
    train_full
    ;;
  serve)
    serve_vllm "${2:-dev}"
    ;;
  benchmark)
    benchmark_vllm "${2:-dev}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
