"""
行动系统 - 处理单位的各种行动（按规则手册v1.2）
"""

from framework import System, World
from ..components import (
    HexPosition,
    MovementPoints,
    UnitCount,
    UnitStatus,
    Unit,
    ActionPoints,
    MapData,
    Terrain,
    Player,
)
from ..prefabs.config import GameConfig, ActionType, UnitState, TerrainType
from ..utils.hex_utils import HexMath


class ActionSystem(System):
    """行动系统 - 处理单位的各种行动"""

    def __init__(self):
        super().__init__(priority=250)

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        pass

    def perform_move(self, entity: int, target_pos: tuple) -> bool:
        """执行移动动作"""
        action_points = self.world.get_component(entity, ActionPoints)
        movement = self.world.get_component(entity, MovementPoints)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)

        if not all([action_points, movement, position, unit_count]):
            return False

        # 计算移动消耗
        movement_cost = self._calculate_movement_cost(
            (position.col, position.row), target_pos
        )

        # 检查行动力和移动力
        effective_movement = movement.get_effective_movement(unit_count)
        if (
            not action_points.can_perform_action(ActionType.MOVE)
            or movement_cost > effective_movement
        ):
            return False

        # 消耗移动力和行动力
        movement.current_movement -= movement_cost
        movement.has_moved = True

        # 移动消耗的行动力等于地形消耗
        terrain_cost = self._get_terrain_movement_cost(target_pos)
        action_points.current_ap -= terrain_cost

        # 更新位置
        position.col, position.row = target_pos

        return True

    def perform_garrison(self, entity: int) -> bool:
        """执行驻扎动作"""
        action_points = self.world.get_component(entity, ActionPoints)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)
        unit_status = self.world.get_component(entity, UnitStatus)

        if not all([action_points, position, unit_count, unit_status]):
            return False

        # 检查是否可以驻扎（仅城池/丘陵格）
        terrain_type = self._get_terrain_at_position((position.col, position.row))
        if terrain_type not in [TerrainType.URBAN, TerrainType.HILL]:
            return False

        # 检查行动力
        if not action_points.can_perform_action(ActionType.GARRISON):
            return False

        # 消耗行动力
        action_points.consume_ap(ActionType.GARRISON)

        # 恢复10%已损人数（向上取整）
        lost_count = unit_count.max_count - unit_count.current_count
        recovery = max(1, int(lost_count * 0.1))
        unit_count.current_count = min(
            unit_count.max_count, unit_count.current_count + recovery
        )

        # 状态变为正常，防御+2
        unit_status.current_status = UnitState.NORMAL
        unit_status.status_duration = 0

        # 这里需要添加防御+2的效果，可以通过临时组件实现
        self._add_garrison_bonus(entity)

        # 记录驻扎行动到统计系统
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_garrison_action(entity)

        return True

    def perform_wait(self, entity: int) -> bool:
        """执行待命动作"""
        action_points = self.world.get_component(entity, ActionPoints)
        unit_status = self.world.get_component(entity, UnitStatus)

        if not all([action_points, unit_status]):
            return False

        # 待命不消耗行动力
        unit_status.wait_turns += 1

        # 若本回合未受击，则下回合开始士气高昂
        # 这个逻辑需要在回合系统中处理

        # 连续待命2回合可驱散混乱
        if (
            unit_status.wait_turns >= 2
            and unit_status.current_status == UnitState.CONFUSION
        ):
            unit_status.current_status = UnitState.NORMAL
            unit_status.status_duration = 0

        # 记录待命行动到统计系统
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_wait_action(entity)

        return True

    def _calculate_movement_cost(self, from_pos: tuple, to_pos: tuple) -> int:
        """计算移动消耗"""
        # 简化：使用目标地形的移动消耗
        return self._get_terrain_movement_cost(to_pos)

    def _get_terrain_movement_cost(self, position: tuple) -> int:
        """获取地形移动消耗"""
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """获取位置的地形类型"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _add_garrison_bonus(self, entity: int):
        """添加驻扎防御加成"""
        # 这里可以添加一个临时防御加成组件
        # 为了简化，暂时跳过实现
        pass

    def reset_turn_actions(self, faction=None):
        """重置回合行动（回合开始时调用）"""
        query = self.world.query().with_all(ActionPoints, MovementPoints, UnitStatus)

        for entity in query.entities():
            # 如果指定了阵营，只重置该阵营的单位
            if faction is not None:
                unit = self.world.get_component(entity, Unit)
                if not unit or unit.faction != faction:
                    continue

            action_points = self.world.get_component(entity, ActionPoints)
            movement = self.world.get_component(entity, MovementPoints)
            unit_status = self.world.get_component(entity, UnitStatus)
            unit_count = self.world.get_component(entity, UnitCount)

            # 重置行动力
            action_points.reset()

            # 重置移动力（考虑人数影响）
            if unit_count:
                movement.current_movement = movement.get_effective_movement(unit_count)
            else:
                movement.current_movement = movement.base_movement
            movement.has_moved = False

            # 处理状态持续时间
            if unit_status.status_duration > 0:
                unit_status.status_duration -= 1
                if unit_status.status_duration <= 0:
                    unit_status.current_status = UnitState.NORMAL

            # 处理待命后的士气高昂
            if unit_status.wait_turns > 0:
                # 如果上回合待命且未受击，获得士气高昂
                # 这里简化处理，假设待命就能获得士气高昂
                unit_status.current_status = UnitState.HIGH_MORALE
                unit_status.status_duration = 1
                unit_status.wait_turns = 0

    def _get_statistics_system(self):
        """获取统计系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None
