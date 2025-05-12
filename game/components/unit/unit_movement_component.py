from dataclasses import dataclass


@dataclass
class MovementComponent:
    pass


@dataclass
class UnitMovementPathComponent:
    start_x: float
    start_y: float
    target_x: float
    target_y: float
    current_x: float
    current_y: float
    speed: float  # 单位每秒移动的距离
    total_distance: float = 0.0  # 总移动距离
    distance_moved: float = 0.0  # 已移动距离
    completed: bool = False  # 是否完成移动
    terrain_factor: float = 1.0  # 地形影响因子
