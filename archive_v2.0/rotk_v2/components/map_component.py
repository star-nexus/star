from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from rotk_v2.components.tile_component import TileComponent, TerrainType

@dataclass
class MapComponent:
    """地图组件，存储整个地图的信息"""
    width: int = 100  # 地图宽度(格子数)
    height: int = 100  # 地图高度(格子数)
    tile_size: int = 32  # 每个格子的像素大小
    
    # 地形数据，使用numpy数组存储提高性能
    elevation_map: np.ndarray = field(default_factory=lambda: np.zeros((100, 100), dtype=np.int32))
    terrain_map: np.ndarray = field(default_factory=lambda: np.zeros((100, 100), dtype=np.int32))
    moisture_map: np.ndarray = field(default_factory=lambda: np.zeros((100, 100), dtype=np.float32))
    
    # 地形实体ID映射
    tile_entities: Dict[Tuple[int, int], int] = field(default_factory=dict)
    
    # 寻路缓存
    pathfinding_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[Tuple[int, int]]] = field(default_factory=dict)
    
    # 视野缓存
    vision_cache: Dict[Tuple[int, int], List[Tuple[int, int]]] = field(default_factory=dict)
    
    # 地图名称和描述
    name: str = "默认地图"
    description: str = "自动生成的地图"
    
    # 地图生成参数
    seed: int = 0  # 随机种子
    octaves: int = 6  # 噪声函数的八度数
    persistence: float = 0.5  # 噪声函数的持续度
    lacunarity: float = 2.0  # 噪声函数的间隙度
    
    def get_terrain_at(self, x: int, y: int) -> Optional[TerrainType]:
        """获取指定坐标的地形类型"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return TerrainType(self.terrain_map[y, x])
        return None
    
    def get_elevation_at(self, x: int, y: int) -> Optional[int]:
        """获取指定坐标的海拔高度"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.elevation_map[y, x]
        return None
    
    def get_tile_entity_at(self, x: int, y: int) -> Optional[int]:
        """获取指定坐标的地形实体ID"""
        return self.tile_entities.get((x, y))
    
    def is_passable(self, x: int, y: int, unit_type: str = "infantry") -> bool:
        """检查指定坐标是否可通行"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
            
        terrain_type = self.get_terrain_at(x, y)
        
        # 基本通行规则
        if terrain_type == TerrainType.WATER:
            return False if unit_type != "naval" else True
        elif terrain_type == TerrainType.MOUNTAIN:
            return False
            
        return True
    
    def get_movement_cost(self, x: int, y: int, unit_type: str = "infantry") -> float:
        """获取指定坐标的移动消耗"""
        if not self.is_passable(x, y, unit_type):
            return float('inf')
            
        # 基本移动消耗
        terrain_type = self.get_terrain_at(x, y)
        base_cost = 1.0
        
        # 根据地形类型调整移动消耗
        if terrain_type == TerrainType.PLAIN:
            base_cost = 1.0
        elif terrain_type == TerrainType.HILL:
            base_cost = 1.5
        elif terrain_type == TerrainType.FOREST:
            base_cost = 2.0
        elif terrain_type == TerrainType.SWAMP:
            base_cost = 3.0
        elif terrain_type == TerrainType.ROAD:
            base_cost = 0.5
            
        # 考虑单位类型
        if unit_type == "cavalry":
            if terrain_type == TerrainType.FOREST or terrain_type == TerrainType.SWAMP:
                base_cost *= 1.5
            elif terrain_type == TerrainType.PLAIN or terrain_type == TerrainType.ROAD:
                base_cost *= 0.8
                
        return base_cost