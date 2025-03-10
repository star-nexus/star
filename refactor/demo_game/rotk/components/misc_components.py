from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from framework.core.ecs.component import Component


@dataclass
class VictoryConditionComponent(Component):
    """胜利条件组件，定义当前游戏的胜利条件"""

    # 胜利类型
    victory_type: str = (
        "ANNIHILATION"  # 可选值: ANNIHILATION(全歼敌方), CAPTURE(占领目标), SURVIVAL(生存时间)
    )

    # 根据胜利类型的特定条件
    target_positions: List[Tuple[int, int]] = field(
        default_factory=list
    )  # CAPTURE类型的目标位置
    survival_time: float = 600.0  # SURVIVAL类型的生存时间(秒)
    target_faction_id: int = 0  # 需要消灭的特定阵营ID

    # 当前进度
    progress: float = 0.0  # 完成度百分比 0.0-1.0
    elapsed_time: float = 0.0  # 已经过的时间(秒)
