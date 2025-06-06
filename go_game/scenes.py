"""
围棋游戏场景
"""

import pygame
from framework_v2.engine.scenes import Scene
from framework_v2 import World
from .systems import (
    InputSystem,
    BoardSystem,
    GameLogicSystem,
    AISystem,
    BoardRenderSystem,
    StoneRenderSystem,
    UIRenderSystem,
    UISystem,
    MenuRenderSystem,
    TerritorySystem,
    UIButtonSystem,
)
from .components import (
    GameState,
    StoneColor,
    GameBoard,
    GameStats,
    AIPlayer,
    UIState,
    MouseState,
    BoardRenderer,
    StoneRenderer,
    Renderable,
    GameResultDialog,
)

from framework_v2.engine.scenes import scene_manager
from framework_v2.engine.events import EventBus
from framework_v2.engine.engine_event import KeyDownEvent


class GameScene(Scene):
    """游戏场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.world = World()

    def enter(self, **kwargs):
        super().enter(**kwargs)

        # 初始化单例组件
        self._initialize_game_components()

        # 添加系统
        input_system = InputSystem()
        board_system = BoardSystem()
        game_logic_system = GameLogicSystem()
        ai_system = AISystem()
        territory_system = TerritorySystem()
        board_render_system = BoardRenderSystem()
        stone_render_system = StoneRenderSystem()
        ui_render_system = UIRenderSystem()
        ui_system = UISystem()
        ui_button_system = UIButtonSystem()

        self.world.add_system(input_system)
        self.world.add_system(board_system)
        self.world.add_system(game_logic_system)
        self.world.add_system(ai_system)
        self.world.add_system(territory_system)
        self.world.add_system(board_render_system)
        self.world.add_system(stone_render_system)
        self.world.add_system(ui_render_system)
        self.world.add_system(ui_system)
        self.world.add_system(ui_button_system)

        # 订阅事件
        input_system.subscribe_events()
        ui_button_system.subscribe_events()

        self.subscribe_events()

        print("进入围棋游戏")

    def _initialize_game_components(self):
        """初始化游戏组件"""
        # 游戏棋盘
        if not self.world.get_singleton_component(GameBoard):
            self.world.add_singleton_component(GameBoard())

        # 游戏状态
        if not self.world.get_singleton_component(GameState):
            self.world.add_singleton_component(GameState())

        # 游戏统计
        if not self.world.get_singleton_component(GameStats):
            self.world.add_singleton_component(GameStats())

        # AI玩家
        if not self.world.get_singleton_component(AIPlayer):
            self.world.add_singleton_component(AIPlayer())

        # UI状态
        if not self.world.get_singleton_component(UIState):
            self.world.add_singleton_component(UIState())

        # 鼠标状态
        if not self.world.get_singleton_component(MouseState):
            self.world.add_singleton_component(MouseState())

        # 游戏结果对话框
        if not self.world.get_singleton_component(GameResultDialog):
            self.world.add_singleton_component(GameResultDialog())

        # 创建棋盘渲染器实体
        board_entity = self.world.create_entity()
        self.world.add_component(board_entity, BoardRenderer())
        self.world.add_component(board_entity, Renderable(layer=0))

        # 创建棋子渲染器实体
        stone_entity = self.world.create_entity()
        self.world.add_component(stone_entity, StoneRenderer())
        self.world.add_component(stone_entity, Renderable(layer=1))

    def exit(self):
        super().exit()
        print("退出围棋游戏")

    def update(self, delta_time: float):
        if self.world:
            self.world.update(delta_time)

    def subscribe_events(self):
        """订阅事件"""
        EventBus().subscribe(KeyDownEvent, self.handle_event)

    def handle_event(self, event) -> bool:
        if event.key == pygame.K_ESCAPE:
            scene_manager().switch_to("menu")
            return True
        elif event.key == pygame.K_r:
            # 重新开始游戏
            self.restart_game()
            return True
        elif event.key == pygame.K_p:
            # Pass回合
            self.pass_turn()
            return True

        return False

    def restart_game(self):
        """重新开始游戏"""
        if self.world:
            # 重置游戏状态
            game_state = self.world.get_singleton_component(GameState)
            if game_state:
                game_state.current_player = StoneColor.BLACK
                game_state.game_phase = "playing"
                game_state.winner = None
                game_state.move_count = 0
                game_state.pass_count = 0

            # 清除所有棋子实体
            from .components import Stone, Position

            for entity_id in list(self.world.get_entities_with_component(Stone)):
                self.world.destroy_entity(entity_id)

            # 重置棋盘
            from .components import GameBoard, GameStats

            board = self.world.get_singleton_component(GameBoard)
            if board:
                board.board = [[StoneColor.EMPTY for _ in range(19)] for _ in range(19)]

            # 重置统计
            stats = self.world.get_singleton_component(GameStats)
            if stats:
                stats.black_captures = 0
                stats.white_captures = 0
                stats.moves_history = []

    def pass_turn(self):
        """跳过回合"""
        if self.world:
            for system in self.world.systems:
                if hasattr(system, "pass_turn"):
                    system.pass_turn()
                    break


class MenuScene(Scene):
    """主菜单场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.world = World()

    def enter(self, **kwargs):
        super().enter(**kwargs)

        # 添加菜单渲染系统
        menu_render_system = MenuRenderSystem()
        self.world.add_system(menu_render_system)

        print("进入主菜单")

    def exit(self):
        super().exit()
        print("退出主菜单")

    def update(self, delta_time: float):
        if self.world:
            self.world.update(delta_time)
