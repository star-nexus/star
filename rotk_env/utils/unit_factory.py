"""
单位工厂 - 按规则手册v1.2创建单位
"""

from framework import World
from ..components import (
    Unit,
    UnitCount,
    UnitStatus,
    Movement,
    Combat,
    Vision,
    ActionPoints,
    UnitSkills,
    HexPosition,
    Renderable,
)
from ..prefabs.config import GameConfig, UnitType, Faction, UnitState


class UnitFactory:
    """单位工厂类"""

    @staticmethod
    def create_unit(
        world: World,
        unit_type: UnitType,
        faction: Faction,
        position: tuple,
        player_entity: int = None,
    ) -> int:
        """创建单位实体"""

        # 获取单位基础配置
        base_stats = GameConfig.UNIT_BASE_STATS.get(unit_type)
        if not base_stats:
            raise ValueError(f"未找到单位类型 {unit_type} 的配置")

        # 创建实体
        entity = world.create_entity()

        # 添加基础组件
        world.add_component(
            entity,
            Unit(
                unit_type=unit_type,
                faction=faction,
                name=f"{faction.value}_{unit_type.value}_{entity}",
            ),
        )

        # 添加人数组件
        world.add_component(
            entity,
            UnitCount(
                current_count=base_stats.max_count, max_count=base_stats.max_count
            ),
        )

        # 添加状态组件
        world.add_component(
            entity,
            UnitStatus(
                current_status=UnitState.NORMAL,
                status_duration=0,
                wait_turns=0,
                charge_stacks=0,
            ),
        )

        # 添加移动组件
        world.add_component(
            entity,
            Movement(
                base_movement=base_stats.movement,
                current_movement=base_stats.movement,
                has_moved=False,
            ),
        )

        # 添加战斗组件
        world.add_component(
            entity,
            Combat(
                base_attack=base_stats.base_attack,
                base_defense=base_stats.base_defense,
                attack_range=base_stats.attack_range,
                has_attacked=False,
            ),
        )

        # 添加视野组件
        world.add_component(entity, Vision(range=base_stats.vision_range))

        # 添加行动力组件
        world.add_component(entity, ActionPoints(current_ap=2, max_ap=2))

        # 添加技能组件
        skills = UnitFactory._get_unit_skills(unit_type)
        world.add_component(entity, UnitSkills(available_skills=skills))

        # 添加位置组件
        world.add_component(entity, HexPosition(col=position[0], row=position[1]))

        # 添加渲染组件
        color = GameConfig.FACTION_COLORS.get(faction, (128, 128, 128))
        world.add_component(entity, Renderable(color=color, size=20, visible=True))

        # 将单位添加到玩家
        if player_entity is not None:
            from ..components import Player

            player = world.get_component(player_entity, Player)
            if player:
                player.units.add(entity)

        return entity

    @staticmethod
    def _get_unit_skills(unit_type: UnitType) -> set:
        """获取单位技能"""
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
        """创建编队"""
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
        """获取默认编队配置"""
        if len(start_positions) < 3:
            raise ValueError("至少需要3个起始位置")

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
