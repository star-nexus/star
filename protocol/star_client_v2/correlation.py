"""Request/response correlation for the agent side of the protocol.

The SDK used to hand out a request id and leave correlation to the caller. Three
implementations grew (`rotk_agent/core/bridge.py`, `rotk_agent/core/runner.py`,
`examples/protocol_conformance.py`), each with its own dict, its own polling
loop, and its own idea of whether an id is an int or a string. That mismatch
surfaced as spurious timeouts: the Hub round-trips JSON, so an id sent as `123`
could come back as `"123"` and never match.

One correlator, keyed by `normalize_id`, resolving `asyncio.Future`s.

The awkward part this class exists to own: an outcome can arrive *before* anyone
awaits it (the ENV is fast, or the caller sent then did other work). A plain
"create future, then await" would drop it. So a slot holds either a waiter or an
already-delivered value, whichever comes first.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Any, Dict, Optional

from .exceptions import ActionTimeout
from .ids import normalize_id


class Correlator:
    """Matches inbound outcomes to outbound requests.

    Not thread-safe by design: everything runs on one asyncio loop.
    """

    def __init__(self, max_unclaimed: int = 512):
        # Insertion-ordered so abandoned slots can be pruned oldest-first.
        self._waiters: "OrderedDict[Any, asyncio.Future]" = OrderedDict()
        # Outcomes for ids nobody registered. Bounded so a peer that answers
        # requests nobody reads cannot grow this without limit.
        self._unclaimed: "OrderedDict[Any, Any]" = OrderedDict()
        self._max_unclaimed = max_unclaimed

    # ---------------------------------------------------------------- sending

    def expect(self, request_id: Any) -> Any:
        """Register interest in `request_id`. Call before sending.

        Returns the normalised key, which is what everything else is keyed by.
        """
        key = normalize_id(request_id)
        if key not in self._waiters and key not in self._unclaimed:
            self._waiters[key] = asyncio.get_running_loop().create_future()
            self._prune_abandoned()
        return key

    # --------------------------------------------------------------- receiving

    def resolve(self, request_id: Any, value: Any) -> bool:
        """Deliver an outcome. True if the request was registered.

        The future is deliberately *not* removed here. `expect` runs before the
        send, so an outcome can arrive while the caller is still between `send`
        and `await`; popping on resolve would drop the value on the floor and
        the caller would then time out holding a fresh, never-resolved future.
        `wait` owns removal.
        """
        key = normalize_id(request_id)
        future = self._waiters.get(key)
        if future is not None:
            if not future.done():
                future.set_result(value)
            return True
        self._park(key, value)
        return False

    def fail(self, request_id: Any, error: BaseException) -> bool:
        """Deliver an error for a request. True if the request was registered."""
        key = normalize_id(request_id)
        future = self._waiters.get(key)
        if future is None:
            return False
        if not future.done():
            future.set_exception(error)
            # Nothing may ever await this, and an unretrieved exception is noisy
            # at GC time. Mark it seen; `wait` re-raises from the future anyway.
            future.exception()
        return True

    def discard(self, request_id: Any) -> None:
        """Forget a request outright.

        For sends that never left the process: no outcome can ever arrive, so
        unlike `fail` this leaves nothing behind for `wait` to collect.
        """
        key = normalize_id(request_id)
        future = self._waiters.pop(key, None)
        if future is not None and not future.done():
            future.cancel()
        self._unclaimed.pop(key, None)

    def _park(self, key: Any, value: Any) -> None:
        """Hold an outcome for an id nobody registered."""
        self._unclaimed[key] = value
        self._unclaimed.move_to_end(key)
        while len(self._unclaimed) > self._max_unclaimed:
            self._unclaimed.popitem(last=False)

    def _prune_abandoned(self) -> None:
        """Drop settled futures nobody ever awaited.

        A slot that is `done` and still present was resolved but never claimed
        (fire-and-forget, or a caller that gave up). Those are the only entries
        safe to discard: a pending slot may still have a live awaiter.
        """
        if len(self._waiters) <= self._max_unclaimed:
            return
        for key in [k for k, f in self._waiters.items() if f.done()]:
            del self._waiters[key]
            if len(self._waiters) <= self._max_unclaimed:
                return

    # ---------------------------------------------------------------- awaiting

    async def wait(
        self,
        request_id: Any,
        timeout: float,
        *,
        action: str = "<unknown>",
    ) -> Any:
        """Await the outcome for `request_id`.

        Raises `ActionTimeout` if it does not arrive in `timeout` seconds.
        """
        key = normalize_id(request_id)

        if key in self._unclaimed:
            return self._unclaimed.pop(key)

        future = self._waiters.get(key)
        if future is None:
            # Nobody called `expect`. Register now; the outcome may still be in
            # flight. This is the path a caller who hand-rolled an id takes.
            future = asyncio.get_running_loop().create_future()
            self._waiters[key] = future

        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except asyncio.TimeoutError:
            raise ActionTimeout(action, request_id, timeout) from None
        finally:
            self._waiters.pop(key, None)

    # ------------------------------------------------------------- lifecycle

    def abandon_all(self, error: BaseException) -> int:
        """Fail every outstanding waiter. Used when the connection drops.

        Without this, a disconnect leaves callers blocked until each individual
        timeout expires instead of failing fast.
        """
        waiters, self._waiters = self._waiters, {}
        count = 0
        for future in waiters.values():
            if not future.done():
                future.set_exception(error)
                count += 1
        return count

    # ------------------------------------------------------------ diagnostics

    @property
    def pending_ids(self) -> list:
        return list(self._waiters)

    @property
    def unclaimed_ids(self) -> list:
        return list(self._unclaimed)

    def __len__(self) -> int:
        return len(self._waiters)


__all__ = ["Correlator"]
