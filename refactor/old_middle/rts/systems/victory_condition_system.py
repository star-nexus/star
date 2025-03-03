import pygame
from framework.ecs.system import System
from rts.components.faction import FactionComponent
from rts.components.building import BuildingComponent
from rts.managers.event_manager import EventManager
from rts.managers.game_events import GameOverEvent
from rts.components.resource import ResourceComponent


class VictoryCondition:
    """代表一个胜利条件的基类"""

    def check(self, entities, factions):
        """检查胜利条件是否满足"""
        return False, None


class EliminationVictoryCondition(VictoryCondition):
    """消灭所有敌方单位和建筑的胜利条件"""

    def check(self, entities, factions):
        active_factions = set()

        # 检查每个实体属于哪个阵营
        for entity_id, entity in entities.items():  # 修改这里使用items()迭代字典
            faction_comp = entity.get_component(FactionComponent)
            if faction_comp:
                active_factions.add(faction_comp.faction_id)

        # 获取所有应该存在的阵营
        all_factions = set(factions.keys())

        # 如果只有一个阵营有实体，并且游戏中存在多个阵营，那么该阵营获胜
        if len(active_factions) == 1 and len(all_factions) > 1:
            return True, list(active_factions)[0]
        return False, None


class ResourceVictoryCondition(VictoryCondition):
    """达到特定资源数量的胜利条件"""

    def __init__(self, target_resource_amount):
        self.target_amount = target_resource_amount

    def check(self, entities, factions):
        # 遍历所有阵营，查找是否有阵营的资源达到目标值
        for faction_id, faction_comp in factions.items():
            # 寻找对应阵营的实体，该实体应该有ResourceComponent
            for entity_id, entity in entities.items():
                if entity.has_component(FactionComponent) and entity.has_component(
                    ResourceComponent
                ):

                    faction = entity.get_component(FactionComponent)
                    # 确认是同一个阵营
                    if faction.faction_id == faction_id:
                        # 获取资源组件
                        res_comp = entity.get_component(ResourceComponent)
                        # 检查金币数量是否达到目标
                        if res_comp.gold >= self.target_amount:
                            return True, faction_id

        return False, None


class MainBaseVictoryCondition(VictoryCondition):
    """基地存活/摧毁的胜利条件"""

    def check(self, entities, factions):
        factions_with_base = set()

        for entity_id, entity in entities.items():  # 修改这里使用items()迭代字典
            building_comp = entity.get_component(BuildingComponent)
            faction_comp = entity.get_component(FactionComponent)

            if (
                building_comp
                and faction_comp
                and building_comp.building_type == "main_base"
            ):
                factions_with_base.add(faction_comp.faction_id)

        # 如果只有一个阵营有主基地，该阵营获胜
        if len(factions_with_base) == 1:
            return True, list(factions_with_base)[0]
        return False, None


class VictoryConditionSystem(System):
    def __init__(self):
        super().__init__()
        self.victory_conditions = []
        self.game_over = False
        self.winner = None
        self.event_manager = EventManager()

    def add_victory_condition(self, condition):
        """添加胜利条件"""
        self.victory_conditions.append(condition)

    def update(self, delta_time):
        """检查所有胜利条件"""
        if self.game_over:
            return

        factions = self._get_factions_from_entities(self.world.entities)

        for condition in self.victory_conditions:
            victory, winner_faction_id = condition.check(self.world.entities, factions)
            if victory:
                self.game_over = True
                self.winner = winner_faction_id
                self.event_manager.emit(GameOverEvent(winner_faction_id))
                break

    def _get_factions_from_entities(self, entities):
        """从实体字典中提取所有阵营信息"""
        factions = {}
        # 修改遍历方式，使用 .items() 来同时获取键和值
        for entity_id, entity in entities.items():
            faction_comp = entity.get_component(FactionComponent)
            if faction_comp and faction_comp.faction_id not in factions:
                factions[faction_comp.faction_id] = faction_comp
        return factions

    def reset(self):
        """重置胜利条件系统"""
        self.game_over = False
        self.winner = None
