"""Deferred measurement-epoch control for Scale Test Harness.

Scale workload commands execute inside the ENV main-frame timer stack. Resetting
PerformanceProfiler from inside that stack would corrupt the current frame's
hierarchical timers. This helper therefore schedules the reset for the *next*
``start_frame`` boundary: planning and kickoff stay in the previous epoch, while
the first post-kickoff frame becomes sample 1 of the execution epoch.

The hook is installed only when Scale Test Harness is explicitly mounted. Normal
ENV/profiler behavior is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict

_INSTALLED = "_scale_epoch_hook_installed"
_PENDING = "_scale_pending_measurement_epoch"
_ORIGINAL_START = "_scale_epoch_original_start_frame"
_SERIAL = "_scale_epoch_serial"


def install_deferred_epoch_hook(profiler: Any) -> bool:
    """Install a one-instance deferred-reset hook if the profiler supports it."""
    if bool(getattr(profiler, _INSTALLED, False)):
        return True

    reset = getattr(profiler, "reset", None)
    original_start = getattr(profiler, "start_frame", None)
    set_metadata = getattr(profiler, "set_metadata", None)
    if not callable(reset) or not callable(original_start) or not callable(set_metadata):
        return False

    setattr(profiler, _ORIGINAL_START, original_start)
    setattr(profiler, _SERIAL, int(getattr(profiler, _SERIAL, 0)))
    setattr(profiler, _PENDING, None)

    def _start_frame_with_epoch_boundary() -> None:
        pending = getattr(profiler, _PENDING, None)
        frame_open = bool(getattr(profiler, "_frame_open", False))
        if pending is not None and not frame_open:
            setattr(profiler, _PENDING, None)
            profiler.reset()
            serial = int(getattr(profiler, _SERIAL, 0)) + 1
            setattr(profiler, _SERIAL, serial)
            metadata = dict(pending.get("metadata", {}))
            metadata.update(
                measurement_epoch=str(pending["name"]),
                measurement_epoch_serial=serial,
            )
            profiler.set_metadata(**metadata)
        original_start()

    profiler.start_frame = _start_frame_with_epoch_boundary
    setattr(profiler, _INSTALLED, True)
    return True


def request_measurement_epoch(
    profiler: Any,
    name: str,
    **metadata: object,
) -> bool:
    """Schedule a clean profiler epoch at the next safe frame boundary."""
    if not install_deferred_epoch_hook(profiler):
        return False
    setattr(
        profiler,
        _PENDING,
        {
            "name": str(name),
            "metadata": dict(metadata),
        },
    )
    return True


def measurement_epoch_pending(profiler: Any) -> bool:
    return getattr(profiler, _PENDING, None) is not None


def pending_measurement_epoch(profiler: Any) -> Dict[str, object] | None:
    pending = getattr(profiler, _PENDING, None)
    return dict(pending) if isinstance(pending, dict) else None
