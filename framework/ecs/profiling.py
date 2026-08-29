"""Optional profiling hook for the ECS core.

`framework` used to `from performance_profiler import profiler`, a module at the
repository root. That made the ECS depend upwards on its own consumer's layout,
so the package could not be tested or extracted on its own.

The default is a no-op. The ENV entry point installs the real profiler with
`set_profiler(...)` at startup.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class Profiler(Protocol):
    """The slice of the profiler API the framework actually calls."""

    def time_system(self, name: str) -> Any: ...
    def start_frame(self) -> None: ...
    def print_stats(self) -> None: ...


class NullProfiler:
    """Zero-cost default. Keeps call sites free of `if profiler is not None`."""

    @contextmanager
    def time_system(self, name: str) -> Iterator[None]:
        yield

    def start_frame(self) -> None:
        pass

    def print_stats(self) -> None:
        pass


_NULL = NullProfiler()
profiler: Profiler = _NULL


def set_profiler(impl: Profiler | None) -> None:
    """Install a profiler, or `None` to go back to the no-op."""
    global profiler
    profiler = _NULL if impl is None else impl


def get_profiler() -> Profiler:
    return profiler


__all__ = ["Profiler", "NullProfiler", "set_profiler", "get_profiler", "profiler"]
