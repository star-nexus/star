from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from enum import Enum

class TerrainType(Enum):
    """地形类型枚举"""
    PLAIN = 0      # 平原
    HILL = 1       # 丘陵
    MOUNTAIN = 2   # 山地
    FOREST = 3     # 森林
    WATER = 4      # 水域
    DESERT = 5     # 沙漠
    SWAMP = 6      # 沼泽
    ROAD = 7       # 道路
    CITY = 8       # 城市
    PASS = 9       # 关隘

@dataclass
class TileComponent:
    """地形块组件"""
    # 地形基本属性
    terrain_type: TerrainType = TerrainType.PLAIN
    elevation: int = 0  # 海拔高度，用于等高线
    moisture: float = 0.5  # 湿度，影响地形生成
    
    # 网格坐标
    grid_x: int = 0
    grid_y: int = 0
    
    # 战略属性
    movement_cost: float = 1.0  # 移动消耗
    defense_bonus: float = 0.0  # 防御加成
    attack_penalty: float = 0.0  # 攻击惩罚
    vision_block: float = 0.0   # 视野阻挡
    
    # 寻路相关
    passable: bool = True       # 是否可通行
    
    # 资源相关
    resources: Dict[str, float] = field(default_factory=dict)  # 资源类型及数量
    
    # 战术属性
    provides_cover: bool = False  # 是否提供掩护
    
    # 季节影响
    seasonal_effects: Dict[str, Dict[str, float]] = field(default_factory=dict)  # 季节对地形属性的影响
    
    # 天气影响
    weather_effects: Dict[str, Dict[str, float]] = field(default_factory=dict)  # 天气对地形属性的影响
    
    def get_movement_cost(self, unit_type: str = "infantry", season: str = "spring", weather: str = "clear") -> float:
        """获取特定单位类型在当前季节和天气下的移动消耗"""
        base_cost = self.movement_cost
        
        # 应用季节影响
        if season in self.seasonal_effects and "movement_cost" in self.seasonal_effects[season]:
            base_cost *= self.seasonal_effects[season]["movement_cost"]
            
        # 应用天气影响
        if weather in self.weather_effects and "movement_cost" in self.weather_effects[weather]:
            base_cost *= self.weather_effects[weather]["movement_cost"]
            
        # 应用单位类型特殊规则
        # 例如：骑兵在森林中移动更慢，但在平原上更快
        if unit_type == "cavalry":
            if self.terrain_type == TerrainType.FOREST:
                base_cost *= 1.5
            elif self.terrain_type == TerrainType.PLAIN:
                base_cost *= 0.8
                
        return base_cost
    
    def get_defense_bonus(self, unit_type: str = "infantry") -> float:
        """获取特定单位类型的防御加成"""
        base_bonus = self.defense_bonus
        
        # 应用单位类型特殊规则
        if unit_type == "archer" and self.terrain_type == TerrainType.HILL:
            base_bonus += 0.1  # 弓箭手在丘陵上有额外防御加成
            
        return base_bonus
    
    def get_attack_penalty(self, unit_type: str = "infantry") -> float:
        """获取特定单位类型的攻击惩罚"""
        return self.attack_penalty
    
    def get_vision_block(self) -> float:
        """获取视野阻挡值"""
        return self.vision_block