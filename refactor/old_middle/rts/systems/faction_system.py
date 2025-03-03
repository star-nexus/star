from framework.ecs.system import System
from rts.components import FactionComponent, ResourceComponent


class FactionSystem(System):
    """
    阵营系统：管理游戏中的所有阵营，处理阵营间的交互
    """

    def __init__(self):
        super().__init__([FactionComponent])
        self.factions = {}  # 以faction_id为键，存储阵营实体
        self.player_faction = None  # 玩家阵营
        self.active_factions = []  # 当前活跃的阵营列表

    def initialize_factions(self, faction_definitions):
        """初始化阵营"""
        for faction_def in faction_definitions:
            faction_entity = self.world.create_entity()
            faction_comp = FactionComponent(
                faction_def["id"], faction_def["name"], faction_def["color"]
            )
            faction_comp.is_player = faction_def.get("is_player", False)
            faction_entity.add_component(faction_comp)

            # 添加资源组件
            if "resources" in faction_def:
                res_comp = ResourceComponent()
                for res_type, amount in faction_def["resources"].items():
                    if res_type == "gold":
                        res_comp.gold = amount
                    elif res_type == "weapons":
                        res_comp.weapons = amount
                    elif res_type == "food":
                        res_comp.food = amount
                    elif res_type == "supplies":
                        res_comp.supplies = amount
                faction_entity.add_component(res_comp)

            # 记录阵营
            self.factions[faction_def["id"]] = faction_entity
            self.active_factions.append(faction_entity)

            # 标记玩家阵营
            if faction_comp.is_player:
                self.player_faction = faction_entity

    def update(self, delta_time):
        """更新阵营状态，每帧调用"""
        # 遍历所有阵营实体
        for entity in self.entities:
            faction_comp = entity.get_component(FactionComponent)

            # 如果实体有资源组件，更新资源
            if entity.has_component(ResourceComponent):
                res_comp = entity.get_component(ResourceComponent)
                res_comp.update_resources(delta_time)

        # 检查阵营生存状态
        self._check_faction_status()

    def _check_faction_status(self):
        """检查各阵营状态，判断是否有阵营被消灭"""
        # 此函数将在后续实现，当有单位和建筑系统时可以更好地判断
        pass

    def get_faction_by_id(self, faction_id):
        """根据ID获取阵营实体"""
        return self.factions.get(faction_id)

    def get_faction_entities(self, faction_id):
        """获取指定阵营的所有实体（单位和建筑）"""
        faction_entities = []
        for entity in self.world.entities.values():
            if entity.has_component(FactionComponent):
                faction_comp = entity.get_component(FactionComponent)
                if faction_comp.faction_id == faction_id:
                    faction_entities.append(entity)
        return faction_entities

    def get_player_faction(self):
        """获取玩家阵营"""
        return self.player_faction
