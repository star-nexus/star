"""One-slot display mailbox. Overflow replaces deltas with a complete snapshot.

This is for disposable display state, never Agent responses or reliable events.
The producer supplies a snapshot at the exact revision of the replacement.
"""

from copy import deepcopy
from threading import Lock


class SnapshotMailbox:
    def __init__(self):
        self._lock = Lock()
        self._pending = None
        self._closed = False
        self.resyncs = 0

    def offer(self, packet, snapshot):
        with self._lock:
            if self._closed:
                return False
            if self._pending is not None:
                packet = snapshot
                self.resyncs += 1
            self._pending = deepcopy(packet)
            return True

    def take(self):
        with self._lock:
            packet, self._pending = self._pending, None
            return packet

    def close(self):
        with self._lock:
            self._closed = True
            self._pending = None
