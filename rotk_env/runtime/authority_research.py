"""Private E12 owner-thread primitive; no scene or protocol default uses it.

The host must supply the ordered request/tick stream. This primitive does not
choose admission times, run a simulation clock, drop deltas, or capture VLM
frames. SDL and the derived display World stay with the UI caller.
"""
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
import json
from threading import Condition, Thread, get_ident


@dataclass(frozen=True)
class _Publication:
    sequence: int
    epoch: int
    revision: int
    tick: int
    json: str


class _AuthorityExecutor:
    """Transfer an existing runtime exclusively to one research worker.

    submit freezes JSON inputs before admission and rejects a full inbox without
    executing anything. Accepted commands always execute in FIFO order. Output
    backpressure blocks the owner rather than discarding an incremental update.
    close drains and returns every outstanding publication, then joins the owner;
    callers must consume these publications if display/event preservation matters.
    """
    _METHODS = frozenset({
        'step', 'execute_action', 'get_faction_state_json', 'execute_control',
        'set_clock', 'host_status', 'diagnostics', 'export_state', 'reset',
        'take_presentation_delta', 'finish_human_turn', 'start_capture',
    })

    def __init__(self, runtime, *, inbox_capacity=32, delta_capacity=8):
        if type(inbox_capacity) is not int or inbox_capacity < 1:
            raise ValueError('invalid inbox capacity')
        if type(delta_capacity) is not int or delta_capacity < 1:
            raise ValueError('invalid delta capacity')
        self._runtime = runtime
        self._inbox_capacity = inbox_capacity
        self._delta_capacity = delta_capacity
        self._commands = deque()
        self._publications = deque()
        self._condition = Condition()
        self._accepting = True
        self._closed = False
        self._failure = None
        self._sequence = 0
        self._owner_ident = None
        self._max_inbox = 0
        self._max_deltas = 0
        self._thread = Thread(target=self._run, name='star-e12-authority')
        self._thread.start()

    def submit(self, method, *args, **kwargs):
        if method not in self._METHODS:
            raise ValueError('unsupported owner research operation')
        action = args[0] if args else kwargs.get('action')
        if method == 'execute_action' and action == 'get_faction_state_vlm':
            raise ValueError('VLM requires a UI revision barrier; outside this prototype')
        # Input objects may be reused/mutated by callers after admission.
        payload = json.dumps([args, kwargs], allow_nan=False)
        future = Future()
        future.set_running_or_notify_cancel()  # accepted work cannot be cancelled
        with self._condition:
            if not self._accepting or self._failure is not None:
                raise RuntimeError('authority executor is closed or failed')
            if len(self._commands) >= self._inbox_capacity:
                raise BufferError('authority inbox is full; nothing admitted')
            self._commands.append((method, payload, future))
            self._max_inbox = max(self._max_inbox, len(self._commands))
            self._condition.notify_all()
        return future

    def drain(self):
        with self._condition:
            result = tuple(self._publications)
            self._publications.clear()
            self._condition.notify_all()
            return result

    def _publish(self, delta):
        packet = _Publication(self._sequence, delta['epoch'], delta['revision'],
                              delta['tick'], json.dumps(delta, allow_nan=False))
        with self._condition:
            while len(self._publications) >= self._delta_capacity:
                self._condition.wait()
            self._publications.append(packet)
            self._sequence += 1
            self._max_deltas = max(self._max_deltas, len(self._publications))
            self._condition.notify_all()
        return packet.sequence

    def _execute(self, method, args, kwargs):
        if method == 'take_presentation_delta':
            return self._publish(self._runtime.take_presentation_delta(*args, **kwargs))
        if method == 'reset':
            # No old-epoch updates/events can be silently abandoned at reset.
            with self._condition:
                if self._publications:
                    raise BufferError('drain old-epoch publications before reset')
            return self._runtime.reset(*args, **kwargs)
        return getattr(self._runtime, method)(*args, **kwargs)

    def _run(self):
        self._owner_ident = get_ident()
        current = None
        try:
            while True:
                with self._condition:
                    while not self._commands:
                        self._condition.wait()
                    method, payload, current = self._commands.popleft()
                if method == '_close':
                    current.set_result(None)
                    current = None
                    break
                try:
                    args, kwargs = json.loads(payload)
                    result = self._execute(method, args, kwargs)
                except Exception as exc:
                    # Expected request/reset errors retain their native prefix.
                    current.set_exception(exc)
                else:
                    current.set_result(result)
                current = None
        except BaseException as exc:
            with self._condition:
                self._failure = exc
            if current is not None and not current.done():
                current.set_exception(exc)
        finally:
            try:
                self._runtime.close()
            except BaseException as exc:
                with self._condition:
                    self._failure = self._failure or exc
            finally:
                with self._condition:
                    self._accepting = False
                    self._closed = True
                    while self._commands:
                        _, _, pending = self._commands.popleft()
                        pending.set_exception(RuntimeError('authority owner stopped'))
                    self._condition.notify_all()

    def close(self):
        if get_ident() == self._owner_ident:
            raise RuntimeError('owner cannot join itself')
        with self._condition:
            if self._accepting:
                self._accepting = False
                end = Future()
                end.set_running_or_notify_cancel()
                # A close fence is admitted once even when the inbox is full.
                self._commands.append(('_close', None, end))
                self._condition.notify_all()
            remaining = []
            while not self._closed:
                remaining.extend(self._publications)
                self._publications.clear()
                self._condition.notify_all()
                self._condition.wait()
            remaining.extend(self._publications)
            self._publications.clear()
        self._thread.join()
        return tuple(remaining)

    def metrics(self):
        with self._condition:
            return dict(owner_ident=self._owner_ident, closed=self._closed,
                        failure=None if self._failure is None else type(self._failure).__name__,
                        published=self._sequence, max_inbox=self._max_inbox,
                        max_deltas=self._max_deltas)
