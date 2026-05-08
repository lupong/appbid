"""Best-effort live GPU telemetry for demo dashboards."""
from __future__ import annotations

from datetime import datetime, timezone
import re
import subprocess
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from shared.gpu_metrics import snapshot as gpu_snapshot

router = APIRouter(prefix="/gpu", tags=["gpu"])


class GpuMetrics(BaseModel):
    available: bool
    sampled_at: str
    util_pct: float = 0.0
    mem_used_gb: float = 0.0
    mem_total_gb: float = 0.0
    power_w: float = 0.0
    temp_c: float = 0.0


@router.get("/metrics", response_model=GpuMetrics)
async def get_gpu_metrics() -> GpuMetrics:
    snap: dict[str, Any] = gpu_snapshot()
    if not snap:
        snap = _fallback_snapshot_from_rocm_smi()
    sampled_at = datetime.now(timezone.utc).isoformat()
    if not snap:
        return GpuMetrics(available=False, sampled_at=sampled_at)
    return GpuMetrics(
        available=True,
        sampled_at=sampled_at,
        util_pct=float(snap.get("util_pct", 0.0)),
        mem_used_gb=float(snap.get("mem_used_gb", 0.0)),
        mem_total_gb=float(snap.get("mem_total_gb", 0.0)),
        power_w=float(snap.get("power_w", 0.0)),
        temp_c=float(snap.get("temp_c", 0.0)),
    )


def _fallback_snapshot_from_rocm_smi() -> dict[str, Any]:
    for cmd in ("rocm-smi", "/usr/bin/rocm-smi", "/opt/rocm/bin/rocm-smi"):
        try:
            proc = subprocess.run(
                [
                    cmd,
                    "--showuse",
                    "--showtemp",
                    "--showmeminfo",
                    "vram",
                    "--showpower",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            if not out.strip():
                continue
            util = re.search(r"GPU use \(%\):\s*([0-9]+(?:\.[0-9]+)?)", out)
            temp = re.search(
                r"Temperature \(Sensor junction\) \(C\):\s*([0-9]+(?:\.[0-9]+)?)",
                out,
            )
            power = re.search(
                r"Current Socket Graphics Package Power \(W\):\s*([0-9]+(?:\.[0-9]+)?)",
                out,
            )
            mem_total = re.search(r"VRAM Total Memory \(B\):\s*([0-9]+)", out)
            mem_used = re.search(r"VRAM Total Used Memory \(B\):\s*([0-9]+)", out)
            if not (util or temp or power or mem_total or mem_used):
                continue
            return {
                "util_pct": float(util.group(1)) if util else 0.0,
                "mem_used_gb": (float(mem_used.group(1)) if mem_used else 0.0)
                / (1024**3),
                "mem_total_gb": (float(mem_total.group(1)) if mem_total else 0.0)
                / (1024**3),
                "power_w": float(power.group(1)) if power else 0.0,
                "temp_c": float(temp.group(1)) if temp else 0.0,
            }
        except Exception:
            continue
    return {}
