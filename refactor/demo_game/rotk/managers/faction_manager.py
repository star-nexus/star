from framework.core.ecs.world import World
from framework.managers.events import EventManager
import json
from rotk.components import FactionComponent


class FactionManager:
    def __init__(
        self, world: World, event_manager: EventManager, config_path: str = None
    ) -> None:
        """初始化阵营系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            config_path: 阵营配置文件路径
        """
        self.world = world
        self.event_manager = event_manager

        # 如果提供了配置文件，从配置加载阵营信息
        if config_path:
            self.load_factions_from_config(config_path)
        else:
            # 否则创建默认阵营
            self.create_default_factions()

    def load_factions_from_config(self, config_path: str) -> None:
        """从配置文件加载阵营信息

        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            for faction_data in config.get("factions", []):
                faction_id = faction_data.get("id")
                self.create_faction(
                    faction_id,
                    faction_data.get("name", f"阵营{faction_id}"),
                    tuple(faction_data.get("color", (200, 200, 200))),
                )

            # 加载阵营关系
            for relation in config.get("relations", []):
                self.set_faction_relation(
                    relation.get("faction1"),
                    relation.get("faction2"),
                    relation.get("value", 0),
                )
        except Exception as e:
            print(f"加载阵营配置失败: {e}")
            self.create_default_factions()

    def create_default_factions(self) -> None:
        """创建默认阵营"""
        # 创建三个默认阵营
        self.create_faction(1, "魏", (0, 0, 180))  # 蓝色
        self.create_faction(2, "蜀", (180, 0, 0))  # 红色
        self.create_faction(3, "吴", (0, 150, 0))  # 绿色
        self.create_faction(4, "黄巾", (255, 255, 0))  # 黄色

        # 设置默认关系
        # self.set_faction_relation(1, 2, -50)  # 魏蜀敌对
        # self.set_faction_relation(1, 3, -30)  # 魏吴轻度敌对
        # self.set_faction_relation(2, 3, 30)  # 蜀吴同盟
        # self.set_faction_relation(1, 4, -80)  # 魏黄巾深度敌对
        # self.set_faction_relation(2, 4, -80)  # 蜀黄巾深度敌对
        # self.set_faction_relation(3, 4, -80)  # 吴黄巾深度敌对

    def create_faction(self, faction_id: int, name: str, color: tuple) -> int:
        """创建新的阵营

        Args:
            faction_id: 阵营ID
            name: 阵营名称
            color: 阵营颜色(RGB元组)

        Returns:
            int: 阵营实体ID
        """
        # 创建阵营实体
        faction_entity = self.world.create_entity()
        self.world.add_component(
            faction_entity,
            FactionComponent(
                faction_id=faction_id, name=name, color=color, active=True
            ),
        )

        # 存储阵营信息
        # self.factions[faction_id] = {
        #     "entity": faction_entity,
        #     "name": name,
        #     "color": color,
        #     "units": [],  # 阵营单位列表
        # }

        # self.active_factions.append(faction_id)

        return faction_entity

    # def set_faction_relation(
    #     self, faction_id1: int, faction_id2: int, relation_value: int
    # ) -> None:
    #     """设置两个阵营间的关系值

    #     Args:
    #         faction_id1: 第一个阵营ID
    #         faction_id2: 第二个阵营ID
    #         relation_value: 关系值(-100到100)
    #     """
    #     if faction_id1 == faction_id2:
    #         return  # 不设置自己与自己的关系

    #     # 确保faction_id1 < faction_id2作为统一的键格式
    #     if faction_id1 > faction_id2:
    #         faction_id1, faction_id2 = faction_id2, faction_id1

    #     key = (faction_id1, faction_id2)
    #     self.faction_relations[key] = max(-100, min(100, relation_value))

    #     # 同时更新实体组件中的外交信息
    #     for faction_id in [faction_id1, faction_id2]:
    #         if faction_id in self.factions:
    #             faction_entity = self.factions[faction_id]["entity"]
    #             faction_comp = self.world.get_component(
    #                 faction_entity, FactionComponent
    #             )
    #             if faction_comp:
    #                 other_id = faction_id2 if faction_id == faction_id1 else faction_id1
    #                 faction_comp.diplomacy[other_id] = self.faction_relations[key]

    # def get_faction_relation(self, faction_id1: int, faction_id2: int) -> int:
    #     """获取两个阵营间的关系值

    #     Args:
    #         faction_id1: 第一个阵营ID
    #         faction_id2: 第二个阵营ID

    #     Returns:
    #         int: 关系值，如果未设置则返回0
    #     """
    #     if faction_id1 == faction_id2:
    #         return 100  # 自己与自己的关系始终为100

    #     # 确保faction_id1 < faction_id2作为统一的键格式
    #     if faction_id1 > faction_id2:
    #         faction_id1, faction_id2 = faction_id2, faction_id1

    #     key = (faction_id1, faction_id2)
    #     return self.faction_relations.get(key, 0)

    # def are_factions_hostile(self, faction_id1: int, faction_id2: int) -> bool:
    #     """检查两个阵营是否敌对

    #     Args:
    #         faction_id1: 第一个阵营ID
    #         faction_id2: 第二个阵营ID

    #     Returns:
    #         bool: 如果关系值小于0则为敌对
    #     """
    #     return self.get_faction_relation(faction_id1, faction_id2) < 0

    # def reset_unit_counts(self) -> None:
    #     """重置所有阵营的单位计数，用于地图重生成后"""
    #     for faction_id in self.factions:
    #         faction_entity = self.factions[faction_id]["entity"]
    #         faction_comp = self.world.get_component(faction_entity, FactionComponent)
    #         if faction_comp:
    #             faction_comp.unit_count = 0
    #             self.factions[faction_id]["units"] = []
