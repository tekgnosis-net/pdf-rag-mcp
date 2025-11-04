#!/bin/sh
set -e

CUDA_DEVICE="${EMBEDDING_DEVICE:-cpu}"
TORCH_INDEX_URL="${TORCH_CUDA_INDEX_URL:-https://download.pytorch.org/whl/cu124}"
TORCH_PKGS="${TORCH_CUDA_PACKAGES:-torch torchvision torchaudio}"

ensure_cuda_torch() {
  python - <<'PY'
import sys
try:
    import torch  # noqa: F401
except ModuleNotFoundError:
    sys.exit(1)

if getattr(torch.version, "cuda", None):
    sys.exit(0)
sys.exit(1)
PY
}

if [ "$CUDA_DEVICE" = "cuda" ]; then
  if ensure_cuda_torch; then
    printf "CUDA-enabled PyTorch already present.\n"
  else
    printf "CUDA requested; installing CUDA-enabled PyTorch wheels...\n"
    pip install --no-cache-dir --upgrade --extra-index-url "$TORCH_INDEX_URL" $TORCH_PKGS
  fi
fi

exec "$@"
