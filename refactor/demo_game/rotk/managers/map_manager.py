import random
import math
from rotk.components import (
    MapComponent,
    TerrainType,
    # TERRAIN_MOVEMENT_COST,
    TERRAIN_COLORS,
)
from framework.managers.events import EventManager, Message
from framework.core.ecs.world import World


class MapManager:
    """地图管理器，负责地图生成和管理"""

    def __init__(self):
        """初始化地图管理器"""
        self.default_width = 50
        self.default_height = 50

        # 噪声生成器种子
        self.seed = random.randint(0, 10000)

        # 地形生成参数
        self.mountain_threshold = 0.70  # 山地高度阈值
        self.hill_threshold = 0.55  # 丘陵高度阈值
        self.forest_threshold = 0.45  # 森林区域阈值
        self.plains_threshold = 0.25  # 平原区域阈值
        self.water_threshold = 0.20  # 水域阈值
        self.deep_water_threshold = 0.15  # 深水阈值

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
    ) -> None:
        """初始化地图管理器"""
        self.event_manager = event_manager
        # 订阅地图生成事件
        self.event_manager.subscribe(
            "MAP_REGENERATED", lambda message: self.generate_map(world)
        )

    def create_map(self, world, width=None, height=None):
        """创建新地图"""
        width = width or self.default_width
        height = height or self.default_height

        # 创建地图实体
        map_entity = world.create_entity()
        world.add_component(map_entity, MapComponent(width=width, height=height))

        # 生成地图内容
        self.generate_map(world)

        # return self.map_entity

    def generate_map(self, world):
        """使用高级地形生成算法生成随机地图"""
        map_entity = world.get_entities_with_components(MapComponent)
        if not map_entity:
            return

        map_comp = world.get_component(map_entity[0], MapComponent)
        if not map_comp:
            return

        width, height = map_comp.width, map_comp.height

        # 调整地形阈值，使比例保持一致，无论地图大小如何
        self._adjust_thresholds(width, height)

        # 生成新种子
        self.seed = random.randint(0, 10000)

        # 步骤1: 生成高度图
        height_map = self._generate_height_map(width, height)

        # 步骤2: 生成湿度图
        moisture_map = self._generate_moisture_map(width, height)

        # 步骤3: 生成温度图
        temperature_map = self._generate_temperature_map(width, height)

        # 步骤4: 模拟水文系统
        river_map = self._simulate_hydrology(height_map, width, height)

        # 步骤5: 根据各种因素确定地形类型
        grid = [[TerrainType.PLAINS for _ in range(width)] for _ in range(height)]

        for y in range(height):
            for x in range(width):
                height_val = height_map[y][x]
                moisture_val = moisture_map[y][x]
                temp_val = temperature_map[y][x]

                # 河流优先
                if river_map[y][x]:
                    grid[y][x] = TerrainType.RIVER
                    continue

                # 根据高度决定基本地形
                if height_val > self.mountain_threshold:
                    grid[y][x] = TerrainType.MOUNTAIN
                elif height_val > self.hill_threshold:
                    grid[y][x] = TerrainType.HILL
                elif height_val > self.forest_threshold:
                    # 根据湿度决定是森林还是平原
                    if moisture_val > 0.5:
                        grid[y][x] = TerrainType.FOREST
                    else:
                        # 根据温度决定是平原还是沙漠
                        if temp_val > 0.7:
                            grid[y][x] = TerrainType.DESERT
                        else:
                            grid[y][x] = TerrainType.PLAINS
                elif height_val > self.plains_threshold:
                    # 低地，根据湿度决定是平原还是沼泽
                    if moisture_val > 0.6:
                        grid[y][x] = TerrainType.SWAMP
                    else:
                        # 根据温度决定是平原还是沙漠
                        if temp_val > 0.7:
                            grid[y][x] = TerrainType.DESERT
                        else:
                            grid[y][x] = TerrainType.PLAINS
                elif height_val > self.water_threshold:
                    grid[y][x] = TerrainType.COAST
                else:
                    # 水域
                    if height_val > self.deep_water_threshold:
                        grid[y][x] = TerrainType.LAKE
                    else:
                        grid[y][x] = TerrainType.OCEAN

        # 步骤6: 策略性地放置城市
        self._place_cities(grid, height_map, width, height)

        # 步骤7: 添加一些特殊地形特征（如桥梁）
        self._add_special_features(grid, river_map, height_map, width, height)

        # 更新地图
        map_comp.grid = grid

    def _adjust_thresholds(self, width, height):
        """根据地图大小动态调整阈值和参数"""
        # 基准尺寸为50x50
        base_size = 50
        self.scale_factor = math.sqrt((width * height) / (base_size * base_size))

        # 根据地图大小调整地形分布阈值
        if width < 30 or height < 30:  # 小地图
            # 小地图上减少水域和山地的比例，增加可用地形
            self.mountain_threshold = 0.75
            self.hill_threshold = 0.58
            self.forest_threshold = 0.45
            self.plains_threshold = 0.20
            self.water_threshold = 0.15
            self.deep_water_threshold = 0.10
        elif width > 80 or height > 80:  # 大地图
            # 大地图上增加地形多样性
            self.mountain_threshold = 0.68
            self.hill_threshold = 0.52
            self.forest_threshold = 0.42
            self.plains_threshold = 0.28
            self.water_threshold = 0.22
            self.deep_water_threshold = 0.18
        else:  # 中等地图
            # 默认参数
            self.mountain_threshold = 0.70
            self.hill_threshold = 0.55
            self.forest_threshold = 0.45
            self.plains_threshold = 0.25
            self.water_threshold = 0.20
            self.deep_water_threshold = 0.15

    def _generate_height_map(self, width, height):
        """生成地形高度图，使用动态缩放的参数"""
        # 初始化高度图
        height_map = [[0 for _ in range(width)] for _ in range(height)]

        # 地形生成参数 - 动态调整尺度
        octaves = min(8, max(4, int(math.log2(max(width, height)))))  # 根据地图大小调整
        persistence = 0.5
        lacunarity = 2.0

        # 关键变化：缩放因子随地图大小动态调整
        base_scale = 100.0
        map_scale = max(width, height) / 50.0  # 基于50x50的地图尺寸
        scale = base_scale * map_scale

        # 生成多层噪声
        for y in range(height):
            for x in range(width):
                amplitude = 1.0
                frequency = 1.0
                noise_value = 0.0

                # 叠加多层噪声
                for i in range(octaves):
                    # 计算样本点，使用动态缩放
                    sample_x = x / scale * frequency
                    sample_y = y / scale * frequency

                    # 生成噪声值 (-1 到 1)
                    noise_val = self._perlin_noise(sample_x, sample_y, self.seed + i)

                    # 累加噪声
                    noise_value += noise_val * amplitude

                    # 调整下一层参数
                    amplitude *= persistence
                    frequency *= lacunarity

                # 归一化到 0-1
                noise_value = (noise_value + 1) / 2.0

                # # 重新启用边缘平滑，使地图边缘更可能是水
                # # 边缘宽度随地图尺寸调整
                # border_width = max(2, int(min(width, height) / 10))
                # distance_to_edge = (
                #     min(x, y, width - x - 1, height - y - 1) / border_width
                # )
                # edge_factor = min(1.0, distance_to_edge)

                # # 调整高度，乘以边缘因子使边缘更低
                # noise_value = noise_value * edge_factor

                # 存储高度值
                height_map[y][x] = noise_value

        return height_map

    def _generate_moisture_map(self, width, height):
        """生成湿度图，使用动态缩放的参数"""
        # 初始化湿度图
        moisture_map = [[0 for _ in range(width)] for _ in range(height)]

        # 湿度生成参数 - 动态调整尺度
        base_scale = 150.0
        map_scale = max(width, height) / 50.0
        scale = base_scale * map_scale
        seed_offset = 1000

        # 生成湿度噪声
        for y in range(height):
            for x in range(width):
                # 使用Perlin噪声生成随机湿度
                sample_x = x / scale
                sample_y = y / scale
                moisture = self._perlin_noise(
                    sample_x, sample_y, self.seed + seed_offset
                )

                # 归一化到 0-1
                moisture = (moisture + 1) / 2.0

                moisture_map[y][x] = moisture

        return moisture_map

    def _generate_temperature_map(self, width, height):
        """生成温度图，使用动态缩放的参数"""
        # 初始化温度图
        temperature_map = [[0 for _ in range(width)] for _ in range(height)]

        # 温度生成参数 - 动态调整尺度
        base_scale = 200.0
        map_scale = max(width, height) / 50.0
        scale = base_scale * map_scale
        seed_offset = 2000

        # 温度倾向于从北到南递增，再加入一些随机变化
        for y in range(height):
            for x in range(width):
                # 基础温度：从北到南递增
                base_temp = y / height

                # 使用Perlin噪声添加随机变化
                sample_x = x / scale
                sample_y = y / scale
                noise = self._perlin_noise(sample_x, sample_y, self.seed + seed_offset)

                # 噪声范围从-1到1，将其缩小到-0.3到0.3，再与base_temp相加
                temp_variation = noise * 0.3
                temperature = base_temp + temp_variation

                # 确保值在0-1范围内
                temperature = max(0.0, min(1.0, temperature))

                temperature_map[y][x] = temperature

        return temperature_map

    def _simulate_hydrology(self, height_map, width, height):
        """模拟水文系统，使用动态缩放的参数"""
        # 初始化河流图
        river_map = [[False for _ in range(width)] for _ in range(height)]

        # 河流数量 - 动态计算
        # 使用地图面积的平方根来计算河流数量，确保大地图有更多河流，但不会过多
        base_rivers = 5  # 基础河流数
        scale_rivers = math.sqrt(width * height) / 7  # 随地图大小动态增加
        num_rivers = max(1, int(base_rivers + scale_rivers))

        # 生成河流
        for _ in range(num_rivers):
            # 寻找适合的河流源头 (较高的点)
            candidate_sources = []
            for y in range(height):
                for x in range(width):
                    if height_map[y][x] > self.hill_threshold and not river_map[y][x]:
                        candidate_sources.append((x, y))

            if not candidate_sources:
                continue

            # 随机选择一个源头
            source_x, source_y = random.choice(candidate_sources)

            # 从源头开始，根据高度图流向低处
            x, y = source_x, source_y
            river_length = 0
            max_length = width * 2  # 限制最大长度，防止无限循环

            while 0 <= x < width and 0 <= y < height and river_length < max_length:
                river_map[y][x] = True
                river_length += 1

                # 寻找周围最低点
                lowest_height = height_map[y][x]
                next_x, next_y = x, y

                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            if height_map[ny][nx] < lowest_height:
                                lowest_height = height_map[ny][nx]
                                next_x, next_y = nx, ny

                # 如果找不到更低的点，结束此河流
                if next_x == x and next_y == y:
                    break

                # 移动到下一个点
                x, y = next_x, next_y

        # 平滑河流，填补可能的间隙
        self._smooth_rivers(river_map, width, height)

        return river_map

    def _smooth_rivers(self, river_map, width, height):
        """平滑河流，填补间隙"""
        # 复制一份河流图
        smoothed = [[river_map[y][x] for x in range(width)] for y in range(height)]

        # 填补间隙
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                # 如果当前点不是河流
                if not river_map[y][x]:
                    # 检查周围有多少河流点
                    river_neighbors = 0
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = x + dx, y + dy
                            if river_map[ny][nx]:
                                river_neighbors += 1

                    # 如果周围有足够的河流点，将此点也标为河流
                    if river_neighbors >= 4:  # 阈值可调整
                        smoothed[y][x] = True

        # 更新河流图
        for y in range(height):
            for x in range(width):
                river_map[y][x] = smoothed[y][x]

    def _place_cities(self, grid, height_map, width, height):
        """策略性地放置城市，使用动态缩放的参数"""
        # 城市数量 - 动态计算
        # 使用地图面积的平方根并加上固定值，确保即使在小地图上也至少有一些城市
        base_cities = 2  # 基础城市数
        scale_cities = math.sqrt(width * height) / 10  # 随地图大小动态增加
        num_cities = max(1, int(base_cities + scale_cities))

        # 城市间最小距离也应该随地图大小调整
        min_city_distance = max(3, int(min(width, height) / 8))

        # 候选位置评分
        city_scores = {}

        for y in range(height):
            for x in range(width):
                # 只考虑平原和丘陵
                if grid[y][x] not in [TerrainType.PLAINS, TerrainType.HILL]:
                    continue

                score = 0

                # 靠近水源得分高
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            if grid[ny][nx] in [
                                TerrainType.RIVER,
                                TerrainType.LAKE,
                                TerrainType.COAST,
                            ]:
                                dist = max(abs(dx), abs(dy))
                                if dist == 1:
                                    score += 5  # 直接相邻
                                else:
                                    score += 5 / dist  # 距离越远，分数越低

                # 避免太靠近其他城市
                for dx in range(-min_city_distance, min_city_distance + 1):
                    for dy in range(-min_city_distance, min_city_distance + 1):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            if grid[ny][nx] == TerrainType.CITY:
                                score -= 20  # 强烈惩罚靠近其他城市

                # 平原比丘陵更适合建城
                if grid[y][x] == TerrainType.PLAINS:
                    score += 2

                # 只记录正分数的位置
                if score > 0:
                    city_scores[(x, y)] = score

        # 根据分数选择城市位置
        sorted_locations = sorted(
            city_scores.keys(), key=lambda loc: city_scores[loc], reverse=True
        )

        # 放置城市
        cities_placed = 0
        for x, y in sorted_locations:
            if cities_placed >= num_cities:
                break

            grid[y][x] = TerrainType.CITY
            cities_placed += 1

            # 更新周围位置的分数，避免城市过于集中
            for dx in range(-5, 6):
                for dy in range(-5, 6):
                    nx, ny = x + dx, y + dy
                    if (nx, ny) in city_scores:
                        city_scores[(nx, ny)] -= 10

    def _add_special_features(self, grid, river_map, height_map, width, height):
        """添加特殊地形特征，如桥梁、峡谷等"""

        # 在河流上添加桥梁
        self._add_bridges(grid, river_map, width, height)

        # 生成一些峡谷
        self._add_valleys(grid, height_map, width, height)

        # 生成一些高原
        self._add_plateaus(grid, height_map, width, height)

    def _add_bridges(self, grid, river_map, width, height):
        """在河流上添加桥梁连接"""
        # 检查每一个河流点
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if grid[y][x] == TerrainType.RIVER:
                    # 检查是否是横向的河流
                    is_horizontal = (
                        grid[y][x - 1] == TerrainType.RIVER
                        and grid[y][x + 1] == TerrainType.RIVER
                    )

                    # 检查是否是纵向的河流
                    is_vertical = (
                        grid[y - 1][x] == TerrainType.RIVER
                        and grid[y + 1][x] == TerrainType.RIVER
                    )

                    # 如果不是笔直的河流，跳过
                    if not is_horizontal and not is_vertical:
                        continue

                    # 检查两侧是否是陆地
                    if is_horizontal:
                        if (
                            self._is_land(grid[y - 1][x])
                            and self._is_land(grid[y + 1][x])
                            and random.random() < 0.2
                        ):  # 20%概率放置桥梁
                            grid[y][x] = TerrainType.BRIDGE

                    if is_vertical:
                        if (
                            self._is_land(grid[y][x - 1])
                            and self._is_land(grid[y][x + 1])
                            and random.random() < 0.2
                        ):  # 20%概率放置桥梁
                            grid[y][x] = TerrainType.BRIDGE

    def _add_valleys(self, grid, height_map, width, height):
        """添加山谷，使用动态缩放的参数"""
        # 山谷数量 - 动态计算
        num_valleys = max(1, int(math.sqrt(width * height) / 8))

        # 山谷大小也应随地图尺寸调整
        min_valley_size = max(2, int(min(width, height) / 15))
        max_valley_size = max(min_valley_size + 1, int(min(width, height) / 8))

        for _ in range(num_valleys):
            # 寻找山地或丘陵区域
            candidates = []
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    if grid[y][x] in [TerrainType.MOUNTAIN, TerrainType.HILL]:
                        # 检查周围是否也是山地或丘陵
                        mountain_neighbors = 0
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                nx, ny = x + dx, y + dy
                                if grid[ny][nx] in [
                                    TerrainType.MOUNTAIN,
                                    TerrainType.HILL,
                                ]:
                                    mountain_neighbors += 1

                        if mountain_neighbors >= 6:  # 周围大部分是山地
                            candidates.append((x, y))

            if not candidates:
                continue

            # 选择一个位置作为山谷起点
            x, y = random.choice(candidates)

            # 创建一个小山谷，尺寸随地图大小变化
            valley_size = random.randint(min_valley_size, max_valley_size)
            for dx in range(-valley_size, valley_size + 1):
                for dy in range(-valley_size, valley_size + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        # 山谷形状为椭圆
                        if (dx * dx + dy * dy * 2) <= valley_size * valley_size:
                            if grid[ny][nx] in [TerrainType.MOUNTAIN, TerrainType.HILL]:
                                grid[ny][nx] = TerrainType.VALLEY

    def _add_plateaus(self, grid, height_map, width, height):
        """添加高原，使用动态缩放的参数"""
        # 高原数量 - 动态计算
        num_plateaus = max(1, int(math.sqrt(width * height) / 10))

        # 高原大小也应随地图尺寸调整
        min_plateau_size = max(2, int(min(width, height) / 15))
        max_plateau_size = max(min_plateau_size + 1, int(min(width, height) / 8))

        for _ in range(num_plateaus):
            # 寻找较高但不是最高的区域
            candidates = []
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    if (
                        height_map[y][x] > self.hill_threshold
                        and height_map[y][x] < self.mountain_threshold
                    ):
                        candidates.append((x, y))

            if not candidates:
                continue

            # 选择一个位置作为高原中心
            x, y = random.choice(candidates)

            # 创建高原，尺寸随地图大小变化
            plateau_size = random.randint(min_plateau_size, max_plateau_size)
            for dx in range(-plateau_size, plateau_size + 1):
                for dy in range(-plateau_size, plateau_size + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        # 高原形状为平滑的椭圆
                        dist = math.sqrt(dx * dx + dy * dy)
                        if dist <= plateau_size:
                            # 边缘渐变
                            if dist > plateau_size - 2:
                                if random.random() < 0.5:
                                    grid[ny][nx] = TerrainType.PLATEAU
                            else:
                                grid[ny][nx] = TerrainType.PLATEAU

    def _is_land(self, terrain_type):
        """检查地形是否是陆地"""
        return terrain_type not in [
            TerrainType.RIVER,
            TerrainType.LAKE,
            TerrainType.OCEAN,
        ]

    def _perlin_noise(self, x, y, seed):
        """简化版Perlin噪声实现"""
        # 确定单元格坐标
        x0 = int(x) & 255
        y0 = int(y) & 255

        # 计算单元格内的相对位置
        x -= int(x)
        y -= int(y)

        # 计算淡化曲线
        u = self._fade(x)
        v = self._fade(y)

        # 获取单元格角落的伪随机梯度向量
        a = self._generate_hash(x0, y0, seed)
        b = self._generate_hash(x0 + 1, y0, seed)
        c = self._generate_hash(x0, y0 + 1, seed)
        d = self._generate_hash(x0 + 1, y0 + 1, seed)

        # 计算梯度向量与到各角落的位移向量的点积
        g_a = self._gradient(a, x, y)
        g_b = self._gradient(b, x - 1, y)
        g_c = self._gradient(c, x, y - 1)
        g_d = self._gradient(d, x - 1, y - 1)

        # 插值计算最终噪声值
        x1 = self._lerp(g_a, g_b, u)
        x2 = self._lerp(g_c, g_d, u)
        return self._lerp(x1, x2, v)

    def _fade(self, t):
        """淡化函数，使插值更平滑"""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a, b, t):
        """线性插值"""
        return a + t * (b - a)

    def _generate_hash(self, x, y, seed):
        """生成伪随机哈希值"""
        return ((x + seed) * 13 + (y + seed) * 7) & 255

    def _gradient(self, hash_val, x, y):
        """从哈希值计算梯度向量与位移向量的点积"""
        h = hash_val & 7  # 取最低3位，共8种可能的梯度向量

        # 梯度向量表的简化版
        grad_x = [1, 1, 0, -1, -1, -1, 0, 1]
        grad_y = [0, 1, 1, 1, 0, -1, -1, -1]

        # 计算点积
        return grad_x[h] * x + grad_y[h] * y

    def regenerate_map(self, world):
        """重新生成地图"""
        # 确保保留map_entity
        map_entity = self.map_entity

        # 获取当前地图组件
        map_comp = world.get_component(map_entity, MapComponent)
        if not map_comp:
            return

        # 保存尺寸信息
        width, height = map_comp.width, map_comp.height

        # 清空实体位置字典但保留地图实体
        map_comp.entities_positions = {}

        # 重新生成地图内容
        self.generate_map(world)

        # 发送地图重生成事件
        if hasattr(world, "event_manager"):
            world.event_manager.publish(
                "MAP_REGENERATED",
                Message(
                    topic="MAP_REGENERATED",
                    data_type="map_event",
                    data={"map_entity": map_entity},
                ),
            )

    def get_movement_cost(self, terrain_type):
        """获取指定地形的移动消耗"""
        return TERRAIN_MOVEMENT_COST.get(terrain_type, 1)

    def get_terrain_color(self, terrain_type):
        """获取指定地形的颜色"""
        return TERRAIN_COLORS.get(terrain_type, (100, 100, 100))

    def find_walkable_position(self, world):
        """在地图上找一个可行走的位置"""
        map_comp = world.get_component(self.map_entity, MapComponent)
        if not map_comp:
            return 0, 0

        width, height = map_comp.width, map_comp.height
        grid = map_comp.grid

        # 尝试10次找到一个合适的位置
        for _ in range(10):
            x, y = random.randint(0, width - 1), random.randint(0, height - 1)
            # 检查是否是可行走的地形
            if y < len(grid) and x < len(grid[y]):
                terrain_type = grid[y][x]
                if terrain_type in [
                    TerrainType.PLAINS,
                    TerrainType.FOREST,
                    TerrainType.HILL,
                ]:
                    # 检查该位置是否已经被其他实体占用
                    if (x, y) not in map_comp.entities_positions.values():
                        return x, y

        # 如果找不到，返回默认值
        return 0, 0

    # def is_position_valid(self, world, x, y):
    #     """检查位置是否在地图范围内且可通行"""
    #     map_comp = world.get_component(self.map_entity, MapComponent)
    #     if not map_comp:
    #         return False

    #     # 检查边界
    #     if x < 0 or x >= map_comp.width or y < 0 or y >= map_comp.height:
    #         return False

    #     # 检查地形是否可通行
    #     terrain_type = map_comp.grid[y][x]
    #     if terrain_type in [TerrainType.OCEAN]:  # 海洋不可通行
    #         return False

    #     return True

    def get_terrain_at(self, world, x, y):
        """获取指定位置的地形类型"""
        map_comp = world.get_component(self.map_entity, MapComponent)
        if (
            not map_comp
            or x < 0
            or y < 0
            or x >= map_comp.width
            or y >= map_comp.height
        ):
            return None
        return map_comp.grid[y][x]
