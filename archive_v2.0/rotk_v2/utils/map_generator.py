import numpy as np
from noise import pnoise2, snoise2
import random
from typing import Tuple, List, Dict, Any
from rotk_v2.components.tile_component import TerrainType

class MapGenerator:
    """地图生成器，使用噪声算法生成地形"""
    
    def __init__(self, width: int, height: int, seed: int = None):
        """初始化地图生成器"""
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 999999)
        random.seed(self.seed)
        np.random.seed(self.seed)
        
    def generate_elevation_map(self, octaves: int = 6, persistence: float = 0.5, lacunarity: float = 2.0) -> np.ndarray:
        """生成海拔高度图"""
        elevation = np.zeros((self.height, self.width), dtype=np.float32)
        
        # 使用Perlin噪声生成自然的地形
        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5
                elevation[y, x] = snoise2(nx, ny, octaves=octaves, 
                                         persistence=persistence, 
                                         lacunarity=lacunarity, 
                                         base=self.seed)
                
        # 归一化到0-100范围
        elevation = (elevation - elevation.min()) / (elevation.max() - elevation.min()) * 100
        return elevation.astype(np.int32)
        
    def generate_moisture_map(self, octaves: int = 4, persistence: float = 0.5, lacunarity: float = 2.0) -> np.ndarray:
        """生成湿度图"""
        moisture = np.zeros((self.height, self.width), dtype=np.float32)
        
        # 使用不同的种子生成湿度
        moisture_seed = self.seed + 1000
        
        for y in range(self.height):
            for x in range(self.width):
                nx = x / self.width - 0.5
                ny = y / self.height - 0.5
                moisture[y, x] = snoise2(nx, ny, octaves=octaves, 
                                        persistence=persistence, 
                                        lacunarity=lacunarity, 
                                        base=moisture_seed)
                
        # 归一化到0-1范围
        moisture = (moisture - moisture.min()) / (moisture.max() - moisture.min())
        return moisture
        
    def generate_terrain_map(self, elevation: np.ndarray, moisture: np.ndarray) -> np.ndarray:
        """根据海拔和湿度生成地形类型"""
        terrain = np.zeros((self.height, self.width), dtype=np.int32)
        
        for y in range(self.height):
            for x in range(self.width):
                e = elevation[y, x]
                m = moisture[y, x]
                
                # 水域
                if e < 20:
                    terrain[y, x] = TerrainType.WATER.value
                # 沙漠
                elif e < 40 and m < 0.3:
                    terrain[y, x] = TerrainType.DESERT.value
                # 平原
                elif e < 40:
                    terrain[y, x] = TerrainType.PLAIN.value
                # 森林
                elif e < 60 and m > 0.6:
                    terrain[y, x] = TerrainType.FOREST.value
                # 丘陵
                elif e < 60:
                    terrain[y, x] = TerrainType.HILL.value
                # 山地
                elif e < 80:
                    terrain[y, x] = TerrainType.MOUNTAIN.value
                # 高山
                else:
                    terrain[y, x] = TerrainType.MOUNTAIN.value
                    
        # 添加一些沼泽
        for _ in range(int(self.width * self.height * 0.01)):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if terrain[y, x] == TerrainType.PLAIN.value and moisture[y, x] > 0.7:
                terrain[y, x] = TerrainType.SWAMP.value
                
        # 添加一些道路
        self._generate_roads(terrain)
                
        return terrain
    
    def _generate_roads(self, terrain: np.ndarray) -> None:
        """生成道路网络"""
        # 选择几个主要点作为城市/关键点
        num_key_points = int(np.sqrt(self.width * self.height) / 5)
        key_points = []
        
        # 确保关键点不在水域或山地
        for _ in range(num_key_points):
            for _ in range(100):  # 尝试100次找到合适的点
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                if terrain[y, x] not in [TerrainType.WATER.value, TerrainType.MOUNTAIN.value]:
                    key_points.append((x, y))
                    # 标记为城市
                    terrain[y, x] = TerrainType.CITY.value
                    break
        
        # 连接关键点，形成道路网络
        for i in range(len(key_points)):
            for j in range(i + 1, len(key_points)):
                if random.random() < 0.6:  # 60%的概率连接两个关键点
                    self._create_road(terrain, key_points[i], key_points[j])
    
    def _create_road(self, terrain: np.ndarray, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        """在两点之间创建道路"""
        x1, y1 = start
        x2, y2 = end
        
        # 使用A*算法寻找最佳路径
        # 这里简化为直线路径，实际应用中应使用A*
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        x, y = x1, y1
        while x != x2 or y != y2:
            # 如果不是水域或山地，则设为道路
            if 0 <= x < self.width and 0 <= y < self.height:
                if terrain[y, x] not in [TerrainType.WATER.value, TerrainType.MOUNTAIN.value, TerrainType.CITY.value]:
                    terrain[y, x] = TerrainType.ROAD.value
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def generate_map(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """生成完整地图，返回(海拔图, 地形图, 湿度图)"""
        elevation = self.generate_elevation_map()
        moisture = self.generate_moisture_map()
        terrain = self.generate_terrain_map(elevation, moisture)
        
        return elevation, terrain, moisture