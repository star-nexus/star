"""
移动系统 - 处理单位移动（按规则手册v1.2）
"""

from typing import Set, Tuple
from framework import System, World
from ..components import (
    HexPosition,
    Movement,
    Unit,
    UnitCount,
    ActionPoints,
    MapData,
    Terrain,
    Tile,
    MovementAnimation,
    UnitStatus,
)
from ..prefabs.config import TerrainType, ActionType
from ..utils.hex_utils import HexMath, PathFinding


class MovementSystem(System):
    """移动系统 - 处理单位移动"""

    def __init__(self):
        super().__init__(required_components={HexPosition, Movement, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新移动系统"""
        pass

    def move_unit(self, entity: int, target_pos: Tuple[int, int]) -> bool:
        """移动单位到目标位置"""
        position = self.world.get_component(entity, HexPosition)
        movement = self.world.get_component(entity, Movement)
        unit_count = self.world.get_component(entity, UnitCount)
        action_points = self.world.get_component(entity, ActionPoints)

        if not all([position, movement, unit_count, action_points]):
            return False

        # 检查是否正在移动
        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return False

        # 获取有效移动力（考虑人数影响）
        effective_movement = movement.get_effective_movement(unit_count)

        # 检查路径是否可行
        obstacles = self._get_obstacles()
        path = PathFinding.find_path(
            (position.col, position.row),
            target_pos,
            obstacles,
            effective_movement,
        )

        if not path or len(path) < 2:
            return False

        # 计算移动消耗（考虑地形）
        total_cost = self._calculate_total_movement_cost(path)

        if total_cost > effective_movement:
            return False

        # 检查行动力
        if not action_points.can_perform_action(ActionType.MOVE):
            return False

        print(f"✓ 单位 {entity} 移动到 {target_pos}")

        # 消耗移动力和行动力
        movement.current_movement -= total_cost
        movement.has_moved = True

        # 移动的行动力消耗等于地形移动消耗
        terrain_cost = self._get_terrain_movement_cost(target_pos)
        action_points.current_ap -= terrain_cost

        # 记录移动行动到统计系统
        statistics_system = self._get_statistics_system()
        if statistics_system:
            from_pos = (position.col, position.row)
            statistics_system.record_movement_action(entity, from_pos, target_pos)

        # 启动移动动画
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_unit_movement(entity, path)
        else:
            # 如果没有动画系统，直接移动到目标位置
            position.col, position.row = target_pos

        # 更新地块占用信息
        self._update_tile_occupation(entity, target_pos)

        # 触发地形事件
        self._trigger_terrain_events(entity, "move_end")

        return True

    def _calculate_total_movement_cost(self, path: list) -> int:
        """计算路径的总移动消耗"""
        total_cost = 0
        for i in range(1, len(path)):
            terrain_cost = self._get_terrain_movement_cost(path[i])
            total_cost += terrain_cost
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """获取地形移动消耗"""
        from ..prefabs.config import GameConfig

        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """获取位置的地形类型"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """获取所有障碍物位置"""
        obstacles = set()

        # 添加其他单位的位置
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        # 添加不可通过的地形
        map_data = self.world.get_singleton_component(MapData)
        if map_data:
            for (q, r), tile_entity in map_data.tiles.items():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.WATER:
                    obstacles.add((q, r))

        return obstacles

    def _trigger_terrain_events(self, entity: int, action: str):
        """触发地形事件"""
        # 获取随机事件系统
        for system in self.world.systems:
            if system.__class__.__name__ == "RandomEventSystem":
                system.trigger_terrain_event(entity, action)
                break

    def _get_statistics_system(self):
        """获取统计系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _get_animation_system(self):
        """获取动画系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def _update_tile_occupation(self, entity: int, position: Tuple[int, int]):
        """更新地块占用信息"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 清除之前的占用
        for tile_entity in map_data.tiles.values():
            tile = self.world.get_component(tile_entity, Tile)
            if tile and tile.occupied_by == entity:
                tile.occupied_by = None

        # 设置新的占用
        tile_entity = map_data.tiles.get(position)
        if tile_entity:
            tile = self.world.get_component(tile_entity, Tile)
            if tile:
                tile.occupied_by = entity
