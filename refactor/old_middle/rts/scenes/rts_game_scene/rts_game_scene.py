import pygame
import math
from framework.scene.scene import Scene
from rts.managers.faction_manager import FactionManager
from rts.scenes.rts_game_scene.ui_manager import RTSUIManager
from rts.scenes.rts_game_scene.input_handler import RTSInputHandler
from rts.scenes.rts_game_scene.map_manager import RTSMapManager
from rts.scenes.rts_game_scene.entity_manager import RTSEntityManager
from rts.scenes.rts_game_scene.combat_manager import RTSCombatManager
from rts.systems.victory_condition_system import (
    VictoryConditionSystem,
    EliminationVictoryCondition,
    ResourceVictoryCondition,
    MainBaseVictoryCondition,
)
from rts.managers.game_state_manager import GameStateManager, GameState
from rts.ui.game_flow_ui import GameFlowUI
from rts.managers.game_events import GameStartEvent, GameOverEvent
from rts.managers.event_manager import EventManager  # Import EventManager directly

# 引入模块化组件
from rts.scenes.rts_game_scene.renderer import RTSGameRenderer
from rts.scenes.rts_game_scene.initializer import RTSSceneInitializer
from rts.scenes.rts_game_scene.updater import RTSSceneUpdater


class RTSGameScene(Scene):
    """
    RTS游戏场景：模块化重构版
    主要负责协调各个子模块和管理场景生命周期
    """

    def __init__(self, game):
        super().__init__(game)
        # 场景状态
        self.initialized = False
        self.debug_mode = False

        # 系统引用（将由初始化器设置）
        self.faction_system = None
        self.resource_system = None
        self.unit_system = None
        self.building_system = None
        self.combat_system = None
        self.unit_control_system = None

        # 阵营管理器
        self.faction_manager = FactionManager()

        # 资源管理（将由初始化器设置）
        self.resource_factory = None
        self.unit_factory = None
        self.building_factory = None

        # 场景速度控制
        self.map_scrolling_speed = 500  # 像素/秒

        # 单位列表
        self.player_units = []
        self.ai_units = []

        # 初始化管理器
        self.ui_manager = RTSUIManager(self)
        self.input_handler = RTSInputHandler(self)
        self.map_manager = RTSMapManager(self)
        self.combat_manager = RTSCombatManager(self)
        self.entity_manager = RTSEntityManager(self)

        # 初始化胜利条件系统
        self.victory_system = VictoryConditionSystem()
        self.victory_system.add_victory_condition(EliminationVictoryCondition())
        self.victory_system.add_victory_condition(
            ResourceVictoryCondition(10000)
        )  # 需要10000金币才能获胜
        self.victory_system.add_victory_condition(MainBaseVictoryCondition())

        # 初始化游戏状态管理器
        self.game_state_manager = GameStateManager.get_instance()

        # 初始化游戏流程UI
        self.game_flow_ui = GameFlowUI(game.screen)

        # 初始化事件管理器
        self.event_manager = EventManager.get_instance()
        self.event_manager.add_listener(
            GameOverEvent, self.game_state_manager.handle_game_over
        )
        self.event_manager.add_listener(GameOverEvent, self.handle_game_over)

        # 设置玩家阵营ID
        self.game_state_manager.set_player_faction(1)

        # 初始化模块化组件
        self.renderer = RTSGameRenderer(self)
        self.initializer = RTSSceneInitializer(self)
        self.updater = RTSSceneUpdater(self)

    def load(self):
        """场景加载时调用"""
        # 确保GameStateManager已正确初始化并设置初始状态
        self.game_state_manager = GameStateManager.get_instance()
        self.game_state_manager.change_state(GameState.PLAYING)

        # 创建游戏界面布局
        self.ui_manager.create_ui()

        # 初始化地图系统
        self.map_manager.initialize()

        # 初始化场景世界（使用模块化初始化器）
        self.initializer.initialize_world()

        # 设置初始游戏状态（使用模块化初始化器）
        self.initializer.setup_initial_state()

        # 标记为已初始化
        self.initialized = True

        # 打印调试信息，确认场景已正确加载
        if self.debug_mode:
            print("RTS游戏场景已加载")
            print(
                f"已注册的系统: {', '.join([type(system).__name__ for system in self.game.world.systems])}"
            )

    def process_event(self, event):
        """处理输入事件"""
        # 使用输入处理器处理事件
        self.input_handler.process_event(event)

        # 让父类继续处理事件
        super().process_event(event)

        # 处理游戏暂停/恢复
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.game_state_manager.is_state(GameState.PLAYING):
                    self.game_state_manager.pause_game()
                elif self.game_state_manager.is_state(GameState.PAUSED):
                    self.game_state_manager.resume_game()

        # 处理游戏流程UI事件
        self.game_flow_ui.handle_event(event)

    def update(self, delta_time):
        """场景更新逻辑"""
        # 使用模块化更新器进行更新
        self.updater.update(delta_time)

    def _handle_entity_death(self, entity):
        """处理实体死亡"""
        # 使用实体管理器标记实体为待移除
        self.entity_manager.mark_entity_for_removal(entity)

    def render(self):
        """场景渲染逻辑"""
        # 使用模块化渲染器进行渲染
        self.renderer.render(self.game.screen)

        # 让父类继续渲染
        super().render()

    def unload(self):
        """场景卸载时调用"""
        # 清空世界
        for entity_id in list(self.game.world.entities.keys()):
            self.game.world.destroy_entity(entity_id)

        # 卸载UI元素
        super().unload()

    def handle_game_over(self, event):
        """处理游戏结束事件"""
        if isinstance(event, GameOverEvent):
            # 转发给GameStateManager
            self.game_state_manager.handle_game_over(event)
