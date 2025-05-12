import random
import numpy as np
from enum import Enum

class TerrainType(Enum):
    PLAIN = 0
    HILL = 1
    MOUNTAIN = 2
    FOREST = 3
    RIVER = 4
    LAKE = 5
    ROAD = 6
    BASIN = 7
    PLATEAU = 8

class MapManager:
    def __init__(self, engine):
        self.engine = engine
        self.width = 0  # 地图宽度，米
        self.height = 0  # 地图高度，米
        self.grid_size = 100  # 网格大小，米
        self.terrain = None  # 地形数据
        self.elevation = None  # 高程数据
        self.roads = []  # 道路数据
        self.grid_cols = 0  # 网格列数
        self.grid_rows = 0  # 网格行数
        
    def generate_map(self, width, height):
        """生成随机地图"""
        self.width = width
        self.height = height
        self.grid_cols = width // self.grid_size
        self.grid_rows = height // self.grid_size
        
        # 初始化地形和高程数据
        self.terrain = np.zeros((self.grid_rows, self.grid_cols), dtype=int)
        self.elevation = np.zeros((self.grid_rows, self.grid_cols), dtype=float)
        
        # 生成高程数据（使用柏林噪声或其他算法）
        self.generate_elevation()
        
        # 根据高程生成地形
        self.generate_terrain_from_elevation()
        
        # 生成河流和湖泊
        self.generate_water_bodies()
        
        # 生成道路
        self.generate_roads()
        
    def generate_elevation(self):
        """生成高程数据"""
        # 简化版：使用随机生成
        # 实际应使用柏林噪声等算法生成更自然的地形
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                # 生成0-1之间的随机值
                self.elevation[row, col] = random.random()
                
    def generate_terrain_from_elevation(self):
        """根据高程生成地形"""
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                elevation = self.elevation[row, col]
                
                # 根据高程值确定地形类型
                if elevation < 0.2:
                    self.terrain[row, col] = TerrainType.PLAIN.value
                elif elevation < 0.4:
                    self.terrain[row, col] = TerrainType.FOREST.value
                elif elevation < 0.6:
                    self.terrain[row, col] = TerrainType.HILL.value
                elif elevation < 0.8:
                    self.terrain[row, col] = TerrainType.PLATEAU.value
                else:
                    self.terrain[row, col] = TerrainType.MOUNTAIN.value
                    
    def generate_water_bodies(self):
        """生成河流和湖泊"""
        # 简化版：随机放置一些河流和湖泊
        # 实际应使用更复杂的算法生成自然的河流和湖泊
        
        # 生成湖泊
        num_lakes = random.randint(1, 3)
        for _ in range(num_lakes):
            lake_center_row = random.randint(0, self.grid_rows - 1)
            lake_center_col = random.randint(0, self.grid_cols - 1)
            lake_size = random.randint(3, 8)
            
            for r in range(max(0, lake_center_row - lake_size), min(self.grid_rows, lake_center_row + lake_size)):
                for c in range(max(0, lake_center_col - lake_size), min(self.grid_cols, lake_center_col + lake_size)):
                    if ((r - lake_center_row) ** 2 + (c - lake_center_col) ** 2) <= lake_size ** 2:
                        self.terrain[r, c] = TerrainType.LAKE.value
                        
        # 生成河流
        num_rivers = random.randint(1, 5)
        for _ in range(num_rivers):
            river_start_row = random.randint(0, self.grid_rows - 1)
            river_start_col = random.randint(0, self.grid_cols - 1)
            river_length = random.randint(10, 30)
            
            current_row, current_col = river_start_row, river_start_col
            for _ in range(river_length):
                self.terrain[current_row, current_col] = TerrainType.RIVER.value
                
                # 河流向低处流动
                neighbors = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = current_row + dr, current_col + dc
                    if 0 <= nr < self.grid_rows and 0 <= nc < self.grid_cols:
                        neighbors.append((nr, nc, self.elevation[nr, nc]))
                        
                if not neighbors:
                    break
                    
                # 选择高程最低的邻居
                next_row, next_col, _ = min(neighbors, key=lambda x: x[2])
                current_row, current_col = next_row, next_col
                
    def generate_roads(self):
        """生成道路"""
        # 简化版：生成一些随机道路
        # 实际应根据地形和重要位置生成更合理的道路网络
        num_roads = random.randint(3, 8)
        
        for _ in range(num_roads):
            road_start_row = random.randint(0, self.grid_rows - 1)
            road_start_col = random.randint(0, self.grid_cols - 1)
            road_end_row = random.randint(0, self.grid_rows - 1)
            road_end_col = random.randint(0, self.grid_cols - 1)
            
            # 使用简单的直线连接起点和终点
            road_points = self.line(road_start_row, road_start_col, road_end_row, road_end_col)
            
            for row, col in road_points:
                if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
                    # 道路可以覆盖其他地形，但不覆盖水体
                    if self.terrain[row, col] != TerrainType.RIVER.value and self.terrain[row, col] != TerrainType.LAKE.value:
                        self.terrain[row, col] = TerrainType.ROAD.value
                        
            self.roads.append(road_points)
            
    def line(self, start_row, start_col, end_row, end_col):
        """使用Bresenham算法生成直线"""
        points = []
        dx = abs(end_col - start_col)
        dy = abs(end_row - start_row)
        sx = 1 if start_col < end_col else -1
        sy = 1 if start_row < end_row else -1
        err = dx - dy
        
        row, col = start_row, start_col
        while True:
            points.append((row, col))
            if row == end_row and col == end_col:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                col += sx
            if e2 < dx:
                err += dx
                row += sy
                
        return points
        
    def get_terrain_at(self, x, y):
        """获取指定位置的地形类型"""
        col = int(x // self.grid_size)
        row = int(y // self.grid_size)
        
        if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
            return self.terrain[row, col]
        return None
        
    def get_elevation_at(self, x, y):
        """获取指定位置的高程"""
        col = int(x // self.grid_size)
        row = int(y // self.grid_size)
        
        if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
            return self.elevation[row, col]
        return None
        
    def is_passable(self, x, y, is_flying=False):
        """检查指定位置是否可通行"""
        terrain = self.get_terrain_at(x, y)
        
        if terrain is None:
            return False
            
        # 飞行单位可以通过任何地形
        if is_flying:
            return True
            
        # 不可通行的地形
        impassable_terrains = [TerrainType.MOUNTAIN.value, TerrainType.LAKE.value]
        return terrain not in impassable_terrains
        
    def get_movement_cost(self, x, y, is_mounted=False, is_flying=False):
        """获取移动到指定位置的代价"""
        terrain = self.get_terrain_at(x, y)
        
        if terrain is None:
            return float('inf')
            
        # 飞行单位不受地形影响
        if is_flying:
            return 1.0
            
        # 不同地形的移动代价
        terrain_costs = {
            TerrainType.PLAIN.value: 1.0,
            TerrainType.ROAD.value: 0.8,
            TerrainType.FOREST.value: 1.5,
            TerrainType.HILL.value: 2.0,
            TerrainType.PLATEAU.value: 1.8,
            TerrainType.BASIN.value: 1.2,
            TerrainType.RIVER.value: 3.0,
            TerrainType.MOUNTAIN.value: float('inf'),
            TerrainType.LAKE.value: float('inf')
        }
        
        cost = terrain_costs.get(terrain, 1.0)
        
        # 骑兵在平原和道路上移动更快，但在森林和丘陵上移动更慢
        if is_mounted:
            if terrain == TerrainType.PLAIN.value or terrain == TerrainType.ROAD.value:
                cost *= 0.8
            elif terrain == TerrainType.FOREST.value or terrain == TerrainType.HILL.value:
                cost *= 1.2
                
        return cost
        
    def save_map(self, filename):
        """保存地图到文件"""
        map_data = {
            'width': self.width,
            'height': self.height,
            'grid_size': self.grid_size,
            'terrain': self.terrain.tolist(),
            'elevation': self.elevation.tolist(),
            'roads': self.roads
        }
        
        # 保存到文件
        import json
        with open(filename, 'w') as f:
            json.dump(map_data, f)
            
    def load_map(self, filename):
        """从文件加载地图"""
        import json
        with open(filename, 'r') as f:
            map_data = json.load(f)
            
        self.width = map_data['width']
        self.height = map_data['height']
        self.grid_size = map_data['grid_size']
        self.terrain = np.array(map_data['terrain'])
        self.elevation = np.array(map_data['elevation'])
        self.roads = map_data['roads']
        self.grid_rows, self.grid_cols = self.terrain.shape
        
    def render(self, surface, camera_x, camera_y, zoom=1.0):
        """渲染地图"""
        # 地形颜色映射
        terrain_colors = {
            TerrainType.PLAIN.value: (200, 230, 180),  # 浅绿色
            TerrainType.HILL.value: (160, 160, 120),   # 棕色
            TerrainType.MOUNTAIN.value: (120, 100, 80), # 深棕色
            TerrainType.FOREST.value: (50, 150, 50),   # 深绿色
            TerrainType.RIVER.value: (100, 150, 255),  # 蓝色
            TerrainType.LAKE.value: (50, 100, 200),    # 深蓝色
            TerrainType.ROAD.value: (200, 200, 200),   # 灰色
            TerrainType.BASIN.value: (180, 210, 170),  # 浅绿灰色
            TerrainType.PLATEAU.value: (170, 140, 100) # 浅棕色
        }
        
        # 计算可见区域
        screen_width, screen_height = surface.get_size()
        visible_left = max(0, int(camera_x - screen_width / (2 * zoom)))
        visible_top = max(0, int(camera_y - screen_height / (2 * zoom)))
        visible_right = min(self.width, int(camera_x + screen_width / (2 * zoom)))
        visible_bottom = min(self.height, int(camera_y + screen_height / (2 * zoom)))
        
        # 接上文的render方法
        # 计算可见网格范围
        start_col = max(0, visible_left // self.grid_size)
        start_row = max(0, visible_top // self.grid_size)
        end_col = min(self.grid_cols, (visible_right // self.grid_size) + 1)
        end_row = min(self.grid_rows, (visible_bottom // self.grid_size) + 1)
        
        # 绘制可见网格
        import pygame
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                # 计算网格在屏幕上的位置
                screen_x = int((col * self.grid_size - camera_x) * zoom + screen_width / 2)
                screen_y = int((row * self.grid_size - camera_y) * zoom + screen_height / 2)
                grid_width = int(self.grid_size * zoom)
                
                # 绘制地形
                terrain_type = self.terrain[row, col]
                color = terrain_colors.get(terrain_type, (128, 128, 128))
                
                # 根据高程调整颜色亮度
                elevation = self.elevation[row, col]
                brightness = 0.7 + 0.3 * elevation  # 0.7-1.0范围
                color = tuple(int(c * brightness) for c in color)
                
                # 绘制网格
                pygame.draw.rect(surface, color, (screen_x, screen_y, grid_width, grid_width))
                
                # 绘制网格线
                if zoom > 0.5:  # 只在放大时绘制网格线
                    pygame.draw.rect(surface, (50, 50, 50), (screen_x, screen_y, grid_width, grid_width), 1)