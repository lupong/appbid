"""Verify the AMD MI300X is visible to PyTorch and we can allocate VRAM.

Run after spinning up the droplet to confirm ROCm + PyTorch see the GPU.
On a healthy MI300X box this prints "AMD Instinct MI300X" with ~192 GB and
finishes a small matmul.
"""
from __future__ import annotations


def main() -> None:
    try:
        import torch
    except ImportError:
        print("torch not installed; this script must run inside the rocm/pytorch image")
        raise SystemExit(1)

    print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
    print(f"device count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"  GPU {i}: {p.name}, {p.total_memory / 1e9:.1f} GB")
    if torch.cuda.is_available():
        x = torch.randn(1024, 1024, device="cuda")
        y = x @ x.T
        print(f"matmul on GPU works, sum={y.sum().item():.4f}")
    else:
        print("no GPU detected by torch — check ROCm + driver match")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
