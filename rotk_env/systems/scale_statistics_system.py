"""Window-only statistics sampler for large interactive scenarios.

The legacy StatisticsSystem intentionally keeps the benchmark/eval behaviour
unchanged. This compatibility-named subclass is mounted only for
``display='window'`` and spreads the once-per-second O(units) bookkeeping over
small frame batches so 1000+ unit visualization does not pay three full scans
in a single frame.

The observation history keeps ordinary ``list`` semantics for compatibility,
but trims only the small overflow beyond the cap. The previous implementation
periodically copied the newest 5000 records and released ~5000 dicts in one
frame, which can create a 20 ms allocator/refcount tail at 2000 units.

Visibility history is change-oriented rather than snapshot-oriented. The live
``faction_visible_units`` and ``UnitObservation.is_visible_to`` state is still
refreshed by the sampler, but an immutable history record is allocated only
when a unit's visibility relation actually changes. Stable visibility therefore
does not create thousands of duplicate dict/list objects every second.
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
from ..utils.unit_spatial_index import get_unit_spatial_index
from .statistics_system import StatisticsSystem as _BaseStatisticsSystem


class StatisticsSystem(_BaseStatisticsSystem):
    """Compatibility-named, frame-amortized StatisticsSystem for window mode."""

    DEFAULT_BATCH_SIZE = 128
    OBSERVATION_HISTORY_LIMIT = 10000
    VISIBILITY_HISTORY_LIMIT = 100

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
            "fog_disabled_visible_to": None,
        }
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

    def _trim_observation_history(self, stats: GameStats) -> int:
        """Drop only this batch's overflow, never half the history at once."""
        history = stats.unit_observation_history
        overflow = len(history) - self.OBSERVATION_HISTORY_LIMIT
        if overflow <= 0:
            return 0
        del history[:overflow]
        return overflow

    def _process_observation_batch(self, cycle: dict) -> int:
        entities = cycle["observation_entities"]
        batch, end = self._batch_slice(entities, cycle["index"])
        stats = self.world.get_singleton_component(GameStats)

        trimmed = 0
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

                # Keep list compatibility while spreading eviction over the same
                # 128-record batches that spread insertion work.
                trimmed = self._trim_observation_history(stats)

        profiling.profiler.set_frame_metric("statistics_history_trimmed", trimmed)
        if stats:
            profiling.profiler.set_frame_metric(
                "statistics_history_size", len(stats.unit_observation_history)
            )

        cycle["index"] = end
        if end >= len(entities):
            cycle["phase"] = "visibility"
            cycle["index"] = 0
        return len(batch)

    def _fog_disabled_visible_factions(self, cycle: dict, fog_of_war: FogOfWar):
        """Return one shared immutable visibility set for fog-disabled batches."""
        cached = cycle.get("fog_disabled_visible_to")
        if cached is not None:
            return cached

        factions = set(fog_of_war.faction_vision.keys())
        spatial_index = get_unit_spatial_index(self.world)
        if spatial_index is not None:
            factions.update(spatial_index.living_factions())
        cached = frozenset(factions)
        cycle["fog_disabled_visible_to"] = cached
        return cached

    def _record_visibility_change(
        self,
        entity: int,
        current_visible,
        visibility_tracker: VisibilityTracker,
        observation: UnitObservation | None,
        current_time: float,
    ) -> tuple[int, int]:
        """Update live visibility and append history only when the relation changes.

        Returns ``(records_appended, records_trimmed)``.  The first record is a
        baseline snapshot; later records are true change events with
        ``newly_spotted`` / ``lost_sight`` derived from the previous state.
        """
        previous_visible = observation.is_visible_to if observation else set()
        changed = previous_visible != current_visible

        if observation is not None:
            # Keep the live state fresh without replacing its set object every
            # statistics cycle.  ``last_seen_time`` retains the legacy sampler's
            # semantics: the own faction always sees the unit.
            observation.last_seen_time = current_time

        if not changed:
            return 0, 0

        history = visibility_tracker.visibility_history.setdefault(entity, [])
        baseline = not history and not previous_visible
        newly_spotted = (
            False
            if baseline
            else any(faction not in previous_visible for faction in current_visible)
        )
        lost_sight = (
            False
            if baseline
            else any(faction not in current_visible for faction in previous_visible)
        )

        history.append(
            {
                "timestamp": current_time,
                "visible_to": sorted(
                    current_visible,
                    key=lambda faction: getattr(faction, "value", str(faction)),
                ),
                "newly_spotted": newly_spotted,
                "lost_sight": lost_sight,
            }
        )

        overflow = len(history) - self.VISIBILITY_HISTORY_LIMIT
        trimmed = 0
        if overflow > 0:
            # Change events are rare; bound the compatibility list in place and
            # never allocate a replacement 100-item list.
            del history[:overflow]
            trimmed = overflow

        if observation is not None:
            observation.is_visible_to.clear()
            observation.is_visible_to.update(current_visible)

        return 1, trimmed

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
        current_time = time.time()
        fog_disabled_visible_to = (
            self._fog_disabled_visible_factions(cycle, fog_of_war)
            if not fog_of_war.enabled
            else None
        )
        changes = 0
        records = 0
        trimmed = 0

        with profiling.profiler.time_system(
            "statistics_visibility", category="work"
        ):
            for entity in batch:
                unit = self.world.get_component(entity, Unit)
                position = self.world.get_component(entity, HexPosition)
                if not unit or not position:
                    continue

                if fog_disabled_visible_to is not None:
                    # Fog-off is one stable all-visible relation. Reuse one
                    # frozenset for the whole batch instead of allocating one
                    # temporary set per unit.
                    if unit.faction in fog_disabled_visible_to:
                        visible_to = fog_disabled_visible_to
                    else:
                        visible_to = frozenset((*fog_disabled_visible_to, unit.faction))
                else:
                    unit_pos = (position.col, position.row)
                    visible_to = {
                        faction
                        for faction, vision_tiles in fog_of_war.faction_vision.items()
                        if faction != unit.faction and unit_pos in vision_tiles
                    }
                    visible_to.add(unit.faction)

                # Maintain the live faction -> visible-unit view every cycle.
                for faction in visible_to:
                    visibility_tracker.faction_visible_units.setdefault(
                        faction, set()
                    ).add(entity)

                observation = self.world.get_component(entity, UnitObservation)
                appended, dropped = self._record_visibility_change(
                    entity,
                    visible_to,
                    visibility_tracker,
                    observation,
                    current_time,
                )
                records += appended
                trimmed += dropped
                changes += int(bool(appended))

        profiling.profiler.set_frame_metric("statistics_visibility_changes", changes)
        profiling.profiler.set_frame_metric(
            "statistics_visibility_history_records", records
        )
        profiling.profiler.set_frame_metric(
            "statistics_visibility_history_trimmed", trimmed
        )
        profiling.profiler.set_frame_metric(
            "statistics_visibility_fog_disabled", int(not fog_of_war.enabled)
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
