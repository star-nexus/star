import numpy as np
from .tile import Tile, TileType


class MapData:
    """
    地图数据结构：存储和管理地图数据
    """

    def __init__(self, width, height):
        self.width = width  # 地图宽度（格子数）
        self.height = height  # 地图高度（格子数）
        self.tiles = {}  # 以 (x, y) 为键的格子字典

        # 初始化地图，创建所有格子
        for y in range(height):
            for x in range(width):
                self.tiles[(x, y)] = Tile(x, y, TileType.PLAINS)

    def get_tile(self, x, y):
        """获取指定坐标的格子"""
        return self.tiles.get((x, y))

    def set_tile_type(self, x, y, tile_type):
        """设置指定坐标的格子类型"""
        if (x, y) in self.tiles:
            self.tiles[(x, y)].type = tile_type
            # 更新水面通行性
            if tile_type == TileType.WATER:
                self.tiles[(x, y)].passable = False
            else:
                self.tiles[(x, y)].passable = True

    def is_valid_position(self, x, y):
        """检查坐标是否在地图范围内"""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x, y):
        """检查指定位置是否可通行"""
        tile = self.get_tile(x, y)
        return tile and tile.passable and not tile.entity

    def get_neighbors(self, x, y):
        """获取给定格子的相邻格子列表"""
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:  # 四方向
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                neighbors.append(self.get_tile(nx, ny))
        return neighbors

    def get_tiles_in_range(self, center_x, center_y, range_value):
        """获取指定范围内的所有格子"""
        tiles = []
        for y in range(center_y - range_value, center_y + range_value + 1):
            for x in range(center_x - range_value, center_x + range_value + 1):
                if self.is_valid_position(x, y):
                    tiles.append(self.get_tile(x, y))
        return tiles
