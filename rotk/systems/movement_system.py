"""
移动系统 - 处理单位移动
"""

from typing import Set, Tuple
from framework_v2 import System, World
from ..components import HexPosition, Movement, Unit, MapData, Terrain, Tile
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
        """移动单位到目标位置"""
        position = self.world.get_component(entity, HexPosition)
        movement = self.world.get_component(entity, Movement)

        if not position or not movement:
            return False

        # 检查是否有足够的移动力
        distance = HexMath.hex_distance((position.col, position.row), target_pos)
        if distance > movement.current_movement:
            return False

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

        # 执行移动
        position.col, position.row = target_pos
        movement.current_movement -= distance
        movement.has_moved = True

        # 更新地块占用信息
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
