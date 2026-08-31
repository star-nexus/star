"""Optional profiling hook for the ECS core.

The framework stays independent from STAR's concrete profiler. The ENV entry
point installs the real profiler at startup; tests and extracted framework use
fall back to the no-op implementation below.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class Profiler(Protocol):
    """Profiler API consumed by the framework / engine."""

    def time_system(self, name: str, *, category: str = "work") -> Any: ...
    def start_frame(self) -> None: ...
    def end_frame(self) -> None: ...
    def print_stats(self) -> None: ...
    def set_metadata(self, **values: object) -> None: ...


class NullProfiler:
    """Zero-cost default. Keeps call sites free of ``if profiler`` branches."""

    @contextmanager
    def time_system(self, name: str, *, category: str = "work") -> Iterator[None]:
        yield

    def start_frame(self) -> None:
        pass

    def end_frame(self) -> None:
        pass

    def print_stats(self) -> None:
        pass

    def set_metadata(self, **values: object) -> None:
        pass


_NULL = NullProfiler()
profiler: Profiler = _NULL


def set_profiler(impl: Profiler | None) -> None:
    """Install a profiler, or ``None`` to restore the no-op implementation."""
    global profiler
    profiler = _NULL if impl is None else impl


def get_profiler() -> Profiler:
    return profiler


__all__ = ["Profiler", "NullProfiler", "set_profiler", "get_profiler", "profiler"]
