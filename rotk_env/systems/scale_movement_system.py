"""Window movement adapter backed by the maintained unit spatial index."""

from __future__ import annotations

from typing import Optional, Set, Tuple

from ..components import HexPosition, Unit
from ..utils.map_query import impassable_terrain
from ..utils.unit_spatial_index import (
    get_unit_spatial_index,
    update_unit_spatial_index,
)
from .movement_system import MovementSystem as _BaseMovementSystem
from .vision_system import mark_vision_dirty

Hex = Tuple[int, int]


class MovementSystem(_BaseMovementSystem):
    """Reuse indexed occupancy and publish committed-position invalidations."""

    def commit_hex_position(
        self, entity: int, col: int, row: int, *, arrived: bool = False
    ) -> None:
        position = self.world.get_component(entity, HexPosition)
        old = (position.col, position.row) if position is not None else None
        super().commit_hex_position(entity, col, row, arrived=arrived)
        if old is not None and old != (col, row):
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
