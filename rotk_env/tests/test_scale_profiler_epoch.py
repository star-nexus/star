"""Regression tests for scale profiler measurement-epoch boundaries."""

from rotk_env.testing.profiler_epoch import (
    install_deferred_epoch_hook,
    measurement_epoch_pending,
    request_measurement_epoch,
)


class _FakeProfiler:
    def __init__(self):
        self._frame_open = False
        self.reset_count = 0
        self.start_count = 0
        self.metadata = {"scenario": "scale-test"}

    def reset(self):
        self.reset_count += 1
        self._frame_open = False

    def start_frame(self):
        self.start_count += 1
        self._frame_open = True

    def end_frame(self):
        self._frame_open = False

    def set_metadata(self, **values):
        self.metadata.update(values)


def test_epoch_reset_is_deferred_until_next_safe_start_frame():
    profiler = _FakeProfiler()
    assert install_deferred_epoch_hook(profiler) is True

    # Simulate a kickoff command issued inside an already-open frame.
    profiler._frame_open = True
    assert request_measurement_epoch(
        profiler,
        "dynamic_world_density_curve.density_1.00.staggered",
        scale_measurement_density=1.0,
    ) is True
    assert measurement_epoch_pending(profiler) is True
    assert profiler.reset_count == 0

    # GameEngine closes the kickoff frame normally. The following start_frame is
    # the safe boundary where the old epoch is discarded.
    profiler.end_frame()
    profiler.start_frame()

    assert profiler.reset_count == 1
    assert profiler.start_count == 1
    assert measurement_epoch_pending(profiler) is False
    assert profiler.metadata["scenario"] == "scale-test"
    assert profiler.metadata["measurement_epoch"] == (
        "dynamic_world_density_curve.density_1.00.staggered"
    )
    assert profiler.metadata["measurement_epoch_serial"] == 1
    assert profiler.metadata["scale_measurement_density"] == 1.0


def test_epoch_request_resets_only_once():
    profiler = _FakeProfiler()
    request_measurement_epoch(profiler, "execution")

    profiler.start_frame()
    assert profiler.reset_count == 1
    profiler.end_frame()
    profiler.start_frame()
    assert profiler.reset_count == 1


def test_unsupported_profiler_is_left_untouched():
    class _NoResetProfiler:
        def start_frame(self):
            pass

        def set_metadata(self, **values):
            pass

    profiler = _NoResetProfiler()
    assert install_deferred_epoch_hook(profiler) is False
    assert request_measurement_epoch(profiler, "execution") is False
