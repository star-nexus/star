import pytest

from framework.ecs import profiling
from framework.engine.game_engine import GameEngine


def _bare_engine(*, uncapped: bool) -> GameEngine:
    engine = object.__new__(GameEngine)
    engine.fps = 60
    engine.uncapped = uncapped
    return engine


def test_capped_clock_keeps_fixed_simulation_delta():
    engine = _bare_engine(uncapped=False)
    fixed_dt = 1.0 / 60.0

    assert engine._frame_delta_seconds(10.0, None, fixed_dt) == fixed_dt
    assert engine._frame_delta_seconds(10.5, 10.0, fixed_dt) == fixed_dt


def test_uncapped_clock_uses_wall_time_after_first_frame():
    engine = _bare_engine(uncapped=True)
    fixed_dt = 1.0 / 60.0

    assert engine._frame_delta_seconds(10.0, None, fixed_dt) == fixed_dt
    assert engine._frame_delta_seconds(10.006, 10.0, fixed_dt) == pytest.approx(0.006)
    assert engine._frame_delta_seconds(9.0, 10.0, fixed_dt) == 0.0


def test_frame_limiter_is_skipped_only_in_uncapped_mode():
    class FakeClock:
        def __init__(self):
            self.calls = []

        def tick(self, fps):
            self.calls.append(fps)

    capped = _bare_engine(uncapped=False)
    capped.clock = FakeClock()
    capped._wait_for_frame_cap(profiling.profiler)
    assert capped.clock.calls == [60]

    uncapped = _bare_engine(uncapped=True)
    uncapped.clock = FakeClock()
    uncapped._wait_for_frame_cap(profiling.profiler)
    assert uncapped.clock.calls == []
