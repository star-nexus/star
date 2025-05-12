import json
import random
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import FactionComponent, UnitStatsComponent


class FactionSystem(System):
    """阵营系统，管理不同阵营间的关系和交互"""

    def __init__(self) -> None:
        super().__init__([FactionComponent], priority=5)
        # self.factions = {}  # 存储阵营信息 {faction_id: faction_data}
        # self.faction_relations = (
        #     {}
        # )  # 存储阵营关系 {(faction_id1, faction_id2): relation_value}
        # self.active_factions = []  # 当前活跃的阵营ID列表
        # self.event_manager = event_manager

    def initialize(
        self,
        event_manager: EventManager,
    ) -> None:
        self.event_manager = event_manager

    def update_faction_info(self, world: World) -> None:
        """更新阵营信息(单位数量等)

        Args:
            world: 游戏世界
        """
        # 重置阵营单位计数
        # for faction_id in self.factions:
        factions = world.get_entities_with_components(FactionComponent)
        for faction_entity in factions:
            faction_comp = world.get_component(faction_entity, FactionComponent)
            if faction_comp:
                faction_comp.unit_count = 0
                # self.factions[faction_id]["units"] = []

            # 统计各阵营单位数量
            for unit in world.get_entities_with_components(UnitStatsComponent):
                unit_stats = world.get_component(unit, UnitStatsComponent)
                faction_id = unit_stats.faction_id

                if faction_id == faction_comp.faction_id:
                    # # faction_entity = self.factions[faction_id]["entity"]
                    # faction_comp = world.get_component(faction_entity, FactionComponent)
                    # if faction_comp:
                    faction_comp.unit_count += 1
                    # self.factions[faction_id]["units"].append(entity)

    def update(self, world: World, delta_time: float) -> None:
        """更新阵营系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 定期更新阵营信息
        self.update_faction_info(world)

        # 检查阵营胜利/失败
        self.check_faction_status(world)

    def check_faction_status(self, world: World) -> None:
        # 检查是否有阵营失败(单位数量为0)
        # for faction_id in list(self.active_factions):
        #     if faction_id in self.factions:
        #         faction_entity = self.factions[faction_id]["entity"]
        factions = world.get_entities_with_components(FactionComponent)
        for faction_entity in factions:
            faction_comp = world.get_component(faction_entity, FactionComponent)
            if faction_comp.active:
                if faction_comp.unit_count == 0 and faction_comp.city_count == 0:
                    # 阵营失败
                    faction_comp.active = False
                    # self.active_factions.remove(faction_id)

                    # 发布阵营失败事件
                    self.event_manager.publish(
                        "FACTION_DEFEATED",
                        Message(
                            topic="FACTION_DEFEATED",
                            data_type="faction_event",
                            data={
                                "faction_id": faction_comp.faction_id,
                                "faction_name": faction_comp.name,
                            },
                        ),
                    )
