from dataclasses import dataclass
from framework.core.ecs.component import Component
from typing import Tuple, Optional


@dataclass
class Sprite(Component):
    """精灵组件，用于渲染具有纹理的实体"""

    # 图像/纹理资源的标识符
    texture_id: str = ""
    # 在纹理图集中的区域 (x, y, width, height)
    source_rect: Optional[Tuple[int, int, int, int]] = None
    # 绘制缩放
    scale: float = 1.0
    # 绘制旋转(角度)
    rotation: float = 0.0
    # 绘制图层(越大越上层)
    z_order: int = 0
    # 是否可见
    visible: bool = True
    # 透明度 (0-255)
    alpha: int = 255
    # 着色颜色 (r,g,b)，用于给精灵着色
    tint: Tuple[int, int, int] = (255, 255, 255)
    # 翻转
    flip_x: bool = False
    flip_y: bool = False
