"""Window combat adapter for shared unit spatial state."""

from __future__ import annotations

from ..utils.unit_spatial_index import remove_unit_from_spatial_index
from .combat_system import CombatSystem as _BaseCombatSystem


class CombatSystem(_BaseCombatSystem):
    """Remove dead units from the spatial index before ECS destruction."""

    def _handle_unit_death(self, entity: int, killer_entity: int = None):
        remove_unit_from_spatial_index(self.world, entity)
        return super()._handle_unit_death(entity, killer_entity)
