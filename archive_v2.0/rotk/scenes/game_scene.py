import pygame
import random
import time
import math
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from rotk.logics.systems import (
    MapSystem,
    FactionSystem,
    UnitSystem,
    CombatSystem,
    RenderSystem,
    HumanControlSystem,
    VictorySystem,
    AIControlSystem,  # 导入AI控制系统
)
from rotk.logics.managers import (
    MapManager,
    CameraManager,
    UnitManager,
    FactionManager,
    ControlManager,
    ScenarioManager,
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
        self.victory_system = None  # 新增胜利系统引用
        self.ai_control_system = None  # 添加AI控制系统引用
        self.map_manager = None
        self.camera_manager = None
        self.player_faction_id = 2  # 默认玩家为蜀国
        self.player_units = []  # 玩家控制的单位列表

        # 新增配置项: 各阵营的部队数量
        self.unit_count_config = {
            1: {"infantry": 1, "ranged": 1, "cavalry": 1},  # 魏国
            2: {"infantry": 1, "ranged": 1, "cavalry": 1},  # 蜀国
            3: {"infantry": 0, "ranged": 7, "cavalry": 3},  # 吴国
            4: {"infantry": 1, "ranged": 0, "cavalry": 0},  # 黄巾军
        }

        # 单位间距配置
        self.unit_spacing = 40.0  # 默认间距（米）
        self.scenario_manager = None  # 新增场景管理器引用

    def enter(self) -> None:
        """场景进入时调用"""
        # 创建相机管理器
        self.camera_manager = CameraManager(self.engine.width, self.engine.height)

        # 创建地图管理器
        self.map_manager = MapManager()
        self.map_manager.initialize(self.world, self.engine.event_manager,)
        self.control_manager = ControlManager()
        self.control_manager.create_human_control(self.world)
        self.faction_manager = FactionManager(
            self.world,
            self.engine.event_manager,
        )
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
            self.unit_system,
        )
        self.world.add_system(self.combat_system)

        # 初始化人类控制系统 (新增)
        self.human_control_system = HumanControlSystem()
        self.human_control_system.initialize(
            self.world, self.engine.event_manager, self.camera_manager
        )
        self.world.add_system(self.human_control_system)

        # 初始化AI控制系统
        self.ai_control_system = AIControlSystem()
        self.ai_control_system.initialize(self.world, self.engine.event_manager)
        self.ai_control_system.player_faction_id = self.player_faction_id
        self.world.add_system(self.ai_control_system)

        # 初始化胜利系统
        self.victory_system = VictorySystem()
        self.victory_system.initialize(
            self.world, self.engine.event_manager, self.engine
        )
        self.victory_system.player_faction_id = self.player_faction_id
        self.world.add_system(self.victory_system)

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
                    "faction_name": "蜀国",  # 更新为蜀国
                },
            ),
        )

        # 创建场景管理器
        self.scenario_manager = ScenarioManager(
            self.world,
            self.engine.event_manager,
            self.unit_manager,
            self.map_manager,
            self.faction_manager,
        )

        # 创建一些测试单位 - 使用场景管理器
        self.player_units = self.scenario_manager.create_test_units(self.camera_manager)

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

        if self.victory_system:
            self.world.remove_system(self.victory_system)
            self.victory_system = None

        if self.ai_control_system:
            self.world.remove_system(self.ai_control_system)
            self.ai_control_system = None

        if self.render_system:
            self.world.remove_system(self.render_system)
            self.render_system = None

        self.map_manager = None
        self.camera_manager = None
        self.player_units = []

    def update(self, delta_time: float) -> None:
        """更新场景逻辑"""
        # 场景特定的逻辑可以在这里添加
        # 注意：移除了对_check_game_end_conditions的调用
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
            # 使用场景管理器重新生成战场
            self.scenario_manager.regenerate_battle_scene(self.camera_manager)
            # 更新玩家单位引用
            self.player_units = self.scenario_manager.player_units
