"""Lightweight process-memory sampling without an optional psutil dependency.

Soak tests sample only at explicit safe points, never from the realtime hot loop.
Linux reads /proc directly; macOS asks `ps` for the current RSS. A max-RSS
fallback keeps the probe usable on other Unix-like platforms.
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
from typing import Any, Dict, Optional


def _linux_current_rss_bytes() -> Optional[int]:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
    except (OSError, ValueError):
        return None
    return None


def _darwin_current_rss_bytes() -> Optional[int]:
    try:
        output = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        ).strip()
        if output:
            return int(output.split()[0]) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def _max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Darwin reports bytes; Linux and most BSD-style ports report KiB.
    return value if sys.platform == "darwin" else value * 1024


def process_memory_snapshot() -> Dict[str, Any]:
    """Return current RSS when available plus the process high-water mark."""
    if sys.platform.startswith("linux"):
        current = _linux_current_rss_bytes()
        source = "proc_self_status" if current is not None else "maxrss_fallback"
    elif sys.platform == "darwin":
        current = _darwin_current_rss_bytes()
        source = "ps_rss" if current is not None else "maxrss_fallback"
    else:
        current = None
        source = "maxrss_fallback"

    maximum = _max_rss_bytes()
    if current is None:
        current = maximum

    mib = 1024.0 * 1024.0
    return {
        "rss_bytes": int(current),
        "rss_mb": round(float(current) / mib, 3),
        "max_rss_bytes": int(maximum),
        "max_rss_mb": round(float(maximum) / mib, 3),
        "rss_source": source,
    }
