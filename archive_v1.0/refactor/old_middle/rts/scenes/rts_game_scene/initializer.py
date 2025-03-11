import math
from rts.components import FactionComponent, ResourceComponent


class RTSSceneInitializer:
    """
    RTS场景初始化器：负责所有游戏场景的初始化逻辑
    将所有初始化逻辑从主游戏场景中分离出来
    """

    def __init__(self, scene):
        """
        初始化场景初始化器

        参数:
            scene: RTSGameScene实例，提供对游戏资源和系统的访问
        """
        self.scene = scene
        self.debug_mode = (
            self.scene.debug_mode if hasattr(self.scene, "debug_mode") else False
        )

    def initialize_world(self):
        """初始化游戏世界和系统"""
        from rts.systems import (
            FactionSystem,
            ResourceSystem,
            UnitSystem,
            BuildingSystem,
            CombatSystem,
            UnitControlSystem,
        )
        from rts.factories import ResourceFactory, UnitFactory, BuildingFactory

        # 清空现有实体
        self.scene.game.world.entities.clear()

        # 注册RTS特定的系统
        self.scene.faction_system = FactionSystem()
        self.scene.resource_system = ResourceSystem()
        self.scene.unit_system = UnitSystem()
        self.scene.building_system = BuildingSystem()
        self.scene.combat_system = CombatSystem()
        self.scene.unit_control_system = UnitControlSystem()

        self.scene.game.world.register_system(self.scene.faction_system)
        self.scene.game.world.register_system(self.scene.resource_system)
        self.scene.game.world.register_system(self.scene.unit_system)
        self.scene.game.world.register_system(self.scene.building_system)
        self.scene.game.world.register_system(self.scene.unit_control_system)
        self.scene.game.world.register_system(self.scene.combat_system)
        self.scene.game.world.register_system(self.scene.victory_system)

        # 初始化工厂，传入游戏实例
        self.scene.resource_factory = ResourceFactory(self.scene.game.world)
        self.scene.unit_factory = UnitFactory(self.scene.game.world, self.scene.game)
        self.scene.building_factory = BuildingFactory(
            self.scene.game.world, self.scene.game
        )

        if self.debug_mode:
            print(
                f"游戏世界初始化完成，共注册了 {len(self.scene.game.world.systems)} 个系统"
            )

    def setup_initial_state(self):
        """设置游戏初始状态"""
        # 创建阵营
        faction_definitions = self.scene.faction_manager.get_faction_definitions()
        self.scene.faction_system.initialize_factions(faction_definitions)

        # 生成资源节点
        resource_nodes = self.scene.resource_factory.create_random_resources(
            self.scene.map_manager.map_data, 10
        )

        # 注册资源节点到资源系统
        for node in resource_nodes:
            self.scene.resource_system.register_resource_node(node)

        # 设置实体管理器的资源节点
        self.scene.entity_manager.set_resource_nodes(resource_nodes)

        # 设置战斗系统的地图数据
        self.scene.unit_system.set_map_data(self.scene.map_manager.map_data)
        self.scene.combat_system.set_map_data(self.scene.map_manager.map_data)
        self.scene.combat_system.add_death_callback(self.scene._handle_entity_death)

        # 创建初始单位和建筑
        self.create_initial_units_and_buildings()

        # 打印阵营信息到控制台（调试用）
        player_faction = self.scene.faction_system.get_player_faction()
        if player_faction and self.debug_mode:
            faction_comp = player_faction.get_component(FactionComponent)
            print(
                f"玩家阵营: {faction_comp.faction_name} (ID: {faction_comp.faction_id})"
            )

            if player_faction.has_component(ResourceComponent):
                res_comp = player_faction.get_component(ResourceComponent)
                print(
                    f"初始资源: 金币={res_comp.gold}, 武器={res_comp.weapons}, "
                    f"食物={res_comp.food}, 辎重={res_comp.supplies}"
                )

    def create_initial_units_and_buildings(self):
        """创建玩家和AI的初始单位和建筑"""
        # 获取阵营ID
        player_faction = self.scene.faction_system.get_player_faction()
        ai_factions = []

        # 遍历所有阵营实体，识别AI阵营
        for entity in self.scene.faction_system.entities:
            faction_comp = entity.get_component(FactionComponent)
            if not faction_comp.is_player:
                ai_factions.append(entity)

        # 检查玩家阵营是否存在
        if not player_faction:
            print("错误: 未找到玩家阵营!")
            return

        # 获取玩家阵营ID
        player_faction_comp = player_faction.get_component(FactionComponent)
        player_faction_id = player_faction_comp.faction_id

        # 获取地图大小
        map_width = self.scene.map_manager.map_data.width
        map_height = self.scene.map_manager.map_data.height

        # 创建玩家基地和单位
        self._create_player_base_and_units(player_faction_id, map_width, map_height)

        # 创建AI基地和单位
        self._create_ai_base_and_units(ai_factions, map_width, map_height)

    def _create_player_base_and_units(self, player_faction_id, map_width, map_height):
        """创建玩家基地和单位"""
        # 为玩家基地寻找合适的位置（在地图左侧四分之一处）
        player_base_x, player_base_y = self._find_suitable_location(
            int(map_width * 0.25), int(map_height * 0.5), 5
        )

        # 创建玩家总部（将格子坐标乘以32转换为像素坐标）
        player_hq = self.scene.building_factory.create_headquarters(
            player_faction_id,
            player_base_x * 32,  # 转换为像素坐标
            player_base_y * 32,
        )

        # 为玩家创建一些初始单位
        self.scene.player_units = []
        unit_types = [
            "plains",
            "plains",
            "plains",  # 3个基础单位（适合平原地形）
            "ranged",  # 1个远程单位
            "supply",  # 1个辎重单位（补给运输）
        ]

        # 围绕总部环形部署单位
        for i, unit_type in enumerate(unit_types):
            # 计算单位位置，形成围绕总部的圆形阵列
            angle = (2 * math.pi * i) / len(unit_types)
            offset_x = int(80 * math.cos(angle))  # 80像素的半径
            offset_y = int(80 * math.sin(angle))

            unit_x = player_base_x * 32 + offset_x
            unit_y = player_base_y * 32 + offset_y

            # 根据类型创建不同种类的单位
            unit = None
            if unit_type == "plains":
                unit = self.scene.unit_factory.create_plains_unit(
                    player_faction_id, unit_x, unit_y
                )
            elif unit_type == "ranged":
                unit = self.scene.unit_factory.create_ranged_unit(
                    player_faction_id, unit_x, unit_y
                )
            elif unit_type == "supply":
                unit = self.scene.unit_factory.create_supply_unit(
                    player_faction_id, unit_x, unit_y
                )

            # 将创建的单位添加到玩家单位列表中
            if unit:
                self.scene.player_units.append(unit)

    def _create_ai_base_and_units(self, ai_factions, map_width, map_height):
        """创建AI基地和单位"""
        # 创建AI基地和单位(如果存在AI阵营)
        self.scene.ai_units = []
        for i, ai_faction in enumerate(ai_factions):
            if i >= 1:  # 目前限制为1个AI阵营
                break

            # 获取AI阵营ID
            ai_faction_comp = ai_faction.get_component(FactionComponent)
            ai_faction_id = ai_faction_comp.faction_id

            # AI基地在地图右侧四分之三处
            ai_base_x, ai_base_y = self._find_suitable_location(
                int(map_width * 0.75), int(map_height * 0.5), 5
            )

            # 创建AI总部
            ai_hq = self.scene.building_factory.create_headquarters(
                ai_faction_id, ai_base_x * 32, ai_base_y * 32
            )

            # 创建一些AI单位，比玩家配置略有不同
            ai_unit_types = [
                "plains",
                "plains",
                "mountain",
                "ranged",
            ]  # 山地单位代替辎重单位

            # 围绕AI基地环形部署单位
            for j, unit_type in enumerate(ai_unit_types):
                angle = (2 * math.pi * j) / len(ai_unit_types)
                offset_x = int(80 * math.cos(angle))
                offset_y = int(80 * math.sin(angle))

                unit_x = ai_base_x * 32 + offset_x
                unit_y = ai_base_y * 32 + offset_y

                # 根据类型创建不同单位
                unit = None
                if unit_type == "plains":
                    unit = self.scene.unit_factory.create_plains_unit(
                        ai_faction_id, unit_x, unit_y
                    )
                elif unit_type == "mountain":
                    unit = self.scene.unit_factory.create_mountain_unit(
                        ai_faction_id, unit_x, unit_y
                    )
                elif unit_type == "ranged":
                    unit = self.scene.unit_factory.create_ranged_unit(
                        ai_faction_id, unit_x, unit_y
                    )

                # 将创建的单位添加到AI单位列表中
                if unit:
                    self.scene.ai_units.append(unit)

    def _find_suitable_location(self, start_x, start_y, radius=3):
        """为建筑/单位寻找合适(可通行)的位置"""
        # 检查起始位置是否合适
        if self.scene.map_manager.is_valid_position(start_x, start_y):
            tile = self.scene.map_manager.get_tile(start_x, start_y)
            if tile and tile.passable:
                return start_x, start_y

        # 在扩展的圆圈中搜索
        for r in range(1, radius + 3):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    # 仅检查圆周上的点
                    if abs(dx) == r or abs(dy) == r:
                        x = start_x + dx
                        y = start_y + dy

                        if self.scene.map_manager.is_valid_position(x, y):
                            tile = self.scene.map_manager.get_tile(x, y)
                            if tile and tile.passable:
                                return x, y

        # 如果没有找到合适的位置，返回原始位置
        return start_x, start_y
