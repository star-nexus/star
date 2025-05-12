from dataclasses import dataclass
from framework_v2.ecs.component import Component
from enum import Enum, auto

@dataclass
class CameraComponent(Component):
    """
    相机组件 - 纯数据组件
    存储相机状态信息
    """
    x: float = 0 # 相机X坐标
    y: float = 0 # 相机Y坐标
    zoom: float = 1.0 # 缩放级别
    move_speed: float = 300.0 # 移动速度（像素/秒）
    zoom_speed: float = 0.1 # 缩放速度

@dataclass
class MainCameraTagComponent:
    """主相机标签组件"""
    pass

@dataclass
class MiniMapCameraTagComponent:
    """小地图相机标签组件"""
    pass