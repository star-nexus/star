"""Request/response correlation.

Covers the failure modes the three hand-rolled implementations had between them:
an id that changes type in transit, an outcome that arrives before its awaiter,
a disconnect leaving callers blocked, and a timeout that never cleans up.
"""

import asyncio

import pytest

from protocol.star_client_v2.correlation import Correlator
from protocol.star_client_v2.exceptions import (
    ActionTimeout,
    ConnectionError as ClientConnectionError,
    ProtocolError,
)
from protocol.star_client_v2.ids import gen_id, normalize_id


# ------------------------------------------------------------------ id keys


def test_int_and_str_ids_are_the_same_key():
    """The bug this normalisation exists for.

    The Hub round-trips JSON, so an id sent as `123` can come back as `"123"`.
    Two of the old implementations keyed on the raw value and silently failed to
    match, which surfaced to the agent as a spurious timeout.
    """
    assert normalize_id(123) == normalize_id("123")


def test_normalize_id_strips_whitespace():
    assert normalize_id(" 42 ") == normalize_id(42)


def test_normalize_id_passes_through_unusual_values():
    for value in (None, (1, 2)):
        assert normalize_id(value) == value


def test_gen_id_is_short_and_json_safe():
    """`uuid.uuid4().int` was 128-bit: past 2**53, so JSON layers could mangle it."""
    for _ in range(50):
        request_id = gen_id()
        assert isinstance(request_id, str)
        assert len(request_id) < 30, request_id


def test_gen_id_is_unique():
    assert len({gen_id() for _ in range(1000)}) == 1000


def test_gen_id_prefix_is_visible():
    assert gen_id("batch").startswith("batch-")


# -------------------------------------------------------------- basic matching


async def test_resolve_wakes_the_waiter():
    c = Correlator()
    key = c.expect("req-1")
    task = asyncio.create_task(c.wait(key, timeout=1.0))
    await asyncio.sleep(0)
    assert c.resolve("req-1", {"success": True}) is True
    assert await task == {"success": True}


async def test_resolve_matches_across_id_types():
    """End-to-end version of the normalisation test."""
    c = Correlator()
    c.expect(7)
    task = asyncio.create_task(c.wait(7, timeout=1.0))
    await asyncio.sleep(0)
    c.resolve("7", "answered")  # came back from JSON as a string
    assert await task == "answered"


async def test_outcome_arriving_before_the_awaiter_is_not_lost():
    """The race a plain create-then-await would drop."""
    c = Correlator()
    c.expect("req-2")
    c.resolve("req-2", "early")
    assert await c.wait("req-2", timeout=1.0) == "early"


async def test_wait_without_expect_still_works():
    c = Correlator()
    task = asyncio.create_task(c.wait("never-expected", timeout=1.0))
    await asyncio.sleep(0)
    c.resolve("never-expected", "ok")
    assert await task == "ok"


async def test_resolve_reports_whether_anyone_was_waiting():
    c = Correlator()
    assert c.resolve("nobody", "x") is False
    c.expect("somebody")
    assert c.resolve("somebody", "x") is True


# ---------------------------------------------------------------- timeouts


async def test_timeout_raises_action_timeout_with_context():
    c = Correlator()
    c.expect("slow")
    with pytest.raises(ActionTimeout) as excinfo:
        await c.wait("slow", timeout=0.01, action="move")
    assert excinfo.value.action == "move"
    assert excinfo.value.request_id == "slow"
    assert excinfo.value.timeout_seconds == 0.01


async def test_timeout_does_not_leak_the_waiter():
    c = Correlator()
    c.expect("slow")
    with pytest.raises(ActionTimeout):
        await c.wait("slow", timeout=0.01)
    assert c.pending_ids == []
    assert len(c) == 0


async def test_successful_wait_does_not_leak_the_waiter():
    c = Correlator()
    c.expect("fast")
    c.resolve("fast", 1)
    await c.wait("fast", timeout=1.0)
    assert c.pending_ids == []
    assert c.unclaimed_ids == []


# ------------------------------------------------------------------- errors


async def test_fail_raises_at_the_await_site():
    c = Correlator()
    c.expect("bad")
    task = asyncio.create_task(c.wait("bad", timeout=1.0))
    await asyncio.sleep(0)
    c.fail("bad", ProtocolError("env rejected it", "bad"))
    with pytest.raises(ProtocolError):
        await task


async def test_failing_an_unawaited_slot_is_quiet(recwarn):
    """No "Future exception was never retrieved" noise on stderr.

    A slot can be failed with nobody awaiting it: a fire-and-forget send, or a
    caller that already timed out. Callers that *are* waiting still see the
    exception raised at their await; see the tests above.
    """
    import gc

    c = Correlator()
    c.expect("nobody-waits")
    c.abandon_all(ClientConnectionError("bye"))

    c2 = Correlator()
    c2.expect("also-nobody")
    c2.fail("also-nobody", ProtocolError("x", "also-nobody"))

    del c, c2
    gc.collect()


async def test_abandon_all_keeps_the_waiters_mapping_ordered():
    """Pruning relies on insertion order, so the swap must preserve the type."""
    c = Correlator()
    c.expect("a")
    c.abandon_all(ClientConnectionError("bye"))
    c.expect("b")
    c.expect("c")
    assert c.pending_ids == ["b", "c"]


async def test_abandoned_slots_are_bounded():
    """A caller that sends without ever awaiting must not grow memory forever."""
    c = Correlator(max_waiters=4)
    for i in range(100):
        c.expect(f"sent-{i}")
        c.resolve(f"sent-{i}", i)  # answered, but never awaited
    assert len(c.pending_ids) <= 5, c.pending_ids


async def test_abandon_all_fails_every_waiter():
    """A disconnect should fail fast, not make each caller wait out its timeout."""
    c = Correlator()
    for i in range(3):
        c.expect(f"r{i}")
    tasks = [asyncio.create_task(c.wait(f"r{i}", timeout=30.0)) for i in range(3)]
    await asyncio.sleep(0)

    assert c.abandon_all(ClientConnectionError("hub went away")) == 3
    for task in tasks:
        with pytest.raises(ClientConnectionError):
            await task
    assert c.pending_ids == []


async def test_discard_forgets_a_request_that_never_left():
    c = Correlator()
    c.expect("unsent")
    c.discard("unsent")
    assert c.pending_ids == []
    # A later outcome for it is unclaimed, not delivered to a stale waiter.
    assert c.resolve("unsent", "late") is False


async def test_fail_for_an_unknown_id_is_a_no_op():
    c = Correlator()
    assert c.fail("nobody", ProtocolError("x", "nobody")) is False


# ------------------------------------------------------------------ bounding


async def test_unclaimed_outcomes_are_bounded():
    """A peer answering requests nobody reads must not grow memory forever."""
    c = Correlator(max_unclaimed=4)
    for i in range(50):
        c.resolve(f"orphan-{i}", i)
    assert len(c.unclaimed_ids) == 4
    # Oldest dropped, newest kept.
    assert await c.wait("orphan-49", timeout=0.1) == 49


async def test_concurrent_requests_do_not_cross_wires():
    c = Correlator()
    ids = [f"req-{i}" for i in range(20)]
    for request_id in ids:
        c.expect(request_id)
    tasks = {rid: asyncio.create_task(c.wait(rid, timeout=1.0)) for rid in ids}
    await asyncio.sleep(0)

    for i, request_id in enumerate(reversed(ids)):  # answer out of order
        c.resolve(request_id, i)

    results = {rid: await task for rid, task in tasks.items()}
    for i, request_id in enumerate(reversed(ids)):
        assert results[request_id] == i
