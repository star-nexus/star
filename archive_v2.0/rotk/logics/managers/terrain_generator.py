import random
import math
from rotk.logics.components import (
    MapComponent,
    TerrainType,
)


class TerrainGenerator:
    """地形生成器，负责生成基本地形"""

    def __init__(self):
        """初始化地形生成器"""
        # 噪声生成器种子
        self.seed = random.randint(0, 10000)

        # 地形生成参数
        self.mountain_threshold = 0.70  # 山地高度阈值
        self.hill_threshold = 0.55  # 丘陵高度阈值
        self.forest_threshold = 0.45  # 森林区域阈值
        self.plains_threshold = 0.25  # 平原区域阈值
        self.water_threshold = 0.20  # 水域阈值

        # 河流生成参数
        self.river_count = 3
        self.river_threshold = 0.06
        self.river_min_length = 5
        
    def generate_terrain(self, width, height):
        """生成地形数据
        
        Args:
            width: 地图宽度
            height: 地图高度
            
        Returns:
            tuple: (grid, height_map, moisture_map, river_map)
        """
        # 调整阈值参数
        self._adjust_thresholds(width, height)
        
        # 生成高度图
        height_map = self._generate_height_map(width, height)
        
        # 生成湿度图
        moisture_map = self._generate_moisture_map(width, height)
        
        # 生成温度图
        temperature_map = self._generate_temperature_map(width, height)
        
        # 模拟水文（河流）
        river_map = self._simulate_hydrology(height_map, width, height)
        
        # 平滑河流
        river_map = self._smooth_rivers(river_map, width, height)
        
        # 初始化地形网格
        grid = [[TerrainType.PLAIN for _ in range(width)] for _ in range(height)]
        
        # 根据高度图、湿度图和温度图决定地形类型
        for y in range(height):
            for x in range(width):
                height_val = height_map[y][x]
                moisture_val = moisture_map[y][x]
                
                # 确定基本地形
                if height_val > self.mountain_threshold:
                    grid[y][x] = TerrainType.MOUNTAIN
                elif height_val > self.hill_threshold:
                    grid[y][x] = TerrainType.HILL
                elif height_val > self.forest_threshold and moisture_val > 0.4:
                    grid[y][x] = TerrainType.FOREST
                elif height_val > self.plains_threshold:
                    grid[y][x] = TerrainType.PLAIN
                elif height_val > self.water_threshold:
                    grid[y][x] = TerrainType.SWAMP if moisture_val > 0.6 else TerrainType.PLAIN
                else:
                    if moisture_val > 0.7:
                        grid[y][x] = TerrainType.LAKE
                    else:
                        grid[y][x] = TerrainType.RIVER
                
                # 处理河流
                if river_map[y][x] > 0:
                    grid[y][x] = TerrainType.RIVER
                
        return grid, height_map, moisture_map, river_map
    
    def _adjust_thresholds(self, width, height):
        """根据地图大小调整地形生成阈值"""
        # 调整河流数量和阈值
        map_size = width * height
        self.river_count = max(1, int(map_size / 2500))
        
        # 为较小的地图适当调整阈值
        if map_size < 2500:
            self.mountain_threshold += 0.05
            self.hill_threshold += 0.05
            self.water_threshold -= 0.05
        
        # 为较大的地图调整阈值，确保地形分布合理
        if map_size > 10000:
            self.mountain_threshold -= 0.03
            self.forest_threshold -= 0.02
    
    def _generate_height_map(self, width, height):
        """生成地形高度图
        
        使用多层Perlin噪声生成自然的高度变化
        """
        height_map = [[0 for _ in range(width)] for _ in range(height)]
        
        # 使用多层噪声生成逼真的地形
        octaves = 6
        persistence = 0.5
        lacunarity = 2.0
        
        for y in range(height):
            for x in range(width):
                amplitude = 1.0
                frequency = 1.0
                height_value = 0.0
                
                # 多层噪声叠加
                for i in range(octaves):
                    nx = x / width * frequency
                    ny = y / height * frequency
                    
                    # 添加扭曲以打破规则性
                    if i > 0:
                        nx += self._perlin_noise(x / width * 3, y / height * 3, self.seed + 123) * 0.2
                        ny += self._perlin_noise(x / width * 3, y / height * 3, self.seed + 321) * 0.2
                    
                    noise_value = self._perlin_noise(nx, ny, self.seed + i * 1000)
                    height_value += noise_value * amplitude
                    
                    amplitude *= persistence
                    frequency *= lacunarity
                
                # 标准化并应用变形
                height_value = (height_value + 1) / 2.0
                
                # 添加边缘渐变，使地图边缘倾向于水域
                edge_distance = min(
                    x / (width * 0.2),
                    (width - x) / (width * 0.2),
                    y / (height * 0.2),
                    (height - y) / (height * 0.2)
                )
                edge_factor = min(1.0, edge_distance)
                height_value *= edge_factor
                
                height_map[y][x] = height_value
                
        return height_map
    
    def _generate_moisture_map(self, width, height):
        """生成湿度图，用于决定植被和水域"""
        moisture_map = [[0 for _ in range(width)] for _ in range(height)]
        
        # 使用不同的种子以确保与高度图有差异
        moisture_seed = self.seed + 12345
        
        for y in range(height):
            for x in range(width):
                # 基础湿度基于Perlin噪声
                base_moisture = self._perlin_noise(x / width * 3, y / height * 3, moisture_seed)
                
                # 标准化到0-1范围
                moisture = (base_moisture + 1) / 2.0
                
                # 纬度效应 - 向地图中部增加湿度
                latitude_factor = 1.0 - 2.0 * abs(y / height - 0.5)
                moisture = (moisture + latitude_factor) / 2.0
                
                moisture_map[y][x] = max(0.0, min(1.0, moisture))
                
        return moisture_map
    
    def _generate_temperature_map(self, width, height):
        """生成温度图，用于影响生物群落分布"""
        temperature_map = [[0 for _ in range(width)] for _ in range(height)]
        
        # 使用另一个种子
        temp_seed = self.seed + 54321
        
        for y in range(height):
            for x in range(width):
                # 基础温度基于Perlin噪声
                base_temp = self._perlin_noise(x / width * 2, y / height * 2, temp_seed)
                
                # 纬度效应 - 中部温暖，边缘凉爽
                latitude_factor = 1.0 - 2.0 * abs(y / height - 0.5)
                
                # 合并噪声和纬度效应
                temperature = (base_temp + 1) / 2.0
                temperature = temperature * 0.4 + latitude_factor * 0.6
                
                temperature_map[y][x] = max(0.0, min(1.0, temperature))
                
        return temperature_map
    
    def _simulate_hydrology(self, height_map, width, height):
        """模拟水文系统，生成逼真的河流"""
        river_map = [[0 for _ in range(width)] for _ in range(height)]
        
        # 河流源头候选位置
        potential_sources = []
        
        # 寻找可能的河流源头（山地或丘陵）
        for y in range(height):
            for x in range(width):
                if height_map[y][x] > self.hill_threshold:
                    potential_sources.append((x, y))
                    
        # 如果没有足够的山地或丘陵，则使用随机位置
        if len(potential_sources) < self.river_count:
            while len(potential_sources) < self.river_count:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                if (x, y) not in potential_sources:
                    potential_sources.append((x, y))
                    
        # 随机选择河流源头
        random.shuffle(potential_sources)
        sources = potential_sources[:self.river_count]
        
        # 从每个源头生成河流
        for source_x, source_y in sources:
            self._generate_river(source_x, source_y, height_map, river_map, width, height)
            
        return river_map
    
    def _generate_river(self, x, y, height_map, river_map, width, height):
        """从给定位置生成一条河流，沿着高度梯度流向"""
        # 河流当前位置
        current_x, current_y = x, y
        
        # 已经流过的位置
        path = [(current_x, current_y)]
        
        # 河流长度计数
        length = 0
        
        # 继续流动直到达到地图边缘或者最大长度
        while (0 < current_x < width - 1 and 0 < current_y < height - 1 
               and length < width + height):
            river_map[current_y][current_x] = 1
            
            # 计算周围8个方向的高度
            neighbors = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                        
                    nx, ny = current_x + dx, current_y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbors.append((nx, ny, height_map[ny][nx]))
                        
            # 按高度排序
            neighbors.sort(key=lambda n: n[2])
            
            # 选择高度最低的邻居（沿着高度梯度流动）
            found_next = False
            for nx, ny, _ in neighbors:
                if (nx, ny) not in path:  # 避免循环
                    current_x, current_y = nx, ny
                    path.append((current_x, current_y))
                    found_next = True
                    break
                    
            if not found_next:
                break  # 无法继续流动
                
            length += 1
            
        # 如果河流太短，则移除
        if length < self.river_min_length:
            for x, y in path:
                river_map[y][x] = 0
                
    def _smooth_rivers(self, river_map, width, height):
        """平滑河流以使其更逼真"""
        smoothed_map = [[0 for _ in range(width)] for _ in range(height)]
        
        # 复制原始河流图
        for y in range(height):
            for x in range(width):
                smoothed_map[y][x] = river_map[y][x]
                
        # 找到所有河流格
        river_cells = []
        for y in range(height):
            for x in range(width):
                if river_map[y][x] > 0:
                    river_cells.append((x, y))
                    
        # 连接孤立的河流格
        for x, y in river_cells:
            river_neighbors = 0
            
            # 检查四个相邻格
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and river_map[ny][nx] > 0:
                    river_neighbors += 1
                    
            # 如果这个格只有一个河流相邻，则尝试添加另一个相邻格使其连续
            if river_neighbors == 1:
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    
                    # 只考虑地图内的格子
                    if 0 <= nx < width and 0 <= ny < height:
                        # 如果这个相邻格不是河流，考虑将其变为河流
                        if river_map[ny][nx] == 0:
                            # 检查这个新格是否能连接到另一个河流格
                            for d2x, d2y in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                                n2x, n2y = nx + d2x, ny + d2y
                                
                                if 0 <= n2x < width and 0 <= n2y < height:
                                    if (n2x, n2y) != (x, y) and river_map[n2y][n2x] > 0:
                                        smoothed_map[ny][nx] = 1
                                        break
                                        
        return smoothed_map
    
    def _perlin_noise(self, x, y, seed):
        """生成Perlin噪声"""
        # 获取单元格坐标和范围内的位置
        x_floor = math.floor(x)
        y_floor = math.floor(y)
        
        x_frac = x - x_floor
        y_frac = y - y_floor
        
        # 淡化函数使结果更自然
        x_faded = self._fade(x_frac)
        y_faded = self._fade(y_frac)
        
        # 获取四个顶点的hash值
        p00 = self._generate_hash(x_floor, y_floor, seed)
        p01 = self._generate_hash(x_floor, y_floor + 1, seed)
        p10 = self._generate_hash(x_floor + 1, y_floor, seed)
        p11 = self._generate_hash(x_floor + 1, y_floor + 1, seed)
        
        # 计算每个顶点的梯度
        g00 = self._gradient(p00, x_frac, y_frac)
        g01 = self._gradient(p01, x_frac, y_frac - 1)
        g10 = self._gradient(p10, x_frac - 1, y_frac)
        g11 = self._gradient(p11, x_frac - 1, y_frac - 1)
        
        # 双线性插值得到最终噪声值
        u = self._lerp(g00, g10, x_faded)
        v = self._lerp(g01, g11, x_faded)
        
        return self._lerp(u, v, y_faded)
        
    def _fade(self, t):
        """淡化函数，使噪声更平滑"""
        return t * t * t * (t * (t * 6 - 15) + 10)
        
    def _lerp(self, a, b, t):
        """线性插值"""
        return a + t * (b - a)
        
    def _generate_hash(self, x, y, seed):
        """生成一个伪随机哈希值"""
        return (x * 1619 + y * 31337 + seed) % 256
        
    def _gradient(self, hash_val, x, y):
        """根据哈希值生成梯度向量并计算点积"""
        # 从哈希值获取一个方向
        h = hash_val & 7
        
        # 梯度向量查找表
        gradients = [
            (1, 1), (-1, 1), (1, -1), (-1, -1),
            (1, 0), (-1, 0), (0, 1), (0, -1)
        ]
        
        grad_x, grad_y = gradients[h]
        
        # 计算点积
        return grad_x * x + grad_y * y 