from framework.core.ecs.world import World
from framework.managers.events import EventManager
import json
from rotk.logics.components import FactionComponent


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
        return faction_entity
