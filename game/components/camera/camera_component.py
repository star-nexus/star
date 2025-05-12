from dataclasses import dataclass
from framework.ecs.component import Component


@dataclass
class CameraComponent(Component):
    """摄像机组件，控制视口位置和缩放"""

    x: float = 0.0  # 摄像机中心点x坐标
    y: float = 0.0  # 摄像机中心点y坐标
    zoom: float = 1.0  # 缩放比例
    width: int = 1280  # 视口宽度
    height: int = 720  # 视口高度
    min_zoom: float = 0.5  # 最小缩放比例
    max_zoom: float = 20.0  # 最大缩放比例
    move_speed: float = 500.0  # 移动速度
    zoom_speed: float = 0.1  # 缩放速度
