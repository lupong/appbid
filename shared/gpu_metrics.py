"""Optional AMD GPU metrics via amdsmi.

``snapshot()`` returns a small dict suitable for adding to the concurrency
demo's live panel (utilization %, VRAM used/total, power, junction temp).
Returns an empty dict if ``amdsmi`` isn't installed or the call fails — the
caller should treat metrics as best-effort and not error if absent. This
lets the marketplace + agents run on a laptop without a GPU.
"""
from __future__ import annotations

from typing import Any

try:
    import amdsmi  # type: ignore[import-not-found]

    HAS_AMDSMI = True
except ImportError:
    HAS_AMDSMI = False


def snapshot() -> dict[str, Any]:
    """Return ``{util_pct, mem_used_gb, mem_total_gb, power_w, temp_c}`` for GPU 0.

    Empty dict on any error or when amdsmi isn't available — graceful degrade.
    """
    if not HAS_AMDSMI:
        return {}
    try:
        amdsmi.amdsmi_init()
        try:
            handles = amdsmi.amdsmi_get_processor_handles()
            if not handles:
                return {}
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
        return {}
