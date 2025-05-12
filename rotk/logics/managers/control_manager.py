from framework.core.ecs.world import World
from framework.managers.events import EventManager
import json
from rotk.logics.components import (
    HumanControlComponent,
    AgentControlComponent,
    UniqueComponent,
    AIControlComponent,
)


class ControlManager:
    """管理游戏控制组件和控制逻辑"""

    def __init__(self) -> None:
        """初始化控制管理器"""
        pass

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
    ) -> None:
        """初始化控制管理器"""
        self.event_manager = event_manager
        self.create_human_control(world)

    def create_human_control(self, world: World) -> int:
        """创建人类控制组件

        Args:
            world: 游戏世界

        Returns:
            int: 创建的组件实体ID
        """
        control_entity = world.create_entity()
        world.add_component(
            control_entity,
            UniqueComponent(unique_id="human"),
        )
        world.add_component(
            control_entity,
            HumanControlComponent(
                selected_unit=None,
                selected_target=None,
                selected_faction_id=None,
                selected_position=None,
            ),
        )
        return control_entity

    def create_ai_control(
        self,
        world: World,
        faction_id: int,
        difficulty: int = 1,
        behavior_type: str = "balanced",
    ) -> int:
        """创建AI控制组件

        Args:
            world: 游戏世界
            faction_id: AI控制的阵营ID
            difficulty: AI难度(1-5)
            behavior_type: AI行为类型

        Returns:
            int: 创建的组件实体ID
        """
        ai_entity = world.create_entity()
        world.add_component(
            ai_entity,
            AIControlComponent(
                faction_id=faction_id,
                difficulty=difficulty,
                behavior_type=behavior_type,
            ),
        )
        return ai_entity

    def create_agent_control(self, world: World) -> None:
        """创建代理控制组件"""
        pass

    def update(self, world: World, delta_time: float) -> None:
        """更新控制管理器"""
        pass
