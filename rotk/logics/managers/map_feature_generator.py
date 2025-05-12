import random
from rotk.logics.components import TerrainType


class MapFeatureGenerator:
    """地图特殊特征生成器，负责生成城市、桥梁、高原等特殊地形"""

    def __init__(self):
        """初始化地图特征生成器"""
        # 特征生成参数
        self.city_density = 0.02  # 城市密度
        self.min_city_distance = 8  # 城市间最小距离
        self.bridge_probability = 0.3  # 桥梁生成概率
        self.valley_count = 3  # 山谷数量
        self.plateau_count = 2  # 高原数量

    def add_cities(self, grid, height_map, width, height):
        """在地图上添加城市
        
        Args:
            grid: 地形网格
            height_map: 高度图
            width: 地图宽度
            height: 地图高度
            
        Returns:
            list: 城市位置列表[(x, y), ...]
        """
        # 估计城市数量
        map_size = width * height
        max_cities = max(1, int(map_size * self.city_density))
        
        # 存储已放置的城市
        cities = []
        
        # 为城市寻找合适的位置
        attempts = 0
        max_attempts = max_cities * 10  # 限制尝试次数，避免无限循环
        
        while len(cities) < max_cities and attempts < max_attempts:
            attempts += 1
            
            # 随机选择一个位置
            x = random.randint(2, width - 3)
            y = random.randint(2, height - 3)
            
            # 检查位置是否合适
            if self._is_suitable_for_city(x, y, grid, height_map, cities, width, height):
                # 放置城市及其周边区域
                self._place_city(x, y, grid)
                cities.append((x, y))
                
        return cities
        
    def _is_suitable_for_city(self, x, y, grid, height_map, cities, width, height):
        """检查位置是否适合城市"""
        # 检查是否是可通行地形
        if not self._is_passable_terrain(grid[y][x]):
            return False
            
        # 检查高度适合性 - 城市通常不建在高山或水域
        if height_map[y][x] > 0.7 or height_map[y][x] < 0.25:
            return False
            
        # 检查与其他城市的距离
        for city_x, city_y in cities:
            dist = ((x - city_x) ** 2 + (y - city_y) ** 2) ** 0.5
            if dist < self.min_city_distance:
                return False
                
        # 检查周边区域是否足够平坦
        surrounding_suitable = True
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                
                # 检查边界
                if not (0 <= nx < width and 0 <= ny < height):
                    surrounding_suitable = False
                    break
                    
                # 检查地形
                if not self._is_city_compatible_terrain(grid[ny][nx]):
                    surrounding_suitable = False
                    break
                    
                # 检查相邻格子的高度差异
                if abs(height_map[ny][nx] - height_map[y][x]) > 0.1:
                    surrounding_suitable = False
                    break
                    
            if not surrounding_suitable:
                break
                
        return surrounding_suitable
                
    def _place_city(self, center_x, center_y, grid):
        """在地图上放置城市及其周边建筑"""
        # 中心点放置城市
        grid[center_y][center_x] = TerrainType.URBAN
        
        # 在周围1格范围内随机放置城市延伸
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                # 跳过中心点
                if dx == 0 and dy == 0:
                    continue
                    
                # 80%概率延伸城市
                if random.random() < 0.8:
                    nx, ny = center_x + dx, center_y + dy
                    if 0 <= nx < len(grid[0]) and 0 <= ny < len(grid):
                        grid[ny][nx] = TerrainType.URBAN
                        
    def add_bridges(self, grid, river_map, width, height):
        """在河流上添加桥梁
        
        Args:
            grid: 地形网格
            river_map: 河流图
            width: 地图宽度
            height: 地图高度
        """
        # 查找可能的桥梁位置 - 河流与陆地的交界处
        bridge_candidates = []
        
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                # 只考虑河流单元格
                if grid[y][x] == TerrainType.RIVER:
                    # 检查相邻的陆地单元格
                    land_neighbors = []
                    
                    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nx, ny = x + dx, y + dy
                        
                        if 0 <= nx < width and 0 <= ny < height:
                            if self._is_land(grid[ny][nx]):
                                land_neighbors.append((nx, ny))
                                
                    # 如果有两个相对的陆地邻居，这里适合建桥
                    if len(land_neighbors) >= 2:
                        horizontal_bridge = False
                        vertical_bridge = False
                        
                        # 检查是否有水平对应的陆地
                        if (x-1, y) in land_neighbors and (x+1, y) in land_neighbors:
                            horizontal_bridge = True
                            
                        # 检查是否有垂直对应的陆地
                        if (x, y-1) in land_neighbors and (x, y+1) in land_neighbors:
                            vertical_bridge = True
                            
                        if horizontal_bridge or vertical_bridge:
                            bridge_candidates.append((x, y, horizontal_bridge))
        
        # 随机选择一些候选位置建桥
        random.shuffle(bridge_candidates)
        bridge_count = min(len(bridge_candidates), 
                          max(1, int(len(bridge_candidates) * self.bridge_probability)))
        
        for i in range(bridge_count):
            x, y, is_horizontal = bridge_candidates[i]
            grid[y][x] = TerrainType.BRIDGE
            
    def add_valleys(self, grid, height_map, width, height):
        """添加山谷特征
        
        Args:
            grid: 地形网格
            height_map: 高度图
            width: 地图宽度
            height: 地图高度
        """
        # 查找山区
        mountain_areas = []
        
        for y in range(2, height - 2):
            for x in range(2, width - 2):
                if grid[y][x] == TerrainType.MOUNTAIN:
                    # 检查周围是否都是山地
                    surrounding_mountains = True
                    
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            nx, ny = x + dx, y + dy
                            if grid[ny][nx] != TerrainType.MOUNTAIN:
                                surrounding_mountains = False
                                break
                                
                        if not surrounding_mountains:
                            break
                            
                    if surrounding_mountains:
                        mountain_areas.append((x, y))
        
        # 如果没有足够的山区，直接返回
        if len(mountain_areas) < self.valley_count:
            return
            
        # 随机选择一些山区作为山谷起点
        random.shuffle(mountain_areas)
        valley_starts = mountain_areas[:self.valley_count]
        
        # 从每个起点创建一条山谷路径
        for start_x, start_y in valley_starts:
            # 随机选择一个方向
            direction = random.choice([(0, 1), (1, 0), (0, -1), (-1, 0)])
            dx, dy = direction
            
            # 山谷长度
            valley_length = random.randint(3, 7)
            
            # 创建山谷路径
            current_x, current_y = start_x, start_y
            for _ in range(valley_length):
                # 放置山谷
                grid[current_y][current_x] = TerrainType.VALLEY
                
                # 在山谷两侧也设置一些山谷地形
                if dx != 0:  # 水平山谷
                    if 0 <= current_y - 1 < height:
                        grid[current_y - 1][current_x] = TerrainType.VALLEY
                    if 0 <= current_y + 1 < height:
                        grid[current_y + 1][current_x] = TerrainType.VALLEY
                        
                if dy != 0:  # 垂直山谷
                    if 0 <= current_x - 1 < width:
                        grid[current_y][current_x - 1] = TerrainType.VALLEY
                    if 0 <= current_x + 1 < width:
                        grid[current_y][current_x + 1] = TerrainType.VALLEY
                
                # 移动到下一个位置
                current_x += dx
                current_y += dy
                
                # 检查边界
                if not (0 <= current_x < width and 0 <= current_y < height):
                    break
                    
    def add_plateaus(self, grid, height_map, width, height):
        """添加高原特征
        
        Args:
            grid: 地形网格
            height_map: 高度图
            width: 地图宽度
            height: 地图高度
        """
        # 查找可能的高原位置 - 较高的丘陵区域
        plateau_candidates = []
        
        for y in range(3, height - 3):
            for x in range(3, width - 3):
                if grid[y][x] == TerrainType.HILL and height_map[y][x] > 0.6:
                    # 检查周围是否有足够大的平坦区域
                    flat_area = True
                    avg_height = height_map[y][x]
                    count = 1
                    
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            nx, ny = x + dx, y + dy
                            # 确保在地图内
                            if 0 <= nx < width and 0 <= ny < height:
                                # 计算平均高度
                                avg_height += height_map[ny][nx]
                                count += 1
                                
                                # 确保是丘陵或平原
                                if grid[ny][nx] not in [TerrainType.HILL, TerrainType.PLAIN]:
                                    flat_area = False
                                    break
                                    
                                # 确保高度相对平坦
                                if abs(height_map[ny][nx] - height_map[y][x]) > 0.1:
                                    flat_area = False
                                    break
                                    
                        if not flat_area:
                            break
                            
                    if flat_area:
                        avg_height /= count
                        plateau_candidates.append((x, y, avg_height))
        
        # 按照平均高度排序，选择最高的几个区域作为高原
        plateau_candidates.sort(key=lambda x: x[2], reverse=True)
        plateau_count = min(len(plateau_candidates), self.plateau_count)
        
        for i in range(plateau_count):
            center_x, center_y, _ = plateau_candidates[i]
            
            # 创建高原区域
            plateau_radius = random.randint(2, 4)
            
            for y in range(center_y - plateau_radius, center_y + plateau_radius + 1):
                for x in range(center_x - plateau_radius, center_x + plateau_radius + 1):
                    # 检查是否在地图内
                    if 0 <= x < width and 0 <= y < height:
                        # 计算到中心的距离
                        dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                        
                        # 在半径内的区域设置为高原
                        if dist <= plateau_radius:
                            grid[y][x] = TerrainType.PLATEAU
                            
    def add_all_features(self, grid, height_map, river_map, width, height):
        """添加所有地形特征
        
        Args:
            grid: 地形网格
            height_map: 高度图
            river_map: 河流图
            width: 地图宽度
            height: 地图高度
            
        Returns:
            list: 城市位置列表
        """
        # 添加城市
        cities = self.add_cities(grid, height_map, width, height)
        
        # 添加桥梁
        self.add_bridges(grid, river_map, width, height)
        
        # 添加山谷
        self.add_valleys(grid, height_map, width, height)
        
        # 添加高原
        self.add_plateaus(grid, height_map, width, height)
        
        return cities
                            
    def _is_passable_terrain(self, terrain_type):
        """检查地形是否可通行"""
        return terrain_type in [
            TerrainType.PLAIN, 
            TerrainType.FOREST, 
            TerrainType.HILL
        ]
        
    def _is_city_compatible_terrain(self, terrain_type):
        """检查地形是否适合城市建设"""
        return terrain_type in [
            TerrainType.PLAIN, 
            TerrainType.FOREST, 
            TerrainType.HILL
        ]
        
    def _is_land(self, terrain_type):
        """检查地形是否是陆地"""
        return terrain_type not in [
            TerrainType.RIVER, 
            TerrainType.LAKE, 
            TerrainType.OCEAN
        ] 