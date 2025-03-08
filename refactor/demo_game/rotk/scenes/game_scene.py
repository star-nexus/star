import pygame
import random
import time
import math
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from rotk.systems import (
    MapSystem,
    FactionSystem,
    UnitSystem,
    CombatSystem,
    RenderSystem,
    HumanControlSystem,
)
from rotk.managers import (
    MapManager,
    CameraManager,
    UnitManager,
    FactionManager,
    ControlManager,
)
from rotk.components import (
    MapComponent,
    PositionComponent,
    UnitPositionComponent,
    UnitType,
    HumanControlComponent,
    TerrainType,
)
from rotk.configs import UNIT_CONFIGS
from framework.managers.events import Message


class GameScene(Scene):
    """游戏主场景，负责初始化游戏实体"""

    def __init__(self, engine):
        super().__init__(engine)
        self.map_system = None
        self.faction_system = None
        self.unit_system = None
        self.combat_system = None
        self.human_control_system = None
        self.map_manager = None
        self.camera_manager = None
        self.player_faction_id = 2  # 默认玩家为蜀国
        self.player_units = []  # 玩家控制的单位列表

        # 新增配置项: 各阵营的部队数量
        self.unit_count_config = {
            1: {"infantry": 9, "ranged": 5, "cavalry": 3},  # 魏国
            2: {"infantry": 9, "ranged": 5, "cavalry": 0},  # 蜀国
            3: {"infantry": 0, "ranged": 7, "cavalry": 3},  # 吴国
            4: {"infantry": 3, "ranged": 0, "cavalry": 0},  # 黄巾军
        }

        # 单位间距配置
        self.unit_spacing = 40.0  # 默认间距（米）

    def enter(self) -> None:
        """场景进入时调用"""
        # 创建相机管理器
        self.camera_manager = CameraManager(self.engine.width, self.engine.height)

        # 创建地图管理器
        self.map_manager = MapManager()
        self.control_manager = ControlManager()
        self.control_manager.create_human_control(self.world)
        self.unit_manager = UnitManager(
            self.world,
            self.engine.event_manager,
        )

        # 初始化阵营系统
        self.faction_system = FactionSystem()
        self.faction_system.initialize(self.engine.event_manager)
        self.world.add_system(self.faction_system)

        # 初始化单位系统
        self.unit_system = UnitSystem()
        self.unit_system.initialize(
            self.world,
            self.engine.event_manager,
            UNIT_CONFIGS,  # 传入单位配置
        )
        self.world.add_system(self.unit_system)

        # 初始化地图系统
        self.map_system = MapSystem()
        self.map_system.initialize(
            self.world, self.engine.event_manager, self.camera_manager
        )
        # 设置玩家阵营ID
        self.map_system.player_faction_id = self.player_faction_id
        self.world.add_system(self.map_system)

        # 创建和初始化地图
        self.map_manager.create_map(self.world, width=50, height=50)

        # 初始化战斗系统
        self.combat_system = CombatSystem()
        self.combat_system.initialize(
            self.world,
            self.engine.event_manager,
            self.map_manager,
            self.faction_system,
            self.unit_system,
        )
        self.world.add_system(self.combat_system)

        # 初始化人类控制系统 (新增)
        self.human_control_system = HumanControlSystem()
        self.human_control_system.initialize(
            self.world, self.engine.event_manager, self.camera_manager
        )
        self.world.add_system(self.human_control_system)

        # 初始化渲染系统，确保它与地图系统使用同一玩家阵营ID
        self.render_system = RenderSystem()
        self.render_system.initialize(
            self.world, self.engine.event_manager, self.camera_manager
        )
        self.render_system.player_faction_id = self.player_faction_id  # 确保同步
        self.world.add_system(self.render_system)

        # 通知渲染系统当前阵营
        self.engine.event_manager.publish(
            "FACTION_SWITCHED",
            Message(
                topic="FACTION_SWITCHED",
                data_type="faction_event",
                data={
                    "faction_id": self.player_faction_id,
                    "faction_name": "蜀国",  # 默认为蜀国
                },
            ),
        )

        # 创建一些测试单位
        self._create_test_units()

        # 订阅空格键事件，用于重新生成地图
        self.engine.event_manager.subscribe("KEYDOWN", self._handle_global_input)

        print("游戏场景已加载。")
        print("控制说明:")
        print("- 使用鼠标点击选择己方单位")
        print("- 点击空地移动选中的单位")
        print("- 选择己方单位后点击敌方单位进行攻击")
        print("- 按空格键重新生成地图")
        print("- 按1、2、3、4切换控制阵营 (1-魏 2-蜀 3-吴 4-黄巾)")
        print("- 按住鼠标中键拖动地图")
        print("- 使用+/-缩放视图")
        print("初始控制阵营: 蜀国(红色)")

    def exit(self) -> None:
        """场景退出时调用"""
        # 取消订阅
        self.engine.event_manager.unsubscribe("KEYDOWN", self._handle_global_input)

        # 清理资源
        if self.map_system:
            self.world.remove_system(self.map_system)
            self.map_system = None

        if self.faction_system:
            self.world.remove_system(self.faction_system)
            self.faction_system = None

        if self.unit_system:
            self.world.remove_system(self.unit_system)
            self.unit_system = None

        if self.combat_system:
            self.world.remove_system(self.combat_system)
            self.combat_system = None

        if self.human_control_system:
            self.world.remove_system(self.human_control_system)
            self.human_control_system = None

        if self.render_system:
            self.world.remove_system(self.render_system)
            self.render_system = None

        self.map_manager = None
        self.camera_manager = None
        self.player_units = []

    def update(self, delta_time: float) -> None:
        """更新场景逻辑"""
        # 场景特定的逻辑可以在这里添加
        pass

    def render(self, render_manager) -> None:
        """渲染场景"""
        # 绘制背景
        render_manager.set_layer(0)
        bg_color = (10, 20, 30)  # 深蓝色背景
        rect = pygame.Rect(0, 0, self.engine.width, self.engine.height)
        render_manager.draw_rect(bg_color, rect)

        # 渲染系统已经处理了地图和实体的渲染

    def _handle_global_input(self, message):
        """处理全局输入事件，如空格键重新生成地图"""
        if message.topic == "KEYDOWN" and message.data == pygame.K_SPACE:
            self._regenerate_map()

    def _regenerate_map(self):
        """重新生成地图的协调函数"""
        # 清空所有单位
        for entity in self.world.get_entities_with_components(UnitPositionComponent):
            self.world.remove_entity(entity)

        self.player_units = []

        # 清空地图系统中的选择
        if hasattr(self.map_system, "_clear_selection"):
            self.map_system._clear_selection()

        # 清除人类控制器的选择状态
        hc_entity = self.world.get_unique_entity(HumanControlComponent)
        if hc_entity:
            hc_comp = self.world.get_component(hc_entity, HumanControlComponent)
            if hasattr(hc_comp, "_clear_selection"):
                hc_comp._clear_selection()
            else:
                # 直接设置选择相关属性为None
                hc_comp.selected_unit = None
                hc_comp.target_unit = None
                hc_comp.move_target = None
                hc_comp.selected_position = None

        # 重新生成地图
        self.map_manager.regenerate_map(self.world)

        # 创建新的测试单位
        self._create_test_units()

        print("地图已重新生成!")

    def _create_test_units(self):
        """创建测试用的阵营单位，在随机但战略合理的位置"""
        # 获取地图尺寸
        map_entity = self.world.get_entities_with_components(MapComponent)
        map_comp = self.world.get_component(map_entity[0], MapComponent)
        if not map_comp:
            return

        map_width, map_height = map_comp.width, map_comp.height

        # 首先创建各个阵营
        self.faction_manager = FactionManager(self.world, self.engine.event_manager)

        # 为每个阵营定义生成区域 - 确保各阵营初始位置有所区分但又有随机性
        # 将地图分成四个区域：西北、东北、西南、东南
        regions = {
            # 魏国在地图西部(随机选择西北或西南)
            1: {
                "x_range": (map_width // 8, map_width // 3),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
            # 蜀国在地图东部(随机选择东北或东南)
            2: {
                "x_range": (map_width * 2 // 3, map_width * 7 // 8),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
            # 吴国在地图南部(随机选择东南或西南的南部区域)
            3: {
                "x_range": (map_width // 8, map_width * 7 // 8),
                "y_range": (map_height * 2 // 3, map_height * 7 // 8),
            },
            # 黄巾军可以在整个地图上随机分布
            4: {
                "x_range": (map_width // 8, map_width * 7 // 8),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
        }

        # 查找可行走的位置作为各阵营中心点
        faction_centers = {}
        for faction_id, region in regions.items():
            # 尝试多次找到合适的区域中心
            for attempt in range(10):
                center_x = random.randint(region["x_range"][0], region["x_range"][1])
                center_y = random.randint(region["y_range"][0], region["y_range"][1])

                # 确保区域中心点地形适合生成单位(不是水域等不可通行地形)
                if self._is_valid_spawn_position(map_comp, center_x, center_y):
                    # 为该阵营设置中心点
                    faction_centers[faction_id] = (center_x, center_y)
                    break
                # 如果多次尝试后仍找不到合适位置，使用区域中心点
                if attempt == 9:
                    center_x = (region["x_range"][0] + region["x_range"][1]) // 2
                    center_y = (region["y_range"][0] + region["y_range"][1]) // 2
                    faction_centers[faction_id] = (center_x, center_y)

        # 为三个主要阵营创建单位
        # 魏国单位 (阵营ID: 1)
        wei_center_x, wei_center_y = faction_centers[1]
        wei_config = self.unit_count_config[1]

        # 创建盾兵方阵
        offset_angle = random.uniform(0, 2 * math.pi)  # 随机偏移角度
        offset_distance = random.randint(2, 4)  # 随机偏移距离
        shield_pos_x = wei_center_x + math.cos(offset_angle) * offset_distance
        shield_pos_y = wei_center_y + math.sin(offset_angle) * offset_distance
        wei_shield_units = self.unit_manager.create_unit_formation(
            UnitType.SHIELD_INFANTRY,
            1,
            shield_pos_x,
            shield_pos_y,
            wei_config["infantry"],
            self.unit_spacing,
            random.choice(["square", "staggered"]),
        )

        # 创建弓箭手
        offset_angle = random.uniform(0, 2 * math.pi)  # 随机不同方向
        offset_distance = random.randint(2, 4)
        archer_pos_x = wei_center_x + math.cos(offset_angle) * offset_distance
        archer_pos_y = wei_center_y + math.sin(offset_angle) * offset_distance
        wei_archer_units = self.unit_manager.create_unit_formation(
            UnitType.ARCHER,
            1,
            archer_pos_x,
            archer_pos_y,
            wei_config["ranged"],
            self.unit_spacing,
            random.choice(["line", "staggered"]),
        )

        # 创建骑兵
        offset_angle = random.uniform(0, 2 * math.pi)  # 再一个随机方向
        offset_distance = random.randint(2, 4)
        cavalry_pos_x = wei_center_x + math.cos(offset_angle) * offset_distance
        cavalry_pos_y = wei_center_y + math.sin(offset_angle) * offset_distance
        wei_cavalry = self.unit_manager.create_unit_formation(
            UnitType.HEAVY_CAVALRY,
            1,
            cavalry_pos_x,
            cavalry_pos_y,
            wei_config["cavalry"],
            self.unit_spacing,
            random.choice(["wedge", "line"]),
        )

        # 蜀国单位 (阵营ID: 2，玩家阵营)
        shu_center_x, shu_center_y = faction_centers[2]
        shu_config = self.unit_count_config[2]

        # 蜀国创建长戟兵
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.randint(2, 4)
        spear_pos_x = shu_center_x + math.cos(offset_angle) * offset_distance
        spear_pos_y = shu_center_y + math.sin(offset_angle) * offset_distance
        shu_spear_units = self.unit_manager.create_unit_formation(
            UnitType.SPEAR_INFANTRY,
            2,
            spear_pos_x,
            spear_pos_y,
            shu_config["infantry"],
            self.unit_spacing,
            random.choice(["staggered", "square"]),
        )

        # 蜀国创建弩手
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.randint(2, 4)
        crossbow_pos_x = shu_center_x + math.cos(offset_angle) * offset_distance
        crossbow_pos_y = shu_center_y + math.sin(offset_angle) * offset_distance
        shu_crossbow_units = self.unit_manager.create_unit_formation(
            UnitType.CROSSBOWMAN,
            2,
            crossbow_pos_x,
            crossbow_pos_y,
            shu_config["ranged"],
            self.unit_spacing,
            random.choice(["line", "staggered"]),
        )

        # 记录玩家单位
        self.player_units = shu_spear_units + shu_crossbow_units

        # 吴国单位 (阵营ID: 3)
        wu_center_x, wu_center_y = faction_centers[3]
        wu_config = self.unit_count_config[3]

        # 吴国创建骑射手
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.randint(2, 4)
        mounted_pos_x = wu_center_x + math.cos(offset_angle) * offset_distance
        mounted_pos_y = wu_center_y + math.sin(offset_angle) * offset_distance
        wu_mounted_archers = self.unit_manager.create_unit_formation(
            UnitType.MOUNTED_ARCHER,
            3,
            mounted_pos_x,
            mounted_pos_y,
            wu_config["ranged"],
            self.unit_spacing,
            random.choice(["line", "circle"]),
        )

        # 吴国创建斥候骑兵
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.randint(2, 4)
        scout_pos_x = wu_center_x + math.cos(offset_angle) * offset_distance
        scout_pos_y = wu_center_y + math.sin(offset_angle) * offset_distance
        wu_scouts = self.unit_manager.create_unit_formation(
            UnitType.SCOUT_CAVALRY,
            3,
            scout_pos_x,
            scout_pos_y,
            wu_config["cavalry"],
            self.unit_spacing,
            random.choice(["wedge", "circle"]),
        )

        # 黄巾军单位 (阵营ID: 4) - 随机放置
        rebel_config = self.unit_count_config[4]
        rebel_count = rebel_config["infantry"]

        # 随机分布几个小队黄巾军
        rebel_center_x, rebel_center_y = faction_centers[4]
        for i in range(min(3, max(1, rebel_count // 3))):  # 至少1个小队，最多3个
            # 在黄巾中心点附近随机生成位置
            offset_angle = random.uniform(0, 2 * math.pi)
            offset_distance = random.randint(3, 8)  # 距离可以稍远些，更分散
            rebel_x = rebel_center_x + math.cos(offset_angle) * offset_distance
            rebel_y = rebel_center_y + math.sin(offset_angle) * offset_distance

            # 确保位置有效
            if not self._is_valid_spawn_position(map_comp, rebel_x, rebel_y):
                rebel_x = rebel_center_x
                rebel_y = rebel_center_y

            unit_type = random.choice(
                [UnitType.SHIELD_INFANTRY, UnitType.ARCHER, UnitType.SPEAR_INFANTRY]
            )

            # 创建小群黄巾军
            count = max(1, rebel_count // (4 - i))  # 分配单位到各小队
            rebel_count -= count

            self.unit_manager.create_unit_formation(
                unit_type,
                4,
                rebel_x,
                rebel_y,
                count,
                self.unit_spacing,
                random.choice(["square", "circle", "staggered"]),
            )

        # 确保相机位于玩家单位中心
        if self.player_units and self.camera_manager:
            # 获取第一个玩家单位的位置
            first_unit = self.player_units[0]
            pos = self.world.get_component(first_unit, UnitPositionComponent)
            if pos:
                # 设置相机中心位置
                world_x = pos.x * map_comp.cell_size
                world_y = pos.y * map_comp.cell_size

                # 将相机中心点设置为玩家位置
                center_x = world_x - self.camera_manager.screen_width / (
                    2 * self.camera_manager.zoom
                )
                center_y = world_y - self.camera_manager.screen_height / (
                    2 * self.camera_manager.zoom
                )

                self.camera_manager.set_position(center_x, center_y)
                self.camera_manager.constrain(
                    map_comp.width * map_comp.cell_size,
                    map_comp.height * map_comp.cell_size,
                    map_comp.cell_size,
                )

        print(f"创建了玩家单位: {len(self.player_units)}")

    def _is_valid_spawn_position(self, map_comp, x: float, y: float) -> bool:
        """检查位置是否适合生成单位"""
        # 转换为整数坐标
        grid_x = int(x)
        grid_y = int(y)

        # 检查边界
        if (
            grid_x < 0
            or grid_x >= map_comp.width
            or grid_y < 0
            or grid_y >= map_comp.height
        ):
            return False

        # 检查地形是否可通行
        terrain_type = map_comp.grid[grid_y][grid_x]
        if terrain_type in [
            TerrainType.OCEAN,
            TerrainType.LAKE,
            TerrainType.RIVER,
            TerrainType.SWAMP,
            TerrainType.MOUNTAIN,
        ]:
            return False

        # 避免生成在城市上
        if terrain_type == TerrainType.CITY:
            return False

        return True
