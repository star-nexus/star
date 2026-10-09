"""Single native authority owner; display and SDL remain on the creating thread.

The public runtime calls retain their synchronous result/error contract. Calls
from other threads are admitted independently of UI frames. The optional fixed
clock orders ticks with requests under one condition lock. No delta is dropped.
"""
from collections import deque
from concurrent.futures import Future
from copy import deepcopy
import math
from threading import Condition, Thread, get_ident
import time


class AuthorityRuntime:
    backend = 'rust'
    _METHODS = frozenset({
        'reset', 'step', 'host_status', 'record_message', 'turn_start_context',
        'prepare_game_end', 'execute_control', 'execute_action', 'execute_actions',
        'execute_actions_diagnostic', 'get_faction_state', 'get_faction_state_json',
        'finish_human_turn', 'start_capture', 'set_clock', 'export_state',
        'diagnostics', 'take_presentation_delta',
    })

    def __init__(self, runtime, *, on_publication, capture_frame=None,
                 inbox_capacity=32, delta_capacity=8):
        for value in (inbox_capacity, delta_capacity):
            if type(value) is not int or value < 1:
                raise ValueError('authority queue capacity must be a positive integer')
        self._runtime = runtime
        self._ui_ident = get_ident()
        self._owner_ident = None
        self._condition = Condition()
        self._commands = deque()
        self._publications = deque()
        self._captures = deque()
        self._inbox_capacity = inbox_capacity
        self._delta_capacity = delta_capacity
        self._on_publication = on_publication
        self._capture_frame = capture_frame
        self._accepting = True
        self._closed = False
        self._failure = None
        self._period = None
        self._next_tick = None
        self._sequence = 0
        self._max_inbox = 0
        self._max_deltas = 0
        self._events = []
        self._pumping = False
        # Only this runtime's successful VLM responses use the UI handoff.
        self._old_capture = runtime._frame_capture
        runtime._frame_capture = self._capture
        self._thread = Thread(target=self._run, name='star-authority')
        self._thread.start()

    def __getattr__(self, name):
        if name not in self._METHODS:
            raise AttributeError(name)
        def invoke(*args, **kwargs):
            return self._call(name, args, kwargs)
        return invoke

    def _admit(self, method, args, kwargs):
        # Preserve tuple, ActionRequest and special float/error behavior while
        # removing all mutable input aliases before accepting any operation.
        args, kwargs = deepcopy((args, kwargs))
        future = Future()
        future.set_running_or_notify_cancel()
        while True:
            if get_ident() == self._ui_ident:
                self.pump()
            with self._condition:
                if not self._accepting:
                    raise RuntimeError('native authority is closed') from self._failure
                if len(self._commands) < self._inbox_capacity:
                    self._commands.append((method, args, kwargs, future, time.monotonic()))
                    self._max_inbox = max(self._max_inbox, len(self._commands))
                    self._condition.notify_all()
                    return future
                # Backpressure before admission. No new protocol error or loss.
                self._condition.wait(.01 if get_ident() == self._ui_ident else None)

    def _call(self, method, args, kwargs):
        if get_ident() == self._owner_ident:
            raise RuntimeError('recursive authority admission is not supported')
        if get_ident() == self._ui_ident and self._pumping:
            raise RuntimeError('display callbacks cannot synchronously reenter authority')
        future = self._admit(method, args, kwargs)
        if get_ident() != self._ui_ident:
            return future.result()
        while not future.done():
            self.pump()
            with self._condition:
                if not future.done():
                    self._condition.wait(.01)
        self.pump()
        return future.result()

    def _publish(self):
        delta = self._runtime.take_presentation_delta()
        with self._condition:
            while len(self._publications) >= self._delta_capacity:
                self._condition.wait()
            self._publications.append((self._sequence, delta))
            self._sequence += 1
            self._max_deltas = max(self._max_deltas, len(self._publications))
            self._condition.notify_all()
        return delta

    def _capture(self):
        # Native execution is suspended here: no later request or tick crosses
        # the projection/capture fence, and SDL is never accessed by the owner.
        self._publish()
        result = Future()
        with self._condition:
            self._captures.append(result)
            self._condition.notify_all()
        return result.result()

    def pump(self):
        if get_ident() != self._ui_ident:
            raise RuntimeError('only the display thread may consume publications')
        if self._pumping:
            return
        self._pumping = True
        try:
            with self._condition:
                packets = tuple(self._publications)
                self._publications.clear()
                captures = tuple(self._captures)
                self._captures.clear()
                self._condition.notify_all()
            for _, delta in packets:
                events = self._on_publication(delta)
                if events:
                    self._events.extend(events)
            for result in captures:
                try:
                    capture = self._capture_frame or self._old_capture
                    if capture is None:
                        from framework.engine.frame_capture import capture_rendered_frame
                        capture = capture_rendered_frame
                    result.set_result(capture())
                except BaseException as exc:
                    result.set_exception(exc)
        except BaseException as exc:
            for result in captures:
                if not result.done():
                    result.set_exception(exc)
            raise
        finally:
            self._pumping = False

    def consume_presentation(self):
        self._call('_publish', (), {})
        result, self._events = self._events, []
        return result

    def start_clock(self, dt):
        if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            raise ValueError('authority clock step must be positive and finite')
        self._call('_start_clock', (float(dt),), {})

    def stop_clock(self):
        self._call('_stop_clock', (), {})

    @property
    def clock_running(self):
        with self._condition:
            return self._period is not None

    def scheduling_metrics(self):
        with self._condition:
            return dict(closed=self._closed, owner_ident=self._owner_ident,
                        published=self._sequence, max_inbox=self._max_inbox,
                        max_deltas=self._max_deltas, clock_running=self._period is not None,
                        failure=None if self._failure is None else type(self._failure).__name__)

    def _execute(self, method, args, kwargs):
        if method == '_start_clock':
            with self._condition:
                self._period = args[0]
                self._next_tick = time.monotonic() + self._period
            return None
        if method == '_stop_clock':
            with self._condition:
                self._period = self._next_tick = None
            return None
        if method == '_publish':
            self._publish()
            return None
        if method == 'step':
            if self._period is not None:
                raise RuntimeError('manual step is disabled while the authority clock runs')
            return self._runtime.step(*args, **kwargs)
        if method == 'reset':
            # UI consumption is an explicit old-epoch fence. Never abandon old
            # events when replacing the native epoch. Failed reset keeps state.
            with self._condition:
                if self._period is not None:
                    raise RuntimeError('stop the authority clock before reset')
                if self._publications:
                    raise RuntimeError('consume old-epoch publications before reset')
            return self._runtime.reset(*args, **kwargs)
        return getattr(self._runtime, method)(*args, **kwargs)

    def _run(self):
        self._owner_ident = get_ident()
        current = None
        try:
            while True:
                with self._condition:
                    while True:
                        now = time.monotonic()
                        # Requests accepted before a deadline precede that tick;
                        # later arrivals cannot indefinitely starve the clock.
                        due = self._accepting and self._next_tick is not None and now >= self._next_tick
                        first = self._commands[0] if self._commands else None
                        if first is not None and (not due or first[4] < self._next_tick
                                                  or first[0] == '_close'):
                            method, args, kwargs, current, _ = self._commands.popleft()
                            self._condition.notify_all()
                            break
                        if due:
                            method, args, kwargs, current = '_tick', (), {}, None
                            break
                        self._condition.wait(None if self._next_tick is None
                                             else max(0, self._next_tick - now))
                if method == '_close':
                    current.set_result(None)
                    current = None
                    break
                if method == '_tick':
                    dt = self._period
                    self._runtime.step(dt, wall_time=time.time())
                    self._publish()
                    with self._condition:
                        # Retain a fixed dt under overload, matching capped
                        # gameplay; never manufacture a burst of catch-up steps.
                        self._next_tick = max(self._next_tick + dt, time.monotonic())
                    continue
                try:
                    answer = self._execute(method, args, kwargs)
                except Exception as exc:
                    current.set_exception(exc)
                else:
                    current.set_result(answer)
                current = None
                with self._condition:
                    self._condition.notify_all()
        except BaseException as exc:
            with self._condition:
                self._failure = exc
            if current is not None and not current.done():
                current.set_exception(exc)
        finally:
            try:
                self._runtime._frame_capture = self._old_capture
                self._runtime.close()
            except BaseException as exc:
                self._failure = self._failure or exc
            with self._condition:
                self._accepting = False
                self._closed = True
                self._period = self._next_tick = None
                while self._commands:
                    _, _, _, pending, _ = self._commands.popleft()
                    pending.set_exception(RuntimeError('native authority stopped'))
                self._condition.notify_all()

    def retire(self):
        """Stop admission inside a failed UI callback; its owner is joined later."""
        with self._condition:
            if self._accepting:
                self._accepting = False
                end = Future()
                end.set_running_or_notify_cancel()
                self._commands.append(('_close', (), {}, end, time.monotonic()))
                self._condition.notify_all()

    def close(self):
        if get_ident() != self._ui_ident or self._pumping:
            raise RuntimeError('authority close requires the display thread outside callbacks')
        self.retire()
        error = None
        while True:
            try:
                if error is None:
                    self.pump()
                else:
                    # A broken derived World cannot consume later patches. Still
                    # release backpressure/capture fences and join authority.
                    with self._condition:
                        self._publications.clear()
                        while self._captures:
                            self._captures.popleft().set_exception(error)
                        self._condition.notify_all()
            except BaseException as exc:
                error = error or exc
            with self._condition:
                if self._closed:
                    break
                self._condition.wait(.01)
        if error is None:
            try:
                self.pump()
            except BaseException as exc:
                error = exc
        self._thread.join()
        if error is not None:
            raise error
