"""
管理器模块

包含游戏中使用的所有管理器实现。
"""

# 导入所有管理器
from .map_manager import MapManager
from .terrain_generator import TerrainGenerator
from .terrain_utility import TerrainUtility
from .map_feature_generator import MapFeatureGenerator
from .camera_manager import CameraManager
from .unit_manager import UnitManager
from .faction_manager import FactionManager
from .control_manager import ControlManager
from .scenario_manager import ScenarioManager

__all__ = [
    'MapManager',
    'TerrainGenerator',
    'TerrainUtility',
    'MapFeatureGenerator',
    'CameraManager',
    'UnitManager',
    'FactionManager',
    'ControlManager',
    'ScenarioManager',
]
