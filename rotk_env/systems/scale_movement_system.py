"""Window movement adapter backed by the maintained UnitSpatialIndex.

The movement domain itself lives in ``movement_system``. This subclass only
supplies scale-aware planning inputs and keeps the derived spatial index in sync
when authoritative HexPosition commits occur.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Set, Tuple

from framework.ecs import profiling

from ..components import HexPosition, Unit
from ..prefabs.config import Faction
from ..utils.map_query import board_hexes, impassable_terrain, movement_costs
from ..utils.unit_spatial_index import (
    get_unit_spatial_index,
    update_unit_spatial_index,
)
from .movement_planning import MovementPlanningSnapshot
from .movement_system import MovementSystem as _BaseMovementSystem
from .vision_system import mark_vision_dirty

Hex = Tuple[int, int]


class MovementSystem(_BaseMovementSystem):
    """Scale-aware movement planning using one maintained occupancy index."""

    def initialize(self, world) -> None:
        super().initialize(world)
        socket_value = os.environ.get("STAR_SCALE_HARNESS_SOCKET")
        if not socket_value:
            return
        socket_path = (
            "/tmp/star-scale.sock"
            if socket_value.strip().lower() in {"1", "true", "yes", "on"}
            else socket_value
        )
        # Wiring only: the movement domain never reads stress flags. The optional
        # harness receives this domain service and selects planning policies via
        # its explicit control-plane commands. Measurement concerns are installed
        # as separate test-only adapters around that harness.
        from ..testing.fog_camera_attribution import (
            install_fog_camera_attribution,
        )
        from ..testing.fog_content_bounds_experiment import (
            install_fog_content_bounds_experiment,
        )
        from ..testing.fog_directed_phase_experiment import (
            install_fog_directed_phase_experiment,
        )
        from ..testing.fog_presentation_bounds_experiment import (
            install_fog_presentation_bounds_experiment,
        )
        from ..testing.scale_camera_stress import install_scale_camera_stress
        from ..testing.scale_experiment_measurement import (
            install_scale_experiment_measurement,
        )
        from ..testing.scale_harness import ScaleHarnessSystem
        from ..testing.scale_harness_metrics import ScaleHarnessMetricsSystem
        from ..testing.scale_memory_soak import install_scale_memory_soak
        from ..testing.scale_vision_cache_ablation import (
            install_scale_vision_cache_ablation,
        )

        harness = next(
            (
                system
                for system in world.systems
                if isinstance(system, ScaleHarnessSystem)
            ),
            None,
        )
        if harness is None:
            harness = ScaleHarnessSystem(self, socket_path)
            world.add_system(harness)

        install_scale_experiment_measurement(harness, world, profiling.profiler)
        install_scale_camera_stress(harness, world, profiling.profiler)
        install_fog_camera_attribution(harness, world, profiling.profiler)
        install_fog_content_bounds_experiment(harness, world, profiling.profiler)
        install_fog_directed_phase_experiment(harness, world, profiling.profiler)
        install_fog_presentation_bounds_experiment(
            harness, world, profiling.profiler
        )
        install_scale_memory_soak(harness, world)
        install_scale_vision_cache_ablation(harness, world)

        if not any(
            isinstance(system, ScaleHarnessMetricsSystem) for system in world.systems
        ):
            world.add_system(ScaleHarnessMetricsSystem(sample_every_frames=10))

    def _planning_context(
        self,
        entity: int,
        faction: Optional[Faction],
        snapshot: Optional[MovementPlanningSnapshot],
    ):
        if snapshot is not None:
            return super()._planning_context(entity, faction, snapshot)

        index = get_unit_spatial_index(self.world)
        if index is None:
            return super()._planning_context(entity, faction, None)

        with profiling.profiler.time_system(
            "move_occupancy_snapshot", category="input"
        ):
            occupied, enemy_held = index.occupancy_for_mover(entity, faction)
        blockers = set(impassable_terrain(self.world)) | enemy_held
        costs = movement_costs(self.world)
        walkable = board_hexes(self.world)

        profiling.profiler.set_frame_metric("move_occupied_cells", len(occupied))
        profiling.profiler.set_frame_metric("move_enemy_blockers", len(enemy_held))
        profiling.profiler.set_frame_metric("move_spatial_revision", index.revision)
        return (
            occupied,
            blockers,
            costs,
            set(walkable) if walkable is not None else None,
            index.revision,
        )

    def build_planning_snapshot(self) -> MovementPlanningSnapshot:
        """Build one shared snapshot for thousands of planners without ECS scans."""
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super().build_planning_snapshot()

        occupied = frozenset(index.by_cell.keys())
        impassable = frozenset(impassable_terrain(self.world))
        blockers_by_faction = {}
        for faction in (Faction.WEI, Faction.SHU, Faction.WU):
            enemy = {
                cell
                for cell, faction_counts in index.by_cell.items()
                if any(
                    other_faction != faction and count > 0
                    for other_faction, count in faction_counts.items()
                )
            }
            blockers_by_faction[faction] = frozenset(set(impassable) | enemy)

        walkable = board_hexes(self.world)
        return MovementPlanningSnapshot(
            walkable=frozenset(walkable) if walkable is not None else None,
            terrain_costs=movement_costs(self.world),
            occupied=occupied,
            blockers_by_faction=blockers_by_faction,
            revision=index.revision,
        )

    def commit_hex_position(
        self, entity: int, col: int, row: int, *, arrived: bool = False
    ) -> None:
        position = self.world.get_component(entity, HexPosition)
        old = (position.col, position.row) if position is not None else None
        super().commit_hex_position(entity, col, row, arrived=arrived)
        changed = old is not None and old != (col, row)
        if changed:
            # Event-driven visibility invalidation: dynamic-world scale should
            # pay for units that actually changed hex, not all resident units.
            mark_vision_dirty(self.world, entity)
        update_unit_spatial_index(self.world, entity)

    def _get_obstacles(
        self, exclude_entity: Optional[int] = None
    ) -> Set[Hex]:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super()._get_obstacles(exclude_entity)
        unit = (
            self.world.get_component(exclude_entity, Unit)
            if exclude_entity is not None
            else None
        )
        _occupied, enemy_held = index.occupancy_for_mover(
            exclude_entity, unit.faction if unit else None
        )
        return set(impassable_terrain(self.world)) | enemy_held

    def _occupied(self, exclude_entity: Optional[int] = None) -> Set[Hex]:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super()._occupied(exclude_entity)
        unit = (
            self.world.get_component(exclude_entity, Unit)
            if exclude_entity is not None
            else None
        )
        occupied, _enemy = index.occupancy_for_mover(
            exclude_entity, unit.faction if unit else None
        )
        return occupied
