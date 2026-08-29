"""Request ids and correlation keys.

`docs/agent-protocol.md` allows a request `id` to be an int *or* a string, and
the Hub round-trips JSON. An id that leaves as `123` and comes back as `"123"`
would silently fail correlation and surface as a timeout, so every id is
normalised to a canonical string key on both send and receive.

Ids are also kept short and JSON-safe. The previous `uuid.uuid4().int` produced
a 128-bit integer: ~39 decimal digits, well past the 2**53 that JSON consumers
are guaranteed to preserve, and unreadable in logs.
"""

from __future__ import annotations

import itertools
import os
from typing import Any

# Process-unique prefix so ids stay distinct when several agents share a Hub
# and their logs are read side by side.
_PID = os.getpid()
_counter = itertools.count(1)


def gen_id(prefix: str = "") -> str:
    """Return a short, unique, JSON-safe request id."""
    n = next(_counter)
    base = f"{_PID}-{n}"
    return f"{prefix}-{base}" if prefix else base


def normalize_id(raw: Any) -> Any:
    """Canonical correlation key.

    Ints and numeric strings collapse to the same key, so `123` and `"123"`
    correlate. Anything else is returned unchanged so it can still be used as a
    dict key without silently mangling it.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, str)):
        return str(raw).strip()
    return raw


__all__ = ["gen_id", "normalize_id"]
