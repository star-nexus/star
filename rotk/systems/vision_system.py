"""
视野系统 - 处理战争迷雾和视野计算
"""

from typing import Set, Tuple
from framework_v2 import System, World
from ..components import HexPosition, Vision, Unit, FogOfWar, MapData, Terrain
from ..prefabs.config import GameConfig, TerrainType
from ..utils.hex_utils import HexMath


class VisionSystem(System):
    """视野系统 - 处理战争迷雾和视野计算"""

    def __init__(self):
        super().__init__(required_components={HexPosition, Vision, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新视野系统"""
        self._update_fog_of_war()

    def _update_fog_of_war(self):
        """更新战争迷雾"""
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        if not fog_of_war:
            fog_of_war = FogOfWar()
            self.world.add_singleton_component(fog_of_war)

        # 清空当前视野
        fog_of_war.faction_vision.clear()

        # 计算每个单位的视野
        for entity in self.world.query().with_all(HexPosition, Vision, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            vision = self.world.get_component(entity, Vision)
            unit = self.world.get_component(entity, Unit)

            if not position or not vision or not unit:
                continue

            # 计算视野范围
            visible_tiles = self._calculate_vision(
                (position.col, position.row), vision.range, entity
            )

            # 更新单位的可见地块
            vision.visible_tiles = visible_tiles

            # 更新阵营视野
            if unit.faction not in fog_of_war.faction_vision:
                fog_of_war.faction_vision[unit.faction] = set()

            fog_of_war.faction_vision[unit.faction].update(visible_tiles)

            # 更新探索过的区域
            if unit.faction not in fog_of_war.explored_tiles:
                fog_of_war.explored_tiles[unit.faction] = set()

            fog_of_war.explored_tiles[unit.faction].update(visible_tiles)

    def _calculate_vision(
        self, center: Tuple[int, int], range_val: int, observer_entity: int
    ) -> Set[Tuple[int, int]]:
        """计算视野范围"""
        visible = set()
        q, r = center

        # 获取地形加成
        terrain_bonus = self._get_vision_terrain_bonus(center)
        effective_range = range_val + terrain_bonus

        # 使用射线追踪算法计算视野
        for target_q in range(q - effective_range, q + effective_range + 1):
            for target_r in range(r - effective_range, r + effective_range + 1):
                target_pos = (target_q, target_r)

                # 检查距离
                if HexMath.hex_distance(center, target_pos) <= effective_range:
                    # 检查视线是否被阻挡
                    if self._has_line_of_sight(center, target_pos):
                        visible.add(target_pos)

        return visible

    def _has_line_of_sight(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """检查两点间是否有视线"""
        line = HexMath.line_of_sight(start, end)

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True

        for pos in line[1:-1]:  # 不包括起点和终点
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.MOUNTAIN:
                    return False  # 山地阻挡视线

        return True

    def _get_vision_terrain_bonus(self, position: Tuple[int, int]) -> int:
        """获取地形视野加成"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        terrain = self.world.get_component(tile_entity, Terrain)
        if not terrain:
            return 0

        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain.terrain_type)
        return terrain_effect.vision_bonus if terrain_effect else 0
