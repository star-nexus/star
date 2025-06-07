"""
移动系统 - 处理单位移动
"""

from typing import Set, Tuple
from framework_v2 import System, World
from ..components import (
    HexPosition,
    Movement,
    Unit,
    MapData,
    Terrain,
    Tile,
    MovementAnimation,
    UnitStatus,
)
from ..prefabs.config import TerrainType
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
        # 目前没有需要在每帧更新的逻辑
        pass

    def move_unit(self, entity: int, target_pos: Tuple[int, int]) -> bool:
        """移动单位到目标位置（现在支持连续移动动画）"""
        position = self.world.get_component(entity, HexPosition)
        movement = self.world.get_component(entity, Movement)

        if not position or not movement:
            return False

        # 检查是否正在移动
        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return False  # 单位正在移动中，不能开始新的移动

        # 检查路径是否可行
        obstacles = self._get_obstacles()
        path = PathFinding.find_path(
            (position.col, position.row),
            target_pos,
            obstacles,
            movement.current_movement,
        )

        if not path or len(path) < 2:
            return False

        # 检查是否有足够的移动力
        path_cost = len(path) - 1  # 路径长度减1（不包括起始点）
        if path_cost > movement.current_movement:
            return False

        # 消耗移动力
        movement.current_movement -= path_cost
        movement.has_moved = True

        # 启动移动动画
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_unit_movement(entity, path)
        else:
            # 如果没有动画系统，直接移动到目标位置
            position.col, position.row = target_pos

        # 更新地块占用信息（暂时更新到最终位置）
        self._update_tile_occupation(entity, target_pos)

        return True

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
