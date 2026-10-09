"""E12 private scheduling/lifecycle contracts, deterministic synchronization."""
import json
from threading import Event, get_ident
import pytest

from rotk_env.runtime.authority_research import _AuthorityExecutor


class Runtime:
    def __init__(self):
        self.calls = []
        self.tick = 0
        self.epoch = 1
        self.closed = False
        self.block = Event()
        self.entered = Event()

    def execute_action(self, action, parameters=None, **kw):
        self.calls.append((get_ident(), action, parameters))
        if action == 'block':
            self.entered.set()
            self.block.wait()
        if action == 'error':
            raise ValueError('expected prefix')
        if action == 'panic':
            raise SystemExit('executor failure')
        return dict(action=action, parameters=parameters)

    def step(self, dt, **kw):
        self.tick += 1

    def take_presentation_delta(self):
        return dict(epoch=self.epoch, revision=self.tick, tick=self.tick,
                    events=[dict(tick=self.tick)])

    def reset(self, state):
        if state.get('bad'):
            raise ValueError('bad reset')
        self.epoch += 1
        self.tick = 0

    def close(self):
        self.closed = True


def test_frozen_inputs_fifo_owner_and_no_cancellation():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime)
    try:
        first = owner.submit('execute_action', 'block')
        assert runtime.entered.wait(2)
        params = {'ids': [1, 2]}
        second = owner.submit('execute_action', 'next', params)
        params['ids'].append(3)
        assert not second.cancel()
        runtime.block.set()
        first.result(2)
        assert second.result(2)['parameters'] == {'ids': [1, 2]}
        assert [c[1] for c in runtime.calls] == ['block', 'next']
        assert all(c[0] != get_ident() for c in runtime.calls)
        assert len({c[0] for c in runtime.calls}) == 1
    finally:
        runtime.block.set()
        owner.close()
    assert runtime.closed


def test_inbox_bound_rejects_without_admitting():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime, inbox_capacity=1)
    try:
        first = owner.submit('execute_action', 'block')
        assert runtime.entered.wait(2)
        accepted = owner.submit('execute_action', 'accepted')
        with pytest.raises(BufferError):
            owner.submit('execute_action', 'rejected')
        runtime.block.set()
        first.result(2)
        accepted.result(2)
    finally:
        runtime.block.set()
        owner.close()
    assert [c[1] for c in runtime.calls] == ['block', 'accepted']


def test_ordered_deltas_and_backpressure_close_drains_successful_prefix():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime, delta_capacity=1)
    owner.submit('step', .1).result(2)
    owner.submit('take_presentation_delta').result(2)
    owner.submit('step', .1).result(2)
    pending = owner.submit('take_presentation_delta')
    tail = owner.close()
    pending.result(2)
    assert [(p.sequence, p.tick) for p in tail] == [(0, 1), (1, 2)]
    assert [json.loads(p.json)['events'] for p in tail] == [[{'tick': 1}], [{'tick': 2}]]
    assert owner.metrics()['max_deltas'] == 1
    assert owner.close() == ()
    with pytest.raises(RuntimeError):
        owner.submit('step', .1)


def test_reset_fence_failed_reset_and_epoch():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime)
    try:
        owner.submit('take_presentation_delta').result(2)
        with pytest.raises(BufferError):
            owner.submit('reset', {}).result(2)
        old = owner.drain()[0]
        with pytest.raises(ValueError):
            owner.submit('reset', {'bad': True}).result(2)
        assert runtime.epoch == 1
        owner.submit('reset', {}).result(2)
        owner.submit('take_presentation_delta').result(2)
        new = owner.drain()[0]
        assert (old.epoch, new.epoch) == (1, 2)
        assert new.sequence == old.sequence + 1
        assert json.loads(old.json)['epoch'] == 1
    finally:
        owner.close()


def test_expected_errors_keep_owner_alive_and_prefix():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime)
    try:
        with pytest.raises(ValueError):
            owner.submit('execute_action', 'error').result(2)
        assert owner.submit('execute_action', 'next').result(2)['action'] == 'next'
        assert [c[1] for c in runtime.calls] == ['error', 'next']
    finally:
        owner.close()


def test_panic_joins_and_rejects_pending_without_hanging():
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime)
    failed = owner.submit('execute_action', 'panic')
    with pytest.raises(SystemExit):
        failed.result(2)
    owner.close()
    assert runtime.closed and owner.metrics()['closed']
    assert owner.metrics()['failure'] == 'SystemExit'


@pytest.mark.parametrize('args,kwargs', [(('get_faction_state_vlm',), {}),
                                       ((), {'action': 'get_faction_state_vlm'})])
def test_vlm_barrier_not_silently_bypassed(args, kwargs):
    runtime = Runtime()
    owner = _AuthorityExecutor(runtime)
    try:
        with pytest.raises(ValueError):
            owner.submit('execute_action', *args, **kwargs)
        assert runtime.calls == []
    finally:
        owner.close()


def test_invalid_configuration_and_operation_reject_before_work():
    runtime = Runtime()
    with pytest.raises(ValueError):
        _AuthorityExecutor(runtime, delta_capacity=0)
    owner = _AuthorityExecutor(runtime)
    try:
        with pytest.raises(ValueError):
            owner.submit('unknown')
        with pytest.raises(ValueError):
            owner.submit('step', float('nan'))
        assert runtime.calls == [] and runtime.tick == 0
    finally:
        owner.close()
