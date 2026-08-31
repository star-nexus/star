"""Window-only statistics sampler for large interactive scenarios.

The legacy StatisticsSystem intentionally keeps the benchmark/eval behaviour
unchanged.  This compatibility-named subclass is mounted only for
``display='window'`` and spreads the once-per-second O(units) bookkeeping over
small frame batches so 1000+ unit visualization does not pay three full scans
in a single frame.
"""

from __future__ import annotations

import time
from typing import Dict, List

from framework.ecs import profiling

from ..components import (
    FogOfWar,
    GameStats,
    HexPosition,
    MovementPoints,
    Unit,
    UnitCount,
    UnitObservation,
    VisibilityTracker,
)
from ..prefabs.config import Faction
from .statistics_system import StatisticsSystem as _BaseStatisticsSystem


class StatisticsSystem(_BaseStatisticsSystem):
    """Compatibility-named, frame-amortized StatisticsSystem for window mode."""

    DEFAULT_BATCH_SIZE = 128

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        super().__init__()
        self.batch_size = max(1, int(batch_size))
        self._cycle = None

    def initialize(self, world) -> None:
        super().initialize(world)
        self._cycle = None

    def update(self, delta_time: float) -> None:
        """Mirror game time every frame and amortize periodic statistics work."""
        current_time = time.time()
        self._update_game_time(delta_time)

        if (
            self._cycle is None
            and current_time - self.last_update_time >= self.observation_interval
        ):
            self._start_statistics_cycle(current_time)

        if self._cycle is None:
            profiling.profiler.set_frame_metric("statistics_phase", "idle")
            profiling.profiler.set_frame_metric("statistics_batch_units", 0)
            return

        with profiling.profiler.time_system("statistics_batch", category="work"):
            processed = self._process_statistics_batch()
        profiling.profiler.set_frame_metric("statistics_batch_units", processed)

    def _start_statistics_cycle(self, current_time: float) -> None:
        """Snapshot entity IDs once; components are read live as each batch runs."""
        with profiling.profiler.time_system(
            "statistics_cycle_snapshot", category="work"
        ):
            observation_entities = list(
                self.world.query().with_all(Unit, UnitCount, HexPosition).entities()
            )
            visibility_entities = list(
                self.world.query().with_all(Unit, HexPosition).entities()
            )

        self._cycle = {
            "phase": "observations",
            "index": 0,
            "observation_entities": observation_entities,
            "visibility_entities": visibility_entities,
            "faction_counts": {},
            "visibility_cleared": False,
        }
        # Cadence is measured from cycle start.  The cycle itself is designed to
        # finish well inside the one-second interval, so cycles never overlap.
        self.last_update_time = current_time
        profiling.profiler.set_frame_metric(
            "statistics_cycle_units", len(observation_entities)
        )

    def _process_statistics_batch(self) -> int:
        cycle = self._cycle
        if cycle is None:
            return 0

        phase = cycle["phase"]
        profiling.profiler.set_frame_metric("statistics_phase", phase)

        if phase == "observations":
            processed = self._process_observation_batch(cycle)
        elif phase == "visibility":
            processed = self._process_visibility_batch(cycle)
        elif phase == "factions":
            processed = self._process_faction_batch(cycle)
        else:
            self._cycle = None
            return 0

        return processed

    def _batch_slice(self, entities: List[int], index: int):
        end = min(index + self.batch_size, len(entities))
        return entities[index:end], end

    def _process_observation_batch(self, cycle: dict) -> int:
        entities = cycle["observation_entities"]
        batch, end = self._batch_slice(entities, cycle["index"])
        stats = self.world.get_singleton_component(GameStats)

        if stats:
            with profiling.profiler.time_system(
                "statistics_observations", category="work"
            ):
                for entity in batch:
                    unit = self.world.get_component(entity, Unit)
                    unit_count = self.world.get_component(entity, UnitCount)
                    position = self.world.get_component(entity, HexPosition)
                    movement = self.world.get_component(entity, MovementPoints)
                    if not unit or not unit_count or not position:
                        continue

                    observation = self.world.get_component(entity, UnitObservation)
                    if not observation:
                        observation = UnitObservation()
                        self.world.add_component(entity, observation)

                    observation.previous_position = observation.current_position
                    observation.current_position = (position.col, position.row)
                    observation.health_percentage = (
                        unit_count.current_count / unit_count.max_count
                    ) * 100

                    if movement:
                        observation.movement_remaining = movement.current_mp
                        observation.has_acted_this_turn = movement.has_moved
                        if observation.previous_position != observation.current_position:
                            observation.total_distance_moved += 1
                            observation.movement_path.append(
                                observation.current_position
                            )
                            if len(observation.movement_path) > 50:
                                observation.movement_path = observation.movement_path[-50:]

                    terrain_type = self._get_terrain_at_position(
                        position.col, position.row
                    )
                    observation.current_terrain_type = terrain_type
                    stats.unit_observation_history.append(
                        {
                            "entity": entity,
                            "faction": unit.faction.value,
                            "unit_type": unit.unit_type.value,
                            "position": observation.current_position,
                            "health_percentage": observation.health_percentage,
                            "movement_remaining": observation.movement_remaining,
                            "terrain_type": observation.current_terrain_type,
                            "timestamp": stats.total_game_time,
                        }
                    )

                # Preserve the legacy bounded-history policy, but trim once per
                # batch instead of testing/slicing after every unit append.
                if len(stats.unit_observation_history) > 10000:
                    stats.unit_observation_history = stats.unit_observation_history[-5000:]

        cycle["index"] = end
        if end >= len(entities):
            cycle["phase"] = "visibility"
            cycle["index"] = 0
        return len(batch)

    def _process_visibility_batch(self, cycle: dict) -> int:
        entities = cycle["visibility_entities"]
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if not visibility_tracker or not fog_of_war:
            cycle["phase"] = "factions"
            cycle["index"] = 0
            return 0

        if not cycle["visibility_cleared"]:
            for faction in visibility_tracker.faction_visible_units:
                visibility_tracker.faction_visible_units[faction].clear()
            cycle["visibility_cleared"] = True

        batch, end = self._batch_slice(entities, cycle["index"])
        with profiling.profiler.time_system(
            "statistics_visibility", category="work"
        ):
            for entity in batch:
                unit = self.world.get_component(entity, Unit)
                position = self.world.get_component(entity, HexPosition)
                if not unit or not position:
                    continue

                unit_pos = (position.col, position.row)
                visible_to = {
                    faction
                    for faction, vision_tiles in fog_of_war.faction_vision.items()
                    if faction != unit.faction and unit_pos in vision_tiles
                }
                visible_to.add(unit.faction)
                self._update_unit_visibility(
                    entity, visible_to, visibility_tracker
                )

        cycle["index"] = end
        if end >= len(entities):
            cycle["phase"] = "factions"
            cycle["index"] = 0
        return len(batch)

    def _process_faction_batch(self, cycle: dict) -> int:
        entities = cycle["observation_entities"]
        batch, end = self._batch_slice(entities, cycle["index"])
        stats = self.world.get_singleton_component(GameStats)
        counts: Dict[Faction, int] = cycle["faction_counts"]

        if stats:
            with profiling.profiler.time_system(
                "statistics_factions", category="work"
            ):
                for entity in batch:
                    unit = self.world.get_component(entity, Unit)
                    unit_count = self.world.get_component(entity, UnitCount)
                    if not unit or not unit_count or unit_count.current_count <= 0:
                        continue
                    self._initialize_faction_stats(unit.faction, stats)
                    counts[unit.faction] = counts.get(unit.faction, 0) + 1

        cycle["index"] = end
        if end >= len(entities):
            if stats:
                for faction, territory_count in counts.items():
                    if faction in stats.faction_stats:
                        stats.faction_stats[faction][
                            "territory_controlled"
                        ] = territory_count
            self._cycle = None
            profiling.profiler.set_frame_metric("statistics_phase", "complete")

        return len(batch)
