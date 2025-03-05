from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class MapPosition(Component):
    """地图位置组件，表示实体在地图网格中的位置"""

    x: int = 0  # 网格X坐标
    y: int = 0  # 网格Y坐标
    # 是否锁定在格子中心
    lock_to_grid: bool = True
