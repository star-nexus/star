from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from framework.ecs.component import Component


@dataclass
class BattleStatsComponent(Component):
    """战场统计组件，存储战场情况的全面统计信息

    该组件以上帝视角收集所有战场信息，包括敌我双方的兵力状态、调动情况、
    战场环境和作战进程等数据。其他系统可以根据需要处理这些信息。
    """

    faction: int = 0  # 所属阵营
    # 单位情况 - 单位ID: 单位信息, 包括位置、状态、属性等
    enemy_status_info: Dict[str, Dict] = field(
        default_factory=dict
    )  # 观测范围内敌方兵力部署与状态

    # 调动情况 - 调动单位ID: 调动信息, 包括调动目标、调动时间等
    enemy_transfer_situation: Dict[str, str] = field(
        default_factory=dict
    )  # 敌方调动情况

    my_status_info: Dict[str, Dict] = field(default_factory=dict)  # 我方兵力状态
    # 作战任务 - 任务ID: 任务信息, 包括任务目标、任务进度等
    my_transfer_situation: Dict[str, str] = field(
        default_factory=dict
    )  # 我方作战任务执行进度

    # 战场环境
    terrain_environment: Dict[str, Dict] = field(default_factory=dict)  # 地理环境信息

    # 作战进程
    contact_and_fire: Dict[str, List] = field(
        default_factory=dict
    )  # 交战双方的接触与交火情况,
    death_status: Dict[str, List] = field(default_factory=dict)  # 交战双方的伤亡情况
