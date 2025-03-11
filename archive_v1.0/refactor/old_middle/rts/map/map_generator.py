import random
from .map_data import MapData
from .tile import TileType


class MapGenerator:
    """
    地图生成器：负责生成随机地图或从模板加载地图
    """

    def __init__(self):
        pass

    def generate_random_map(self, width, height, complexity=0.5):
        """
        生成随机地图
        :param width: 地图宽度（格子数）
        :param height: 地图高度（格子数）
        :param complexity: 复杂度 (0.0-1.0)，值越大地形越复杂
        :return: 生成的MapData对象
        """
        map_data = MapData(width, height)

        # 生成水域
        self._generate_water_bodies(map_data, complexity)

        # 生成山脉
        self._generate_mountains(map_data, complexity)

        # 生成森林
        self._generate_forests(map_data, complexity)

        # 生成沼泽
        self._generate_swamps(map_data, complexity)

        return map_data

    def _generate_water_bodies(self, map_data, complexity):
        """生成水域"""
        # 水域数量基于地图大小和复杂度
        num_water_bodies = int((map_data.width + map_data.height) * complexity * 0.1)

        for _ in range(num_water_bodies):
            # 随机选择一个起始点
            x = random.randint(0, map_data.width - 1)
            y = random.randint(0, map_data.height - 1)

            # 水域大小
            size = random.randint(3, 8)

            # 生成不规则水域
            self._generate_blob(map_data, x, y, size, TileType.WATER)

    def _generate_mountains(self, map_data, complexity):
        """生成山脉"""
        # 山脉数量
        num_mountain_ranges = int(
            (map_data.width + map_data.height) * complexity * 0.05
        )

        for _ in range(num_mountain_ranges):
            # 随机选择起始点
            x = random.randint(0, map_data.width - 1)
            y = random.randint(0, map_data.height - 1)

            # 生成山脉
            length = random.randint(3, 10)
            direction = random.choice([(0, 1), (1, 0), (1, 1), (-1, 1)])

            for i in range(length):
                current_x = x + direction[0] * i
                current_y = y + direction[1] * i

                if map_data.is_valid_position(current_x, current_y):
                    # 生成山峰及周围的山地
                    self._generate_blob(
                        map_data, current_x, current_y, 2, TileType.MOUNTAIN
                    )

    def _generate_forests(self, map_data, complexity):
        """生成森林"""
        # 森林数量
        num_forests = int((map_data.width + map_data.height) * complexity * 0.15)

        for _ in range(num_forests):
            # 随机选择起始点
            x = random.randint(0, map_data.width - 1)
            y = random.randint(0, map_data.height - 1)

            # 森林大小
            size = random.randint(4, 10)

            # 生成森林
            self._generate_blob(map_data, x, y, size, TileType.FOREST, 0.7)

    def _generate_swamps(self, map_data, complexity):
        """生成沼泽"""
        # 沼泽数量
        num_swamps = int((map_data.width + map_data.height) * complexity * 0.08)

        for _ in range(num_swamps):
            # 随机选择一个起始点，优先选择靠近水域的地方
            water_tiles = []
            for y in range(map_data.height):
                for x in range(map_data.width):
                    tile = map_data.get_tile(x, y)
                    if tile and tile.type == TileType.WATER:
                        for nx, ny in [
                            (x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        ]:
                            if (
                                map_data.is_valid_position(nx, ny)
                                and map_data.get_tile(nx, ny).type == TileType.PLAINS
                            ):
                                water_tiles.append((nx, ny))

            if water_tiles and random.random() < 0.7:  # 70%概率在水边生成沼泽
                x, y = random.choice(water_tiles)
            else:
                x = random.randint(0, map_data.width - 1)
                y = random.randint(0, map_data.height - 1)

            # 沼泽大小
            size = random.randint(3, 7)

            # 生成沼泽
            self._generate_blob(map_data, x, y, size, TileType.SWAMP, 0.6)

    def _generate_blob(
        self, map_data, center_x, center_y, radius, tile_type, density=0.9
    ):
        """
        生成不规则形状的地形块
        :param center_x, center_y: 中心点
        :param radius: 半径
        :param tile_type: 地形类型
        :param density: 密度，影响生成的密集程度
        """
        for y in range(center_y - radius, center_y + radius + 1):
            for x in range(center_x - radius, center_x + radius + 1):
                if map_data.is_valid_position(x, y):
                    # 计算到中心的距离
                    distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5

                    # 距离在半径内，且通过密度检查
                    if distance <= radius and random.random() < density:
                        current_tile = map_data.get_tile(x, y)

                        # 避免覆盖水域，除非我们正在创建水域
                        if (
                            tile_type == TileType.WATER
                            or current_tile.type != TileType.WATER
                        ):
                            map_data.set_tile_type(x, y, tile_type)

    def load_map_from_file(self, filename):
        """从文件加载地图（留待后续实现）"""
        # TODO: 实现从文件加载地图的功能
        pass
