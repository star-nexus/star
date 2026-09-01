"""Low-rate live metrics for Scale Test Harness workloads.

The observer is mounted only when the scale harness is enabled. It samples every
few frames instead of rescanning MovementAnimation every frame, and it records
its own cost so benchmark readers can separate measurement overhead from the
workload being measured.
"""

from __future__ import annotations

from framework import System
from framework.ecs import profiling

from ..components import MovementAnimation, Unit, UnitCount
from ..utils.unit_spatial_index import get_unit_spatial_index


class ScaleHarnessMetricsSystem(System):
    """Sample actual moving/living density after AnimationSystem has updated."""

    def __init__(self, sample_every_frames: int = 10):
        # AnimationSystem is priority 15. Sample afterwards so a unit completing
        # on this frame is not still counted as active.
        super().__init__(priority=16)
        self.sample_every_frames = max(1, int(sample_every_frames))
        self._frames = 0

    def initialize(self, world) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        self._frames += 1
        if self._frames % self.sample_every_frames:
            return

        with profiling.profiler.time_system(
            "scale_active_density_sample", category="scale_execution"
        ):
            active = 0
            for entity in self.world.query().with_component(MovementAnimation).entities():
                anim = self.world.get_component(entity, MovementAnimation)
                if anim is not None and anim.is_moving:
                    active += 1

            index = get_unit_spatial_index(self.world)
            if index is not None:
                living = sum(index.living_counts.values())
            else:
                living = 0
                for entity in self.world.query().with_all(Unit, UnitCount).entities():
                    count = self.world.get_component(entity, UnitCount)
                    if count is not None and count.current_count > 0:
                        living += 1

        density = active / living if living else 0.0
        profiling.profiler.set_metadata(
            scale_active_moving_units=active,
            scale_actual_density=round(density, 4),
        )
        profiling.profiler.set_frame_metric("scale_active_moving_units", active)
        profiling.profiler.set_frame_metric(
            "scale_actual_density", round(density, 4)
        )
