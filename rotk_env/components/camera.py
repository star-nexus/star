from dataclasses import dataclass
from typing import Tuple
from framework import SingletonComponent


@dataclass
class Camera(SingletonComponent):
    """摄像机单例组件"""

    offset_x: float = 0.0  # 摄像机X偏移
    offset_y: float = 0.0  # 摄像机Y偏移
    zoom: float = 1.0  # 缩放级别
    speed: float = 200.0  # 移动速度(像素/秒)

    def get_offset(self) -> Tuple[float, float]:
        """获取摄像机偏移"""
        return (self.offset_x, self.offset_y)

    def set_offset(self, x: float, y: float) -> None:
        """设置摄像机偏移"""
        self.offset_x = x
        self.offset_y = y

    def move(self, dx: float, dy: float) -> None:
        """移动摄像机"""
        self.offset_x += dx
        self.offset_y += dy
