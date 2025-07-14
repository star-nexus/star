"""
小地图相关组件
"""

from dataclasses import dataclass
from typing import Tuple
from framework import SingletonComponent


@dataclass
class MiniMap(SingletonComponent):
    """小地图单例组件 - 纯数据组件"""

    # 小地图显示设置
    visible: bool = True
    width: int = 200
    height: int = 150
    position: Tuple[int, int] = (10, 10)  # 屏幕上的位置

    # 缩放和偏移
    scale: float = 0.1  # 相对于主地图的缩放比例
    center_on_camera: bool = True  # 是否以摄像机为中心

    # 视觉设置
    background_alpha: int = 180  # 背景透明度
    border_color: Tuple[int, int, int] = (255, 255, 255)  # 边框颜色
    border_width: int = 2

    # 显示选项
    show_units: bool = True
    show_terrain: bool = True
    show_fog_of_war: bool = True
    show_camera_viewport: bool = True  # 显示主摄像机的视野范围

    # 交互设置
    clickable: bool = True  # 是否可以点击小地图进行导航
