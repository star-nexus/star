"""Regression tests for large non-blocking scale-harness replies."""

import json

from rotk_env.testing.scale_experiment_measurement import (
    _install_reliable_socket_output,
)


class _FakeHarness:
    def __init__(self):
        self.dropped = []

    def _drop_client(self, client):
        self.dropped.append(client)
        client.close()


class _PartialSocket:
    """Non-blocking socket double that back-pressures after one partial write."""

    def __init__(self, *, chunk_size=64):
        self.chunk_size = chunk_size
        self.output = bytearray()
        self.closed = False
        self._calls = 0
        self._blocked_once = False

    def send(self, data):
        self._calls += 1
        # First write succeeds partially; second write simulates EWOULDBLOCK.
        if self._calls == 2 and not self._blocked_once:
            self._blocked_once = True
            raise BlockingIOError()
        amount = min(len(data), self.chunk_size)
        self.output.extend(bytes(data[:amount]))
        return amount

    def close(self):
        self.closed = True


def test_large_reply_survives_nonblocking_partial_send():
    harness = _FakeHarness()
    _install_reliable_socket_output(harness)
    client = _PartialSocket(chunk_size=37)
    response = {
        "ok": True,
        "snapshot": "x" * 20_000,
        "sections": list(range(200)),
    }
    expected = (
        json.dumps(response, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    harness._send_response(client, response)

    # Back-pressure must retain the unsent suffix rather than dropping client.
    assert client in harness._scale_pending_output
    assert harness.dropped == []
    assert client.closed is False

    for _ in range(1000):
        if client not in harness._scale_pending_output:
            break
        harness._flush_scale_socket_output()

    assert client not in harness._scale_pending_output
    assert bytes(client.output) == expected
    assert harness.dropped == []
    assert client.closed is False


def test_broken_peer_drops_pending_output_cleanly():
    harness = _FakeHarness()
    _install_reliable_socket_output(harness)

    class _BrokenSocket(_PartialSocket):
        def send(self, data):
            raise BrokenPipeError()

    client = _BrokenSocket()
    harness._send_response(client, {"ok": True, "payload": "x" * 1000})

    assert client not in harness._scale_pending_output
    assert harness.dropped == [client]
    assert client.closed is True
