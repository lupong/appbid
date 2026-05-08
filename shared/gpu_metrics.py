"""Optional AMD GPU metrics via amdsmi.

``snapshot()`` returns a small dict suitable for adding to the concurrency
demo's live panel (utilization %, VRAM used/total, power, junction temp).
Returns an empty dict if ``amdsmi`` isn't installed or the call fails — the
caller should treat metrics as best-effort and not error if absent. This
lets the marketplace + agents run on a laptop without a GPU.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any

try:
    import amdsmi  # type: ignore[import-not-found]

    HAS_AMDSMI = True
except Exception:
    # Some environments install the Python package without the ROCm shared
    # library present (libamd_smi.so). Treat as unavailable and degrade
    # gracefully instead of crashing app startup.
    HAS_AMDSMI = False


def snapshot() -> dict[str, Any]:
    """Return ``{util_pct, mem_used_gb, mem_total_gb, power_w, temp_c}`` for GPU 0.

    Empty dict on any error or when amdsmi isn't available — graceful degrade.
    """
    if not HAS_AMDSMI:
        return _snapshot_from_rocm_smi()
    try:
        amdsmi.amdsmi_init()
        try:
            handles = amdsmi.amdsmi_get_processor_handles()
            if not handles:
                return _snapshot_from_rocm_smi()
            h = handles[0]
            activity = amdsmi.amdsmi_get_gpu_activity(h)
            mem_used = amdsmi.amdsmi_get_gpu_memory_usage(
                h, amdsmi.AmdSmiMemoryType.VRAM
            )
            mem_total = amdsmi.amdsmi_get_gpu_memory_total(
                h, amdsmi.AmdSmiMemoryType.VRAM
            )
            power = amdsmi.amdsmi_get_power_info(h)
            temp = amdsmi.amdsmi_get_temp_metric(
                h,
                amdsmi.AmdSmiTemperatureType.JUNCTION,
                amdsmi.AmdSmiTemperatureMetric.CURRENT,
            )
            return {
                "util_pct": activity["gfx_activity"],
                "mem_used_gb": mem_used / (1024**3),
                "mem_total_gb": mem_total / (1024**3),
                "power_w": power["current_socket_power"],
                "temp_c": temp,
            }
        finally:
            amdsmi.amdsmi_shut_down()
    except Exception:
        return _snapshot_from_rocm_smi()


def _snapshot_from_rocm_smi() -> dict[str, Any]:
    """Best-effort fallback parser for rocm-smi output.

    Useful on hosts where the CLI works but amdsmi Python bindings are absent.
    """
    try:
        out = ""
        for cmd in ("rocm-smi", "/usr/bin/rocm-smi", "/opt/rocm/bin/rocm-smi"):
            try:
                proc = subprocess.run(
                    [
                        cmd,
                        "--showuse",
                        "--showtemp",
                        "--showmemuse",
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
                if out.strip():
                    break
            except Exception:
                continue
        if not out.strip():
            return {}

        util_match = re.search(r"GPU use \(%\):\s*([0-9]+(?:\.[0-9]+)?)", out)
        temp_match = re.search(
            r"Temperature \(Sensor junction\) \(C\):\s*([0-9]+(?:\.[0-9]+)?)", out
        )
        power_match = re.search(
            r"Current Socket Graphics Package Power \(W\):\s*([0-9]+(?:\.[0-9]+)?)",
            out,
        )
        mem_total_match = re.search(r"VRAM Total Memory \(B\):\s*([0-9]+)", out)
        mem_used_match = re.search(r"VRAM Total Used Memory \(B\):\s*([0-9]+)", out)

        util_pct = float(util_match.group(1)) if util_match else 0.0
        temp_c = float(temp_match.group(1)) if temp_match else 0.0
        power_w = float(power_match.group(1)) if power_match else 0.0
        mem_total_b = float(mem_total_match.group(1)) if mem_total_match else 0.0
        mem_used_b = float(mem_used_match.group(1)) if mem_used_match else 0.0

        if util_pct == 0 and temp_c == 0 and power_w == 0 and mem_total_b == 0:
            return {}

        return {
            "util_pct": util_pct,
            "mem_used_gb": mem_used_b / (1024**3),
            "mem_total_gb": mem_total_b / (1024**3),
            "power_w": power_w,
            "temp_c": temp_c,
        }
    except Exception:
        return {}
