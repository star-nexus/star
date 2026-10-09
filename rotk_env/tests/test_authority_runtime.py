"""Event-synchronized contracts for the production authority/display boundary."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

import pytest

from rotk_env.runtime.authority import AuthorityRuntime


class Runtime:
    def __init__(self):
        self._frame_capture = None
        self.calls = []
        self.ticks = 0
        self.epoch = 1
        self.closed = False
        self.stepped = Event()

    def step(self, dt, *, wall_time=None):
        self.calls.append(('step', dt, get_ident()))
        self.ticks += 1
        self.stepped.set()

    def execute_action(self, action, parameters=None, **kwargs):
        self.calls.append((action, parameters, get_ident()))
        if action == 'fatal':
            raise SystemExit('owner failed')
        if action == 'error':
            raise ValueError('successful prefix')
        if action == 'vlm':
            return self._frame_capture()
        return parameters

    def take_presentation_delta(self):
        return dict(epoch=self.epoch, revision=len(self.calls), tick=self.ticks)

    def reset(self, state):
        if state == 'bad':
            raise ValueError('reset failed')
        self.epoch += 1

    def diagnostics(self):
        return dict(epoch=self.epoch, tick=self.ticks)

    def close(self):
        self.closed = True


def test_one_owner_preserves_inputs_fifo_results_and_manual_clock():
    raw = Runtime(); rows = []
    owner = AuthorityRuntime(raw, on_publication=lambda row: rows.append(row))
    try:
        payload = {'path': [[1, 2]]}
        first = owner._admit('execute_action', ('first', payload), {})
        payload['path'][0][0] = 99
        second = owner._admit('execute_action', ('second', {}), {})
        assert first.result(2) == {'path': [[1, 2]]}
        assert second.result(2) == {}
        owner.step(.25, wall_time=1)
        owner.consume_presentation()
        assert [c[0] for c in raw.calls] == ['first', 'second', 'step']
        assert {c[2] for c in raw.calls} == {owner.scheduling_metrics()['owner_ident']}
        assert get_ident() not in {c[2] for c in raw.calls}
        assert rows[-1]['tick'] == 1
    finally:
        owner.close()
    assert raw.closed and owner.scheduling_metrics()['closed']


def test_background_request_finishes_without_ui_frame():
    raw = Runtime(); owner = AuthorityRuntime(raw, on_publication=lambda row: None)
    try:
        with ThreadPoolExecutor(1) as workers:
            assert workers.submit(owner.execute_action, 'read', {'x': 1}).result(2) == {'x': 1}
        assert raw.calls[0][0] == 'read'
    finally:
        owner.close()


def test_output_backpressure_is_drained_in_order_on_close():
    raw = Runtime(); rows = []
    owner = AuthorityRuntime(raw, on_publication=lambda row: rows.append(row), delta_capacity=1)
    try:
        first = owner._admit('_publish', (), {})
        first.result(2)
        second = owner._admit('_publish', (), {})  # admission pumps the first
        second.result(2)
        third = owner._admit('_publish', (), {})
        third.result(2)
    finally:
        owner.close()
    assert len(rows) == 3 and owner.scheduling_metrics()['published'] == 3
    assert owner.scheduling_metrics()['max_deltas'] == 1


def test_clock_advances_without_ui_and_stops_at_an_owner_fence():
    raw = Runtime(); owner = AuthorityRuntime(raw, on_publication=lambda row: None)
    try:
        owner.start_clock(.01)
        assert raw.stepped.wait(2)
        owner.stop_clock()
        count = raw.ticks
        assert not owner.clock_running and count >= 1
        assert owner.diagnostics()['tick'] == count
        owner.start_clock(.01)
        with pytest.raises(RuntimeError, match='manual step'):
            owner.step(.5)
        owner.stop_clock()
    finally:
        owner.close()


def test_reset_failure_and_clock_reset_fence():
    raw = Runtime(); owner = AuthorityRuntime(raw, on_publication=lambda row: None)
    try:
        with pytest.raises(ValueError, match='reset failed'):
            owner.reset('bad')
        assert owner.diagnostics()['epoch'] == 1
        owner.reset('good')
        assert owner.diagnostics()['epoch'] == 2
        owner.start_clock(.1)
        with pytest.raises(RuntimeError, match='stop'):
            owner.reset('good')
        owner.stop_clock()
        assert owner.diagnostics()['epoch'] == 2
    finally:
        owner.close()


def test_vlm_uses_ui_thread_and_blocks_later_owner_work():
    raw = Runtime(); rows = []; captures = []
    def capture():
        captures.append((get_ident(), tuple(c[0] for c in raw.calls), len(rows)))
        return ('bytes', None)
    owner = AuthorityRuntime(raw, on_publication=lambda row: rows.append(row), capture_frame=capture)
    try:
        first = owner._admit('execute_action', ('vlm', {}), {})
        # Direct admission models the host's already-accepted FIFO; later work
        # cannot execute until the display thread services the capture fence.
        later = owner._admit('execute_action', ('later', {}), {})
        while not first.done():
            owner.pump()
            with owner._condition:
                owner._condition.wait(.01)
        assert first.result(2) == ('bytes', None)
        assert later.result(2) == {}
        assert captures == [(get_ident(), ('vlm',), 1)]
    finally:
        owner.close()


def test_expected_error_retains_prefix_but_fatal_error_retires_owner():
    raw = Runtime(); owner = AuthorityRuntime(raw, on_publication=lambda row: None)
    try:
        with pytest.raises(ValueError, match='successful prefix'):
            owner.execute_action('error', {})
        assert owner.execute_action('after', {}) == {}
        with pytest.raises(SystemExit, match='owner failed'):
            owner.execute_action('fatal', {})
    finally:
        owner.close()
    assert raw.closed and owner.scheduling_metrics()['failure'] == 'SystemExit'


def test_failed_consumer_still_joins_and_releases_runtime():
    raw = Runtime()
    def broken(row):
        raise ValueError('display failed')
    owner = AuthorityRuntime(raw, on_publication=broken)
    owner._admit('_publish', (), {}).result(2)
    with pytest.raises(ValueError, match='display failed'):
        owner.close()
    assert raw.closed and owner.scheduling_metrics()['closed']


def test_full_output_blocks_owner_without_loss_until_ui_consumption():
    raw = Runtime(); second = Event(); rows = []
    step = raw.step
    def record(*args, **kwargs):
        step(*args, **kwargs)
        if raw.ticks == 2:
            second.set()
    raw.step = record
    owner = AuthorityRuntime(raw, on_publication=lambda row: rows.append(row), delta_capacity=1)
    try:
        owner.start_clock(.01)
        assert second.wait(2)
        with ThreadPoolExecutor(1) as workers:
            future = workers.submit(owner.execute_action, 'pending', {})
            with owner._condition:
                assert owner._condition.wait_for(lambda: len(owner._commands) == 1, 2)
            assert all(c[0] != 'pending' for c in raw.calls)
            owner.stop_clock()  # UI keeps draining while waiting for this fence.
            assert future.result(2) == {}
        assert [r['tick'] for r in rows[:2]] == [1, 2]
        assert owner.scheduling_metrics()['max_deltas'] == 1
    finally:
        owner.close()


@pytest.mark.parametrize('capacity', [0, -1, True, 1.5])
def test_invalid_capacity_starts_no_owner(capacity):
    raw = Runtime()
    with pytest.raises(ValueError):
        AuthorityRuntime(raw, on_publication=lambda row: None, inbox_capacity=capacity)
    assert not raw.closed
