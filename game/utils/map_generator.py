import numpy as np
from noise import snoise2
import random
from typing import Tuple, List, Dict, Any
import math
from .game_types import TerrainType
from .hex_utils import (
    HexCoordinate,
    create_hex_map_coordinates,
    hex_neighbors,
    hex_distance,
)


class MapGenerator:
    """地图生成器，支持六边形和方形地图"""

    def __init__(
        self,
        width: int,
        height: int,
        seed: int = None,
        map_type: str = "square",
        radius: int = None,
    ):
        """初始化地图生成器"""
        self.width = width
        self.height = height
        self.map_type = map_type
        self.radius = radius if radius is not None else min(width, height) // 2
        self.seed = seed if seed is not None else random.randint(0, 999999)
        random.seed(self.seed)
        np.random.seed(self.seed)

    def generate_elevation_map(
        self, octaves: int = 6, persistence: float = 0.5, lacunarity: float = 2.0
    ) -> np.ndarray:
        """生成海拔高度图，用于绘制等高线"""
        elevation = np.zeros((self.height, self.width), dtype=np.float32)

        # 使用Perlin噪声生成自然的地形
        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5
                elevation[y, x] = snoise2(
                    nx,
                    ny,
                    octaves=octaves,
                    persistence=persistence,
                    lacunarity=lacunarity,
                    base=self.seed,
                )

        # 归一化到0-100范围
        elevation = (
            (elevation - elevation.min()) / (elevation.max() - elevation.min()) * 100
        )
        return elevation.astype(np.int32)

    def generate_moisture_map(
        self, octaves: int = 4, persistence: float = 0.5, lacunarity: float = 2.0
    ) -> np.ndarray:
        """生成湿度图，影响植被和水系"""
        moisture = np.zeros((self.height, self.width), dtype=np.float32)

        # 使用不同的种子生成湿度
        moisture_seed = self.seed + 1000

        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5
                moisture[y, x] = snoise2(
                    nx,
                    ny,
                    octaves=octaves,
                    persistence=persistence,
                    lacunarity=lacunarity,
                    base=moisture_seed,
                )

        # 归一化到0-1范围
        moisture = (moisture - moisture.min()) / (moisture.max() - moisture.min())
        return moisture

    def _is_basin(self, elevation: np.ndarray, x: int, y: int, radius: int = 3) -> bool:
        """判断一个点是否为盆地（周围有更高的地形包围）"""
        center_elevation = elevation[y, x]
        higher_neighbors = 0
        total_neighbors = 0

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:  # 跳过中心点
                    continue

                nx, ny = x + dx, y + dy
                # 检查边界
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    total_neighbors += 1
                    if elevation[ny, nx] > center_elevation:
                        higher_neighbors += 1

        # 如果大部分邻居都比中心点高，则认为是盆地
        return higher_neighbors / total_neighbors > 0.7  # 70%的邻居更高

    def generate_terrain_map(
        self, elevation: np.ndarray, moisture: np.ndarray
    ) -> np.ndarray:
        """根据海拔和湿度生成地形类型"""
        terrain = np.zeros((self.height, self.width), dtype=np.int32)

        for y in range(self.height):
            for x in range(self.width):
                e = elevation[y, x]
                m = moisture[y, x]

                # 水系地形 (0-15)
                if e < 15:
                    # if m < 0.3:  # 浅水
                    #     terrain[y, x] = TerrainType.LAKE.value
                    # elif m < 0.6:  # 深水
                    #     terrain[y, x] = TerrainType.OCEAN.value
                    # else:  # 湿地
                    #     terrain[y, x] = TerrainType.WETLAND.value
                    terrain[y, x] = TerrainType.LAKE.value

                # 低地地形 (15-40)
                elif e < 75:  # 40:
                    if m < 0.6:  # 干燥低地
                        terrain[y, x] = TerrainType.PLAIN.value
                    # elif m < 0.6:  # 适中湿度
                    #     terrain[y, x] = TerrainType.GRASSLAND.value
                    else:  # 潮湿低地
                        terrain[y, x] = TerrainType.FOREST.value

                # # 丘陵地形 (40-60)
                # elif e < 60:
                #     if m < 0.4:  # 干燥丘陵
                #         terrain[y, x] = TerrainType.HILL.value
                #     elif m < 0.7:  # 有植被的丘陵
                #         terrain[y, x] = (
                #             TerrainType.HILL.value
                #         )  # 仍然是丘陵但后续会添加森林特性
                #     else:  # 湿润丘陵
                #         terrain[y, x] = TerrainType.FOREST.value

                # # 高原与盆地 (60-75)
                # elif e < 75:
                #     # 检查周围，如果周围都高则为盆地，否则为高原
                #     is_basin = self._is_basin(elevation, x, y)
                #     if is_basin:
                #         terrain[y, x] = TerrainType.BASIN.value
                #     else:
                #         terrain[y, x] = TerrainType.PLATEAU.value

                # 山地 (75-100)
                else:
                    terrain[y, x] = TerrainType.MOUNTAIN.value

        # 生成河流网络
        self._generate_rivers(terrain, elevation, moisture)
        # 生成道路网络
        self._generate_roads(terrain, elevation)

        return terrain

    def _generate_rivers(
        self, terrain: np.ndarray, elevation: np.ndarray, moisture: np.ndarray
    ) -> None:
        """生成河流网络"""
        # 河流数量基于地图大小
        num_rivers = max(1, int(np.sqrt(self.width * self.height) / 10))
        # 找到高处作为河流源头
        for _ in range(num_rivers):
            # 随机选择一个较高的点作为河流源头
            for _ in range(100):  # 尝试100次找到合适的点
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if elevation[y, x] > 60:  # 选择高处作为河流源头
                    self._create_river(
                        terrain, elevation, x, y, depth=0
                    )  # 显式传递初始深度为0
                    break

    def _create_river(
        self,
        terrain: np.ndarray,
        elevation: np.ndarray,
        start_x: int,
        start_y: int,
        depth: int = 0,
    ) -> None:
        """从源头创建一条河流，沿着高度最低的方向流动

        Args:
            terrain: 地形图
            elevation: 海拔图
            start_x: 起始x坐标
            start_y: 起始y坐标
            depth: 当前递归深度，用于限制分叉
        """
        # 限制最大递归深度，防止无限递归
        MAX_DEPTH = 100
        if depth > MAX_DEPTH:
            return

        x, y = start_x, start_y
        river_length = 0
        max_length = self.width + self.height  # 防止无限循环

        # 记录已经流过的点，避免形成环路
        visited = set()
        visited.add((x, y))

        while (
            0 <= x < self.width and 0 <= y < self.height and river_length < max_length
        ):
            # 标记当前位置为河流
            if terrain[y, x] not in [
                TerrainType.LAKE.value,
                TerrainType.OCEAN.value,
                TerrainType.RIVER.value,
            ]:
                terrain[y, x] = TerrainType.RIVER.value

            # 找出周围8个方向中高度最低的方向
            lowest_elevation = elevation[y, x]
            next_x, next_y = x, y
            possible_directions = []

            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue

                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        # 避免回到已经流过的点
                        if (nx, ny) in visited:
                            continue

                        # 倾向于沿着既有河流流动
                        if terrain[ny, nx] == TerrainType.RIVER.value:
                            next_x, next_y = nx, ny
                            break
                        # 或者选择高度更低的位置
                        elif elevation[ny, nx] < lowest_elevation:
                            lowest_elevation = elevation[ny, nx]
                            next_x, next_y = nx, ny
                            possible_directions.append((nx, ny, elevation[ny, nx]))

            # 如果找不到更低的位置或者已经到达水域，结束河流
            if (next_x == x and next_y == y) or terrain[next_y, next_x] in [
                TerrainType.LAKE.value,
                TerrainType.OCEAN.value,
            ]:
                break

            # 记录新位置为已访问
            visited.add((next_x, next_y))
            x, y = next_x, next_y
            river_length += 1

            # 有小概率分叉，但限制分叉条件
            # 1. 河流长度必须足够长
            # 2. 递归深度不能太大
            # 3. 分叉概率随深度降低
            branch_probability = 0.05 / (depth + 1)  # 随深度降低分叉概率
            if (
                random.random() < branch_probability
                and river_length > 5
                and depth < MAX_DEPTH
            ):
                # 只从可能的低洼方向中选择分叉，而不是随机方向
                if possible_directions:
                    # 按海拔排序，选择第二低的点作为分叉（如果有的话）
                    possible_directions.sort(key=lambda d: d[2])
                    # 确保至少有两个方向可选
                    if len(possible_directions) >= 2:
                        branch_x, branch_y, _ = possible_directions[1]  # 选择第二低的点
                        # 确保分叉点不是当前点或已访问点
                        if (branch_x, branch_y) != (x, y) and (
                            branch_x,
                            branch_y,
                        ) not in visited:
                            self._create_river(
                                terrain, elevation, branch_x, branch_y, depth + 1
                            )

    def _generate_roads(self, terrain: np.ndarray, elevation: np.ndarray) -> None:
        """生成道路网络，连接城市和村庄"""
        # 放置一些城市和村庄
        settlements = []

        # 城市数量基于地图大小
        num_cities = max(2, int(np.sqrt(self.width * self.height) / 15))
        num_villages = num_cities * 3

        # 放置城市（在平原或丘陵上）
        for _ in range(num_cities):
            for _ in range(100):  # 尝试100次找到合适的位置
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                # 城市通常位于平原、草地或丘陵上，离河流或湖泊不远
                if terrain[y, x] in [
                    TerrainType.PLAIN.value,
                    TerrainType.GRASSLAND.value,
                    TerrainType.HILL.value,
                ]:
                    # 检查是否靠近水源
                    has_water = False
                    for dy in range(-3, 4):
                        for dx in range(-3, 4):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if terrain[ny, nx] in [
                                    TerrainType.RIVER.value,
                                    TerrainType.LAKE.value,
                                ]:
                                    has_water = True
                                    break
                        if has_water:
                            break

                    if has_water or random.random() < 0.3:  # 允许一些城市不靠近水源
                        terrain[y, x] = TerrainType.CITY.value
                        settlements.append((x, y, True))  # True表示城市
                        break

        # # 放置村庄（更随机的位置）
        # for _ in range(num_villages):
        #     for _ in range(50):  # 尝试50次找到合适的位置
        #         x = random.randint(0, self.width - 1)
        #         y = random.randint(0, self.height - 1)
        #         if terrain[y, x] in [
        #             TerrainType.PLAIN.value,
        #             TerrainType.GRASSLAND.value,
        #             TerrainType.HILL.value,
        #             TerrainType.FOREST.value,
        #         ]:
        #             terrain[y, x] = TerrainType.VILLAGE.value
        #             settlements.append((x, y, False))  # False表示村庄
        #             break

        # # 连接城市和村庄
        # # 首先连接所有城市
        # cities = [s for s in settlements if s[2]]
        # for i in range(len(cities)):
        #     # 每个城市至少连接到一个其他城市
        #     nearest_city = None
        #     min_dist = float("inf")

        #     for j in range(len(cities)):
        #         if i != j:
        #             x1, y1, _ = cities[i]
        #             x2, y2, _ = cities[j]
        #             dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        #             if dist < min_dist:
        #                 min_dist = dist
        #                 nearest_city = cities[j]

        #     if nearest_city:
        #         x1, y1, _ = cities[i]
        #         x2, y2, _ = nearest_city
        #         self._create_road(terrain, elevation, (x1, y1), (x2, y2))

        # # 然后将村庄连接到最近的城市或道路
        # villages = [s for s in settlements if not s[2]]
        # for village in villages:
        #     x1, y1, _ = village

        #     # 寻找最近的城市或现有道路
        #     nearest_point = None
        #     min_dist = float("inf")

        #     # 检查所有城市
        #     for city in cities:
        #         x2, y2, _ = city
        #         dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        #         if dist < min_dist:
        #             min_dist = dist
        #             nearest_point = (x2, y2)

        #     # 检查现有道路
        #     for y in range(self.height):
        #         for x in range(self.width):
        #             if terrain[y, x] == TerrainType.ROAD.value:
        #                 dist = math.sqrt((x - x1) ** 2 + (y - y1) ** 2)
        #                 if dist < min_dist:
        #                     min_dist = dist
        #                     nearest_point = (x, y)

        #     if nearest_point and random.random() < 0.7:  # 70%的村庄有道路
        #         self._create_road(terrain, elevation, (x1, y1), nearest_point)

    def _create_road(
        self,
        terrain: np.ndarray,
        elevation: np.ndarray,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> None:
        """在两点之间创建道路，考虑地形因素"""
        x1, y1 = start
        x2, y2 = end

        # A*寻路算法权重地图（根据地形设置移动成本）
        weights = np.ones((self.height, self.width), dtype=np.float32) * 10.0

        # 设置不同地形的移动成本
        for y in range(self.height):
            for x in range(self.width):
                terrain_type = terrain[y, x]
                e = elevation[y, x]

                # 水域和山脉更难通过
                if terrain_type in [
                    TerrainType.LAKE.value,
                    TerrainType.OCEAN.value,
                    TerrainType.RIVER.value,
                ]:
                    weights[y, x] = 100.0  # 水域难以通过，但不是不可能（可以建桥）
                elif terrain_type == TerrainType.MOUNTAIN.value:
                    weights[y, x] = 50.0  # 山地很难通过
                elif (
                    terrain_type == TerrainType.HILL.value
                    or terrain_type == TerrainType.PLATEAU.value
                ):
                    weights[y, x] = 5.0  # 丘陵和高原略微困难
                elif terrain_type == TerrainType.FOREST.value:
                    weights[y, x] = 3.0  # 森林略微困难
                elif terrain_type == TerrainType.ROAD.value:
                    weights[y, x] = 0.5  # 现有道路很容易通过
                else:
                    weights[y, x] = 1.0  # 平原、草地等容易通过

                # 高度变化增加难度
                if x > 0:
                    weights[y, x] += abs(elevation[y, x] - elevation[y, x - 1]) * 0.1
                if y > 0:
                    weights[y, x] += abs(elevation[y, x] - elevation[y - 1, x]) * 0.1

        # 简化版A*路径，这里使用Bresenham算法代替，实际项目应使用真正的A*
        # Bresenham直线算法
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while x != x2 or y != y2:
            if 0 <= x < self.width and 0 <= y < self.height:
                if terrain[y, x] not in [
                    TerrainType.CITY.value,
                    TerrainType.VILLAGE.value,
                ]:
                    # 如果是水域，则设为桥梁
                    if terrain[y, x] in [
                        TerrainType.RIVER.value,
                        TerrainType.LAKE.value,
                    ]:
                        terrain[y, x] = TerrainType.BRIDGE.value
                    else:
                        terrain[y, x] = TerrainType.ROAD.value

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def generate_hex_terrain_map(self, radius: int) -> Dict[Tuple[int, int, int], int]:
        """为六边形地图生成地形"""
        # 获取所有六边形坐标
        hex_coords = create_hex_map_coordinates(radius)
        terrain_map = {}

        # 使用噪声生成基础地形
        for hex_coord in hex_coords:
            # 将六边形坐标转换为噪声输入
            x_noise = hex_coord.q * 0.3
            y_noise = hex_coord.r * 0.3

            # 生成噪声值
            elevation_noise = snoise2(x_noise, y_noise, octaves=4, base=self.seed)
            moisture_noise = snoise2(
                x_noise + 100, y_noise + 100, octaves=2, base=self.seed + 1000
            )

            # 归一化
            elevation = (elevation_noise + 1) * 50  # 0-100
            moisture = (moisture_noise + 1) * 0.5  # 0-1

            # 根据elevation和moisture确定地形类型
            terrain_type = self._determine_terrain_type(elevation, moisture)
            terrain_map[hex_coord.to_tuple()] = terrain_type.value

        # 生成河流网络
        self._generate_hex_rivers(terrain_map, hex_coords)

        # 生成城市
        self._generate_hex_cities(terrain_map, hex_coords)

        return terrain_map

    def _determine_terrain_type(self, elevation: float, moisture: float) -> TerrainType:
        """根据海拔和湿度确定地形类型"""
        if elevation < 20:
            return TerrainType.LAKE
        elif elevation < 60:
            if moisture < 0.3:
                return TerrainType.PLAIN
            else:
                return TerrainType.FOREST
        else:
            return TerrainType.MOUNTAIN

    def _generate_hex_rivers(
        self,
        terrain_map: Dict[Tuple[int, int, int], int],
        hex_coords: List[HexCoordinate],
    ):
        """在六边形地图上生成河流"""
        num_rivers = max(1, len(hex_coords) // 20)

        for _ in range(num_rivers):
            # 选择高地作为河流源头
            mountain_coords = [
                coord
                for coord in hex_coords
                if terrain_map[coord.to_tuple()] == TerrainType.MOUNTAIN.value
            ]

            if not mountain_coords:
                continue

            start_coord = random.choice(mountain_coords)
            self._create_hex_river(terrain_map, start_coord, hex_coords)

    def _create_hex_river(
        self,
        terrain_map: Dict[Tuple[int, int, int], int],
        start: HexCoordinate,
        all_coords: List[HexCoordinate],
    ):
        """创建一条六边形河流"""
        current = start
        visited = set()
        max_length = len(all_coords) // 4

        for _ in range(max_length):
            if current.to_tuple() in visited:
                break

            visited.add(current.to_tuple())

            # 标记为河流
            if terrain_map.get(current.to_tuple()) != TerrainType.LAKE.value:
                terrain_map[current.to_tuple()] = TerrainType.RIVER.value

            # 寻找下一个位置（向中心或随机方向）
            neighbors = hex_neighbors(current)
            valid_neighbors = [n for n in neighbors if n.to_tuple() in terrain_map]

            if not valid_neighbors:
                break

            # 优先选择距离地图中心更远的邻居（模拟流向边缘）
            center = HexCoordinate(0, 0, 0)
            current = min(valid_neighbors, key=lambda n: hex_distance(n, center))

    def _generate_hex_cities(
        self,
        terrain_map: Dict[Tuple[int, int, int], int],
        hex_coords: List[HexCoordinate],
    ):
        """在六边形地图上生成城市"""
        num_cities = max(2, len(hex_coords) // 15)

        # 选择平原或森林作为城市位置
        suitable_coords = [
            coord
            for coord in hex_coords
            if terrain_map[coord.to_tuple()]
            in [TerrainType.PLAIN.value, TerrainType.FOREST.value]
        ]

        if len(suitable_coords) < num_cities:
            return

        # 随机选择城市位置，确保它们不会太靠近
        cities = []
        for _ in range(num_cities):
            available = [
                coord
                for coord in suitable_coords
                if all(hex_distance(coord, city) >= 2 for city in cities)
            ]
            if available:
                city = random.choice(available)
                cities.append(city)
                terrain_map[city.to_tuple()] = TerrainType.CITY.value

    def create_symmetric_hex_terrain(
        self, radius: int
    ) -> Dict[Tuple[int, int, int], int]:
        """创建对称的六边形地形图"""
        hex_coords = create_hex_map_coordinates(radius)
        terrain_map = {}

        # 初始化为平原
        for coord in hex_coords:
            terrain_map[coord.to_tuple()] = TerrainType.PLAIN.value

        # 中心为河流/湖泊
        center = HexCoordinate(0, 0, 0)
        terrain_map[center.to_tuple()] = TerrainType.LAKE.value

        # 在特定位置放置山脉（对称）
        if radius >= 2:
            mountains = [
                HexCoordinate(2, -1, -1),  # 右上
                HexCoordinate(-1, 2, -1),  # 左下
                HexCoordinate(-1, -1, 2),  # 左上
            ]
            for mountain in mountains:
                if mountain.to_tuple() in terrain_map:
                    terrain_map[mountain.to_tuple()] = TerrainType.MOUNTAIN.value

        # 在特定位置放置森林
        if radius >= 2:
            forests = [
                HexCoordinate(1, 0, -1),  # 右
                HexCoordinate(-1, 0, 1),  # 左
                HexCoordinate(0, 1, -1),  # 右下
                HexCoordinate(0, -1, 1),  # 左上
            ]
            for forest in forests:
                if forest.to_tuple() in terrain_map:
                    terrain_map[forest.to_tuple()] = TerrainType.FOREST.value

        # 在边缘放置城市
        if radius >= 3:
            cities = [
                HexCoordinate(radius, 0, -radius),  # 右边缘
                HexCoordinate(-radius, 0, radius),  # 左边缘
            ]
            for city in cities:
                if city.to_tuple() in terrain_map:
                    terrain_map[city.to_tuple()] = TerrainType.CITY.value

        return terrain_map

    def generate_map(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """生成完整地图，返回(海拔图, 地形图, 湿度图)"""
        if self.map_type == "hexagonal":
            # 为六边形地图生成伪方形数组以保持兼容性
            terrain_dict = self.generate_hex_terrain_map(self.radius)

            # 创建方形数组存储（用于兼容现有代码）
            terrain = np.zeros((self.height, self.width), dtype=np.int32)
            elevation = np.zeros((self.height, self.width), dtype=np.int32)
            moisture = np.zeros((self.height, self.width), dtype=np.float32)

            # 将六边形数据映射到方形数组（简化处理）
            for (q, r, s), terrain_type in terrain_dict.items():
                # 转换为偏移坐标
                col = q + self.radius
                row = r + self.radius
                if 0 <= col < self.width and 0 <= row < self.height:
                    terrain[row, col] = terrain_type
                    elevation[row, col] = 50  # 默认海拔
                    moisture[row, col] = 0.5  # 默认湿度

            return elevation, terrain, moisture
        else:
            # 原有的方形地图生成逻辑
            elevation = self.generate_elevation_map()
            moisture = self.generate_moisture_map()
            terrain = self.generate_terrain_map(elevation, moisture)
            return elevation, terrain, moisture

    def generate_v1_map(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """生成完整地图，返回(海拔图, 地形图, 湿度图)"""
        from game.utils.map_data_generator import generate_map_data

        elevation = None
        moisture = None
        # 因为 宽 高 相等 所以 只需要一个参数
        terrain = generate_map_data(self.width)
        return elevation, terrain, moisture
