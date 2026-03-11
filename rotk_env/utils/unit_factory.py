"""
Unit factory – creates units per rules v1.2.
"""

from framework import World
from ..components import (
    Unit,
    UnitCount,
    UnitStatus,
    MovementPoints,
    ActionPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    Combat,
    Vision,
    UnitSkills,
    HexPosition,
    Renderable,
)
from ..prefabs.config import GameConfig, UnitType, Faction, UnitState


class UnitFactory:
    """Unit factory."""

    @staticmethod
    def create_unit(
        world: World,
        unit_type: UnitType,
        faction: Faction,
        position: tuple,
        player_entity: int = None,
    ) -> int:
        """Create a unit entity."""

        # Get base unit stats
        base_stats = GameConfig.UNIT_BASE_STATS.get(unit_type)
        if not base_stats:
            raise ValueError(f"No config found for unit type {unit_type}")

        # Create entity
        entity = world.create_entity()

        # Add base components
        world.add_component(
            entity,
            Unit(
                unit_type=unit_type,
                faction=faction,
                name=f"{faction.value}_{unit_type.value}_{entity}",
            ),
        )

        # Add unit count component
        world.add_component(
            entity,
            UnitCount(
                current_count=base_stats.max_count, max_count=base_stats.max_count
            ),
        )

        # Add status component
        world.add_component(
            entity,
            UnitStatus(
                current_status=UnitState.NORMAL,
                status_duration=0,
                wait_turns=0,
                charge_stacks=0,
            ),
        )

        # Add movement component
        world.add_component(
            entity,
            MovementPoints(
                base_mp=base_stats.movement,
                current_mp=base_stats.movement,
                max_mp=base_stats.movement,
                has_moved=False,
            ),
        )

        # Add resource point components
        world.add_component(entity, ActionPoints())
        world.add_component(
            entity, AttackPoints(normal_attacks=1, max_normal_attacks=1)
        )
        world.add_component(entity, ConstructionPoints(current_cp=1, max_cp=1))
        world.add_component(entity, SkillPoints(current_sp=1, max_sp=1))

        # Add combat component
        world.add_component(
            entity,
            Combat(
                base_attack=base_stats.base_attack,
                base_defense=base_stats.base_defense,
                attack_range=base_stats.attack_range,
                has_attacked=False,
            ),
        )

        # Add vision component
        world.add_component(entity, Vision(range=base_stats.vision_range))

        # Add skills component
        skills = UnitFactory._get_unit_skills(unit_type)
        world.add_component(entity, UnitSkills(available_skills=skills))

        # Add position component
        world.add_component(entity, HexPosition(col=position[0], row=position[1]))

        # Add render component
        color = GameConfig.FACTION_COLORS.get(faction, (128, 128, 128))
        world.add_component(entity, Renderable(color=color, size=20, visible=True))

        # Assign unit to player
        if player_entity is not None:
            from ..components import Player

            player = world.get_component(player_entity, Player)
            if player:
                player.units.add(entity)

        return entity

    @staticmethod
    def _get_unit_skills(unit_type: UnitType) -> set:
        """Get unit skills."""
        skills_map = {
            UnitType.INFANTRY: {"盾墙·反射", "密集方阵"},
            UnitType.CAVALRY: {"冲锋·致命一击", "奔袭·踩踏"},
            UnitType.ARCHER: {"狙击·暴击", "火力压制·混乱"},
        }
        return skills_map.get(unit_type, set())

    @staticmethod
    def create_formation(
        world: World, unit_configs: list, player_entity: int = None
    ) -> list:
        """Create a formation."""
        entities = []

        for config in unit_configs:
            unit_type = config.get("type")
            faction = config.get("faction")
            position = config.get("position")

            if all([unit_type, faction, position]):
                entity = UnitFactory.create_unit(
                    world, unit_type, faction, position, player_entity
                )
                entities.append(entity)

        return entities

    @staticmethod
    def get_default_formation(faction: Faction, start_positions: list) -> list:
        """Return default formation config (1 infantry, 1 cavalry, 1 archer)."""
        if len(start_positions) < 3:
            raise ValueError("At least 3 start positions required")

        return [
            {
                "type": UnitType.INFANTRY,
                "faction": faction,
                "position": start_positions[0],
            },
            {
                "type": UnitType.CAVALRY,
                "faction": faction,
                "position": start_positions[1],
            },
            {
                "type": UnitType.ARCHER,
                "faction": faction,
                "position": start_positions[2],
            },
        ]
