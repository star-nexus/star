import pygame
import random
import time
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from rotk.systems import (
    MapSystem,
    EntitySystem,
    MovementSystem,
    FactionSystem,
    UnitSystem,
    CombatSystem,
)
from rotk.managers import MapManager, CameraManager
from rotk.components import (
    MapComponent,
    PositionComponent,
    PrecisePositionComponent,
    UnitType,
)
from rotk.configs import UNIT_CONFIGS


class GameScene(Scene):
    """游戏主场景，负责初始化游戏实体"""

    def __init__(self, engine):
        super().__init__(engine)
        self.map_system = None
        self.faction_system = None
        self.unit_system = None
        self.combat_system = None
        self.map_manager = None
        self.camera_manager = None
        self.player_faction_id = 2  # 默认玩家为蜀国
        self.player_units = []  # 玩家控制的单位列表

    def enter(self) -> None:
        """场景进入时调用"""
        # 创建相机管理器
        self.camera_manager = CameraManager(self.engine.width, self.engine.height)

        # 创建地图管理器
        self.map_manager = MapManager()

        # 初始化阵营系统
        self.faction_system = FactionSystem()
        self.faction_system.initialize(self.world, self.engine.event_manager)
        self.world.add_system(self.faction_system)

        # 初始化单位系统
        self.unit_system = UnitSystem()
        self.unit_system.initialize(
            self.world,
            self.engine.event_manager,
            self.map_manager,
            self.faction_system,
            UNIT_CONFIGS,  # 传入单位配置
        )
        self.world.add_system(self.unit_system)

        # 初始化地图系统
        self.map_system = MapSystem()
        self.map_system.initialize(
            self.world, self.engine.event_manager, self.map_manager, self.camera_manager
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
        for entity in self.world.get_entities_with_components(PrecisePositionComponent):
            self.world.remove_entity(entity)

        self.player_units = []

        # 清空地图系统中的选择
        if hasattr(self.map_system, "_clear_selection"):
            self.map_system._clear_selection()

        # 重置阵营系统的单位计数
        if hasattr(self.faction_system, "reset_unit_counts"):
            self.faction_system.reset_unit_counts()

        # 重新生成地图
        self.map_manager.regenerate_map(self.world)

        # 创建新的测试单位
        self._create_test_units()

        print("地图已重新生成!")

    def _create_test_units(self):
        """创建测试用的阵营单位"""
        # 获取地图尺寸
        map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
        if not map_comp:
            return

        map_width, map_height = map_comp.width, map_comp.height

        # 为三个主要阵营创建单位
        # 魏国单位 (阵营ID: 1) - 放在地图左侧
        wei_start_x = map_width // 4
        wei_start_y = map_height // 2

        # 魏国创建盾兵方阵
        wei_shield_units = self.unit_system.create_unit_formation(
            UnitType.SHIELD_INFANTRY, 1, wei_start_x, wei_start_y - 3, 9, "square"
        )

        # 魏国创建弓箭手
        wei_archer_units = self.unit_system.create_unit_formation(
            UnitType.ARCHER, 1, wei_start_x - 2, wei_start_y + 3, 5, "line"
        )

        # 魏国创建骑兵
        wei_cavalry = self.unit_system.create_unit_formation(
            UnitType.HEAVY_CAVALRY, 1, wei_start_x + 4, wei_start_y, 3, "wedge"
        )

        # 蜀国单位 (阵营ID: 2，玩家阵营) - 放在地图右侧
        shu_start_x = map_width * 3 // 4
        shu_start_y = map_height // 2

        # 蜀国创建长戟兵
        shu_spear_units = self.unit_system.create_unit_formation(
            UnitType.SPEAR_INFANTRY, 2, shu_start_x, shu_start_y - 2, 9, "square"
        )

        # 蜀国创建弩手
        shu_crossbow_units = self.unit_system.create_unit_formation(
            UnitType.CROSSBOWMAN, 2, shu_start_x + 2, shu_start_y + 3, 5, "line"
        )

        # 蜀国创建山地步兵
        shu_mountain_units = self.unit_system.create_unit_formation(
            UnitType.MOUNTAIN_INFANTRY, 2, shu_start_x - 4, shu_start_y, 3, "wedge"
        )

        # 记录玩家单位
        self.player_units = shu_spear_units + shu_crossbow_units + shu_mountain_units

        # 吴国单位 (阵营ID: 3) - 放在地图下方
        wu_start_x = map_width // 2
        wu_start_y = map_height * 3 // 4

        # 吴国创建骑射手
        wu_mounted_archers = self.unit_system.create_unit_formation(
            UnitType.MOUNTED_ARCHER, 3, wu_start_x, wu_start_y, 7, "line"
        )

        # 吴国创建斥候骑兵
        wu_scouts = self.unit_system.create_unit_formation(
            UnitType.SCOUT_CAVALRY, 3, wu_start_x - 3, wu_start_y - 3, 3, "wedge"
        )

        # 黄巾军单位 (阵营ID: 4) - 随机放置
        for i in range(3):
            # 随机位置
            rebel_x = random.randint(map_width // 4, map_width * 3 // 4)
            rebel_y = random.randint(map_height // 4, map_height * 3 // 4)

            unit_type = random.choice(
                [UnitType.SHIELD_INFANTRY, UnitType.ARCHER, UnitType.SPEAR_INFANTRY]
            )

            # 创建小群黄巾军
            count = random.randint(3, 6)
            self.unit_system.create_unit_formation(
                unit_type, 4, rebel_x, rebel_y, count, "square"
            )

        # 确保相机位于玩家单位中心
        if self.player_units and self.camera_manager:
            # 获取第一个玩家单位的位置
            first_unit = self.player_units[0]
            pos = self.world.get_component(first_unit, PrecisePositionComponent)
            if pos:
                # 设置相机中心位置
                map_comp = self.world.get_component(
                    self.map_manager.map_entity, MapComponent
                )
                if map_comp:
                    world_x = pos.grid_x * map_comp.cell_size
                    world_y = pos.grid_y * map_comp.cell_size

                    # 将相机中心点设置为玩家位置
                    center_x = world_x - self.camera_manager.screen_width / (
                        2 * self.camera_manager.zoom
                    )
                    center_y = world_y - self.camera_manager.screen_height / (
                        2 * self.camera_manager.zoom
                    )

                    self.camera_manager.set_position(center_x, center_y)
                    self.camera_manager.constrain(
                        map_comp.width, map_comp.height, map_comp.cell_size
                    )

        print(f"创建了玩家单位: {len(self.player_units)}")
