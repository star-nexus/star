import pygame
import numpy as np
from enum import Enum, auto

# from map_generator import MapGenerator  # 假设你的地图生成器类在 'map_generator.py' 中
# from game_types import TerrainType  # 导入地形类型枚举


import numpy as np
from noise import snoise2, snoise3
import random
from typing import Tuple, List, Dict, Any
import math
# from scipy.ndimage import gaussian_filter, median_filter
# from .game_types import TerrainType


class TerrainType(Enum):
    """地形类型枚举"""

    # 基本地形类型
    PLAIN = auto()  # 平原
    HILL = auto()  # 丘陵
    MOUNTAIN = auto()  # 山地
    PLATEAU = auto()  # 高原
    BASIN = auto()  # 盆地

    DEEP_WATER = auto()  # 深海

    # 植被类型
    FOREST = auto()  # 森林

    GRASSLAND = auto()  # 草地

    # 水系
    RIVER = auto()  # 河流
    LAKE = auto()  # 湖泊
    OCEAN = auto()  # 海洋
    WETLAND = auto()  # 湿地

    # 特殊地形
    ROAD = auto()  # 道路
    BRIDGE = auto()  # 桥梁
    CITY = auto()  # 城市
    VILLAGE = auto()  # 村庄
    CASTLE = auto()  # 城堡
    PASS = auto()  # 关隘/隘口

    SHALLOW_WATER = auto()  # 浅水
    # 混合地形
    MIXED_FOREST = auto()  # 混合林
    CONIFEROUS_FOREST = auto()  # 针叶林
    DECIDUOUS_FOREST = auto()  # 落叶林
    RAIN_FOREST = auto()  # 雨林
    # 混合
    xc = auto()  # 混合林
    SUBURB = auto()  # 郊区
    MAJOR_ROAD = auto()  # 主要道路
    MAJOR_BRIDGE = auto()  # 主要桥梁
    MOUNTAIN_TUNDRA = auto()  # 山地苔原


class MapGenerator:
    """地图生成器，使用噪声算法生成地形，支持等高线地图、道路和水系"""

    def __init__(self, width: int, height: int, seed: int = None):
        """初始化地图生成器"""
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 999999)
        random.seed(self.seed)
        np.random.seed(self.seed)

    def _smooth_map(self, map_array: np.ndarray, radius: int = 3) -> np.ndarray:
        """使用高斯滤波平滑地图数据"""
        # 使用简单的均值滤波代替高斯滤波
        smoothed = np.copy(map_array)
        for i in range(radius, map_array.shape[0] - radius):
            for j in range(radius, map_array.shape[1] - radius):
                window = map_array[
                    i - radius : i + radius + 1, j - radius : j + radius + 1
                ]
                smoothed[i, j] = np.mean(window)
        return smoothed

    def generate_elevation_map(
        self, octaves: int = 6, persistence: float = 0.5, lacunarity: float = 2.0
    ) -> np.ndarray:
        """生成海拔高度图，用于绘制等高线"""
        elevation = np.zeros((self.height, self.width), dtype=np.float32)

        # 使用Perlin噪声生成自然的地形
        scale = max(30, min(100, (self.width + self.height) // 20))

        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width
                ny = y / self.height
                elevation[y, x] = snoise2(
                    nx * scale,
                    ny * scale,
                    octaves=octaves,
                    persistence=persistence,
                    lacunarity=lacunarity,
                    base=self.seed,
                )

        # 归一化到0-100范围
        elevation = (
            (elevation - elevation.min()) / (elevation.max() - elevation.min()) * 100
        )

        # 添加一些局部变化
        detail_scale = scale * 4
        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width
                ny = y / self.height
                detail = snoise2(
                    nx * detail_scale,
                    ny * detail_scale,
                    octaves=3,
                    persistence=0.6,
                    lacunarity=2.5,
                    base=self.seed + 12345,
                )
                elevation[y, x] += detail * 10  # 添加局部变化

        elevation = (
            (elevation - elevation.min()) / (elevation.max() - elevation.min()) * 100
        )

        # 平滑处理
        elevation = self._smooth_map(elevation, radius=3)
        return elevation.astype(np.int32)

    def generate_moisture_map(
        self, octaves: int = 4, persistence: float = 0.5, lacunarity: float = 2.0
    ) -> np.ndarray:
        """生成湿度图，影响植被和水系"""
        moisture = np.zeros((self.height, self.width), dtype=np.float32)

        # 使用不同的种子生成湿度
        scale = max(30, min(100, (self.width + self.height) // 20))

        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width
                ny = y / self.height
                moisture[y, x] = snoise2(
                    nx * scale,
                    ny * scale,
                    octaves=octaves,
                    persistence=persistence,
                    lacunarity=lacunarity,
                    base=self.seed + 1000,
                )

        # 归一化到0-1范围
        moisture = (moisture - moisture.min()) / (moisture.max() - moisture.min())

        # 添加地形影响湿度
        elevation = self.generate_elevation_map()
        for y in range(self.height):
            for x in range(self.width):
                e = elevation[y, x]
                # 高海拔地区更干燥
                if e > 50:
                    moisture[y, x] *= 0.8 - (e - 50) * 0.005
                # 低洼地区更潮湿
                elif e < 30:
                    moisture[y, x] *= 1.2 + (30 - e) * 0.01

        moisture = np.clip(moisture, 0, 1)
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

    def _determine_plant_type(
        self, elevation: np.ndarray, moisture: np.ndarray, x: int, y: int
    ) -> int:
        """根据海拔和湿度确定植被类型"""
        e = elevation[y, x]
        m = moisture[y, x]

        # 高海拔区域主要是草地和苔原
        if e >= 75:
            if m < 0.3:
                return TerrainType.MOUNTAIN.value  # 岩石山地
            else:
                return TerrainType.MOUNTAIN_TUNDRA.value  # 高山苔原

        # 低海拔区域根据湿度变化
        elif e < 30:
            if m < 0.2:
                return TerrainType.PLAIN.value  # 干旱平原
            elif m < 0.5:
                return TerrainType.GRASSLAND.value  # 草原
            elif m < 0.7:
                return TerrainType.DECIDUOUS_FOREST.value  # 落叶林
            else:
                return TerrainType.RAIN_FOREST.value  # 雨林

        # 中海拔区域
        else:
            if m < 0.2:
                return TerrainType.HILL.value  # 干旱丘陵
            elif m < 0.6:
                return TerrainType.MIXED_FOREST.value  # 混合林
            else:
                return TerrainType.CONIFEROUS_FOREST.value  # 针叶林

    def generate_terrain_map(
        self, elevation: np.ndarray, moisture: np.ndarray
    ) -> np.ndarray:
        """根据海拔和湿度生成地形类型"""
        terrain = np.zeros((self.height, self.width), dtype=np.int32)

        # 生成基础地形
        for y in range(self.height):
            for x in range(self.width):
                e = elevation[y, x]
                m = moisture[y, x]

                # 水系地形 (0-10)
                if e < 10:
                    if m < 0.5:  # 浅水
                        terrain[y, x] = TerrainType.SHALLOW_WATER.value
                    else:  # 深水
                        terrain[y, x] = TerrainType.DEEP_WATER.value

                # 低地地形 (10-30)
                elif e < 30:
                    terrain[y, x] = self._determine_plant_type(
                        elevation, moisture, x, y
                    )

                # 丘陵地形 (30-60)
                elif e < 60:
                    terrain[y, x] = self._determine_plant_type(
                        elevation, moisture, x, y
                    )

                # 高原与盆地 (60-75)
                elif e < 75:
                    # 检查周围，如果周围都高则为盆地，否则为高原
                    is_basin = self._is_basin(elevation, x, y)
                    if is_basin:
                        terrain[y, x] = TerrainType.BASIN.value
                    else:
                        terrain[y, x] = self._determine_plant_type(
                            elevation, moisture, x, y
                        )

                # 山地 (75-100)
                else:
                    terrain[y, x] = self._determine_plant_type(
                        elevation, moisture, x, y
                    )

        # 生成河流网络
        self._generate_rivers(terrain, elevation)
        # 生成道路网络
        self._generate_roads(terrain, elevation)
        # 生成聚居地
        self._generate_settlements(terrain, elevation)

        # 添加一些随机变化以增加真实性
        for y in range(self.height):
            for x in range(self.width):
                # 有小概率改变地形类型以模拟自然变化
                if random.random() < 0.01:
                    current_type = terrain[y, x]
                    # 避免改变水域类型
                    if current_type not in [
                        TerrainType.SHALLOW_WATER.value,
                        TerrainType.DEEP_WATER.value,
                        TerrainType.RIVER.value,
                        TerrainType.LAKE.value,
                    ]:
                        # 附近随机位置
                        dx = random.randint(-2, 2)
                        dy = random.randint(-2, 2)
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            # 与附近地形混合
                            new_type = (current_type + terrain[ny, nx]) // 2
                            terrain[y, x] = new_type

        return terrain

    def _generate_rivers(self, terrain: np.ndarray, elevation: np.ndarray) -> None:
        """生成河流网络"""
        num_rivers = max(1, int(np.sqrt(self.width * self.height) / 30))

        # 生成多个河源点
        river_sources = []
        for _ in range(num_rivers * 5):  # 生成比需要多的河源点
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if elevation[y, x] > 70 and terrain[y, x] not in [
                TerrainType.RIVER.value,
                TerrainType.SHALLOW_WATER.value,
                TerrainType.DEEP_WATER.value,
            ]:
                river_sources.append((x, y))

        # 选择最有可能的河源点
        # 根据海拔高度排序
        river_sources.sort(key=lambda p: elevation[p[1], p[0]], reverse=True)
        river_sources = river_sources[:num_rivers]

        # 为每个河源点创建河流
        for source in river_sources:
            self._create_river(terrain, elevation, source[0], source[1])

    def _create_river(
        self,
        terrain: np.ndarray,
        elevation: np.ndarray,
        start_x: int,
        start_y: int,
    ) -> None:
        """从源头创建一条河流，沿着高度最低的方向流动"""
        x, y = start_x, start_y
        river_length = 0
        max_length = min(
            500, max(100, self.width * self.height // 100)
        )  # 合理的最大长度

        # 记录已经流过的点，避免形成环路
        visited = set()
        visited.add((x, y))
        river_course = [(x, y)]

        while (
            0 <= x < self.width
            and 0 <= y < self.height
            and river_length < max_length
            and terrain[y, x]
            not in [TerrainType.SHALLOW_WATER.value, TerrainType.DEEP_WATER.value]
        ):
            # 标记当前位置为河流
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

                        # 收集可能的方向
                        possible_directions.append((nx, ny, elevation[ny, nx]))

            # 如果没有可能的方向，尝试扩大搜索范围
            if not possible_directions:
                # 尝试在附近区域寻找方向
                for d in range(2, 4):
                    for dy in range(-d, d + 1):
                        for dx in range(-d, d + 1):
                            if dx == 0 and dy == 0:
                                continue

                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if (nx, ny) not in visited:
                                    possible_directions.append(
                                        (nx, ny, elevation[ny, nx])
                                    )
                    if possible_directions:
                        break

            # 如果找到可能的方向
            if possible_directions:
                # 按高度排序，选择最低的位置
                possible_directions.sort(key=lambda d: d[2])
                next_x, next_y, _ = possible_directions[0]

                # 记录新位置为已访问
                visited.add((next_x, next_y))
                river_course.append((next_x, next_y))
                x, y = next_x, next_y
                river_length += 1

            # 如果没有找到方向，或者到达水域，结束河流
            else:
                break

        # 如果河流长度超过一定值，可能形成湖泊
        if river_length > max_length // 3:
            self._form_lake(terrain, river_course)

    def _form_lake(
        self, terrain: np.ndarray, river_course: List[Tuple[int, int]]
    ) -> None:
        """在河流末端形成湖泊"""
        # 取河流末端附近的几个点
        lake_points = []
        for i in range(-1, -6, -1):
            if abs(i) < len(river_course):
                x, y = river_course[i]
                lake_points.append((x, y))

                # 将末端的河流点改为湖泊
                terrain[y, x] = TerrainType.LAKE.value

                # 将周边区域也改为湖泊
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if terrain[ny, nx] not in [
                                TerrainType.SHALLOW_WATER.value,
                                TerrainType.DEEP_WATER.value,
                                TerrainType.LAKE.value,
                            ]:
                                if random.random() < 0.7 - max(abs(dx), abs(dy)) * 0.1:
                                    terrain[ny, nx] = TerrainType.LAKE.value
                                    lake_points.append((nx, ny))

    def _generate_roads(self, terrain: np.ndarray, elevation: np.ndarray) -> None:
        """生成道路网络，连接城市和村庄"""
        # 放置一些城市和村庄
        settlements = []

        # 城市数量基于地图大小
        num_cities = max(2, int(np.sqrt(self.width * self.height) / 30))
        num_villages = num_cities * 5

        # 放置城市（在平原或丘陵上）
        for _ in range(num_cities):
            for _ in range(100):  # 尝试100次找到合适的位置
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                # 城市通常位于平原和低矮丘陵上
                if terrain[y, x] in [
                    TerrainType.GRASSLAND.value,
                    TerrainType.PLAIN.value,
                    TerrainType.MIXED_FOREST.value,
                ]:
                    # 检查是否靠近水源
                    has_water = False
                    for dy in range(-5, 6):
                        for dx in range(-5, 6):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if terrain[ny, nx] in [
                                    TerrainType.RIVER.value,
                                    TerrainType.LAKE.value,
                                    TerrainType.SHALLOW_WATER.value,
                                ]:
                                    has_water = True
                                    break
                        if has_water:
                            break

                    if has_water or random.random() < 0.5:  # 允许一些城市不靠近水源
                        terrain[y, x] = TerrainType.CITY.value
                        settlements.append((x, y, True, 5))  # 大城市
                        # 添加一些周围建筑
                        for dy in range(-3, 4):
                            for dx in range(-3, 4):
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < self.width and 0 <= ny < self.height:
                                    if (
                                        random.random()
                                        < 0.3 - max(abs(dx), abs(dy)) * 0.05
                                    ):
                                        terrain[ny, nx] = TerrainType.SUBURB.value
                        break

        # 放置村庄（更随机的位置）
        for _ in range(num_villages):
            for _ in range(50):  # 尝试50次找到合适的位置
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if terrain[y, x] in [
                    TerrainType.GRASSLAND.value,
                    TerrainType.PLAIN.value,
                    TerrainType.MIXED_FOREST.value,
                    TerrainType.DECIDUOUS_FOREST.value,
                ]:
                    terrain[y, x] = TerrainType.VILLAGE.value
                    settlements.append((x, y, False, 1))  # 小村庄
                    break

        # 构建道路网络
        if settlements:
            # 创建最小生成树连接所有定居点
            self._create_road_network(terrain, settlements)

            # 添加一些次要道路
            self._add_secondary_roads(terrain)

    def _create_road_network(
        self, terrain: np.ndarray, settlements: List[Tuple[int, int, bool, int]]
    ) -> None:
        """使用Kruskal算法创建连接所有定居点的道路网络"""
        # 计算所有定居点之间的距离
        num_settlements = len(settlements)
        if num_settlements < 2:
            return

        # 创建边列表
        edges = []
        for i in range(num_settlements):
            x1, y1, _, size1 = settlements[i]
            for j in range(i + 1, num_settlements):
                x2, y2, _, size2 = settlements[j]
                distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                # 考虑定居点大小
                weight = distance / (size1 + size2)
                edges.append((i, j, weight))

        # 按权重排序
        edges.sort(key=lambda e: e[2])

        # 初始化并查集
        parent = list(range(num_settlements))

        def find(u):
            while parent[u] != u:
                parent[u] = parent[parent[u]]
                u = parent[u]
            return u

        def union(u, v):
            u_root = find(u)
            v_root = find(v)
            if u_root == v_root:
                return False
            parent[v_root] = u_root
            return True

        # Kruskal算法
        for edge in edges:
            u, v, weight = edge
            if union(u, v):
                # 连接这两个定居点
                x1, y1, _, _ = settlements[u]
                x2, y2, _, _ = settlements[v]
                self._create_road(terrain, (x1, y1), (x2, y2))

    def _add_secondary_roads(self, terrain: np.ndarray) -> None:
        """添加一些次要道路以增加网络密度"""
        for _ in range(max(10, self.width * self.height // 1000)):
            # 随机选择起点和终点
            x1 = random.randint(0, self.width - 1)
            y1 = random.randint(0, self.height - 1)
            if terrain[y1, x1] in [
                TerrainType.CITY.value,
                TerrainType.ROAD.value,
                TerrainType.VILLAGE.value,
            ]:
                x2 = random.randint(0, self.width - 1)
                y2 = random.randint(0, self.height - 1)
                if terrain[y2, x2] in [
                    TerrainType.CITY.value,
                    TerrainType.ROAD.value,
                    TerrainType.VILLAGE.value,
                ]:
                    self._create_road(terrain, (x1, y1), (x2, y2), minor=True)

    def _create_road(
        self,
        terrain: np.ndarray,
        start: Tuple[int, int],
        end: Tuple[int, int],
        minor: bool = False,
    ) -> None:
        """在两点之间创建道路"""
        x1, y1 = start
        x2, y2 = end

        # 使用DDA算法生成直线路径
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while x != x2 or y != y2:
            if 0 <= x < self.width and 0 <= y < self.height:
                # 道路类型
                if terrain[y, x] in [
                    TerrainType.RIVER.value,
                    TerrainType.LAKE.value,
                    TerrainType.SHALLOW_WATER.value,
                ]:
                    # 桥梁
                    terrain[y, x] = (
                        TerrainType.BRIDGE.value
                        if minor
                        else TerrainType.MAJOR_BRIDGE.value
                    )
                elif terrain[y, x] not in [
                    TerrainType.CITY.value,
                    TerrainType.VILLAGE.value,
                ]:
                    # 普通道路
                    terrain[y, x] = (
                        TerrainType.ROAD.value
                        if minor
                        else TerrainType.MAJOR_ROAD.value
                    )

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def _generate_settlements(self, terrain: np.ndarray, elevation: np.ndarray) -> None:
        """生成更自然的聚居地分布"""
        # 优化城市和村庄的分布逻辑
        pass

    def generate_map(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """生成完整地图，返回(海拔图, 地形图, 湿度图)"""
        elevation = self.generate_elevation_map()
        moisture = self.generate_moisture_map()
        terrain = self.generate_terrain_map(elevation, moisture)
        return elevation, terrain, moisture


# 初始化 Pygame
pygame.init()

# 设置窗口大小
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("地图生成器可视化")

# 加载或定义颜色映射
# 这里你需要定义TerrainType对应的RGB颜色值
TERRAIN_COLORS = {
    TerrainType.LAKE.value: (66, 139, 202),  # 道奇蓝
    TerrainType.DEEP_WATER.value: (0, 0, 255),  # 纯蓝
    TerrainType.SHALLOW_WATER.value: (135, 206, 235),  # 浅蓝
    TerrainType.PLAIN.value: (245, 245, 220),  # 象牙白
    TerrainType.GRASSLAND.value: (144, 238, 144),  # 淡绿色
    TerrainType.DECIDUOUS_FOREST.value: (34, 139, 34),  # 森林绿
    TerrainType.RAIN_FOREST.value: (0, 128, 0),  # 绿色
    TerrainType.MIXED_FOREST.value: (46, 139, 87),  # 墨绿色
    TerrainType.CONIFEROUS_FOREST.value: (0, 100, 0),  # 暗绿色
    TerrainType.HILL.value: (139, 111, 85),  # 褐色
    TerrainType.PLATEAU.value: (210, 180, 140),  # 棕色
    TerrainType.BASIN.value: (240, 230, 140),  # 米色
    TerrainType.MOUNTAIN.value: (139, 137, 137),  # 灰色
    TerrainType.xc.value: (222, 184, 135),  # 纳瓦霍白
    TerrainType.CITY.value: (192, 192, 192),  # 银色
    TerrainType.VILLAGE.value: (210, 180, 140),  # 棕色
    TerrainType.SUBURB.value: (169, 169, 169),  # 暗灰色
    TerrainType.ROAD.value: (105, 105, 105),  # 青灰色
    TerrainType.MAJOR_ROAD.value: (80, 80, 80),  # 深灰
    TerrainType.BRIDGE.value: (210, 180, 140),  # 棕色
    TerrainType.MAJOR_BRIDGE.value: (139, 69, 19),  # 鞍褐色
    TerrainType.RIVER.value: (0, 0, 255),  # 蓝色
}

# 创建地图生成器实例并生成地图
generator = MapGenerator(width=400, height=300, seed=42)
elevation_map, terrain_map, moisture_map = generator.generate_map()

# 确保地图尺寸符合窗口大小比例
scale_x = WINDOW_WIDTH / terrain_map.shape[1]
scale_y = WINDOW_HEIGHT / terrain_map.shape[0]
scale = min(scale_x, scale_y)

# 游戏主循环
running = True
clock = pygame.time.Clock()
pan_x = 0
pan_y = 0
zoom = 1.0

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 处理输入
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        pan_x += 10
    elif keys[pygame.K_RIGHT]:
        pan_x -= 10
    if keys[pygame.K_UP]:
        pan_y += 10
    elif keys[pygame.K_DOWN]:
        pan_y -= 10

    if keys[pygame.K_PLUS] or keys[pygame.K_EQUALS]:
        zoom += 0.1
    elif keys[pygame.K_MINUS] or keys[pygame.K_UNDERSCORE]:
        zoom -= 0.1 if zoom > 0.1 else 0

    # 绘制地图
    window.fill((0, 0, 0))  # 清空屏幕，填充黑色背景

    for y in range(terrain_map.shape[0]):
        for x in range(terrain_map.shape[1]):
            terrain_type = terrain_map[y, x]
            color = TERRAIN_COLORS.get(terrain_type, (255, 255, 255))  # 默认白色

            # 计算缩放和平移后的坐标
            screen_x = (x * scale * zoom) + pan_x
            screen_y = (y * scale * zoom) + pan_y

            # 绘制地形方块
            rect = pygame.Rect(screen_x, screen_y, scale * zoom, scale * zoom)
            pygame.draw.rect(window, color, rect)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
