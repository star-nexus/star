"""
地图系统 - 管理地图生成和地形
"""

import random
import math
from framework import System, World
from ..components import HexPosition, Terrain, MapData
from ..prefabs.config import GameConfig, TerrainType


class Tile:
    """临时地块类，用于兼容现有代码"""

    def __init__(self, position):
        self.position = position


class MapSystem(System):
    """地图系统 - 管理地图生成和地形"""

    def __init__(self):
        super().__init__(priority=100)  # 高优先级，最先初始化

    def initialize(self, world: World) -> None:
        self.world = world
        self.generate_map()

    def subscribe_events(self):
        """订阅事件"""
        # 目前没有需要订阅的事件
        pass

    def update(self, delta_time: float) -> None:
        """更新地图系统"""
        # 地图生成在初始化时完成，通常不需要在每帧更新
        pass

    def generate_map(self):
        """生成地图"""
        map_data = MapData(
            width=GameConfig.MAP_WIDTH, height=GameConfig.MAP_HEIGHT, tiles={}
        )

        # 生成50x50的正方形地图
        for q in range(GameConfig.MAP_WIDTH):
            for r in range(GameConfig.MAP_HEIGHT):
                # 转换为以中心为原点的坐标系
                center_q = q - GameConfig.MAP_WIDTH // 2
                center_r = r - GameConfig.MAP_HEIGHT // 2

                # 随机生成地形
                terrain_type = self._generate_terrain(center_q, center_r)

                # 创建地块实体
                tile_entity = self.world.create_entity()
                self.world.add_component(tile_entity, HexPosition(center_q, center_r))
                self.world.add_component(tile_entity, Terrain(terrain_type))
                self.world.add_component(tile_entity, Tile((center_q, center_r)))

                # 添加到地图数据
                map_data.tiles[(center_q, center_r)] = tile_entity

        self.world.add_singleton_component(map_data)

    def _generate_terrain(self, q: int, r: int) -> TerrainType:
        """生成地形类型 - 适配50x50大地图"""
        # 使用固定种子确保地形生成的一致性
        rand = random.Random(q * 10007 + r * 10009)
        value = rand.random()

        # 距离中心的距离
        distance = math.sqrt(q * q + r * r)
        max_distance = math.sqrt(25 * 25 + 25 * 25)  # 50x50地图的最大距离
        distance_ratio = distance / max_distance

        # 基于距离和随机值决定地形
        if distance < 3:
            # 中心区域：更多城池和平原
            if value < 0.2:
                return TerrainType.URBAN
            elif value < 0.7:
                return TerrainType.PLAIN
            elif value < 0.85:
                return TerrainType.HILL
            else:
                return TerrainType.FOREST
        elif distance_ratio > 0.8:
            # 边缘区域：更多山地和水域
            if value < 0.25:
                return TerrainType.MOUNTAIN
            elif value < 0.4:
                return TerrainType.WATER
            elif value < 0.7:
                return TerrainType.FOREST
            else:
                return TerrainType.HILL
        elif distance_ratio > 0.6:
            # 外围区域：混合地形
            if value < 0.3:
                return TerrainType.FOREST
            elif value < 0.5:
                return TerrainType.HILL
            elif value < 0.65:
                return TerrainType.MOUNTAIN
            elif value < 0.75:
                return TerrainType.WATER
            else:
                return TerrainType.PLAIN
        else:
            # 中间区域：平衡的多样化地形
            if value < 0.35:
                return TerrainType.PLAIN
            elif value < 0.55:
                return TerrainType.FOREST
            elif value < 0.75:
                return TerrainType.HILL
            elif value < 0.85:
                return TerrainType.MOUNTAIN
            elif value < 0.92:
                return TerrainType.WATER
            else:
                return TerrainType.URBAN
