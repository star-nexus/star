import pygame
from engine.scene_base import BaseScene
from .player_controller import PlayerController
from .enemy_controller import EnemyController
from .map_handler import MapHandler
from .ui_controller import UIController
from .input_handler import InputHandler
from factories.entity_factory import EntityFactory


class GameScene(BaseScene):
    """游戏主场景，使用多个控制器管理游戏逻辑"""

    def __init__(self, engine):
        super().__init__(engine)
        self.player_controller = None
        self.enemy_controller = None
        self.map_handler = None
        self.ui_controller = None
        self.input_handler = None
        self.score = 0
        self.game_over = False
        self.victory_font = None
        self.instruction_font = None
        self.entity_factory = EntityFactory(engine)  # 创建实体工厂

    def initialize(self) -> None:
        """初始化游戏场景"""
        super().initialize()

        # 清空场景中的所有实体
        self.entities = []

        # 重置游戏状态
        self.score = 0
        self.game_over = False

        # 初始化字体
        self.victory_font = pygame.font.SysFont("arial", 64)
        self.instruction_font = pygame.font.SysFont("arial", 32)

        # 创建控制器
        self.map_handler = MapHandler(self)
        self.player_controller = PlayerController(self)
        self.enemy_controller = EnemyController(self)
        self.ui_controller = UIController(self)
        self.input_handler = InputHandler(self)

        # 初始化控制器 - 调整初始化顺序
        self.player_controller.initialize()  # 先初始化玩家
        self.map_handler.initialize()  # 再初始化地图
        self.enemy_controller.initialize()
        self.input_handler.initialize()
        self.ui_controller.initialize()  # UI应该最后初始化，因为它依赖于其他控制器的数据

    def setup_ui(self) -> None:
        """设置游戏UI"""
        if self.ui_controller:
            self.ui_controller._setup_ui()

    def update(self, delta_time: float) -> None:
        """更新游戏场景"""
        if self.game_over:
            return

        # 检查游戏状态是否为暂停状态
        if (
            hasattr(self.engine, "game_state_manager")
            and self.engine.game_state_manager.current_state == "paused"
        ):
            # 暂停状态下只更新UI控制器，不更新游戏逻辑
            self.ui_controller.update(delta_time)
            return

        # 更新所有控制器
        self.player_controller.update(delta_time)
        self.enemy_controller.update(delta_time)
        self.map_handler.update(delta_time)
        self.ui_controller.update(delta_time)

        # 更新相机
        self._update_camera()

    def _update_camera(self) -> None:
        """更新相机位置"""
        if self.player_controller and self.player_controller.player:
            screen_width, screen_height = self.engine.screen.get_size()
            self.center_camera_on_entity(
                self.player_controller.player, screen_width, screen_height
            )

    def render(self, surface: pygame.Surface) -> None:
        """渲染游戏场景"""
        # 调用父类渲染方法，渲染地图和实体
        super().render(surface)

        # 如果游戏结束，渲染游戏结束界面
        if self.game_over:
            self.ui_controller.render_game_over(surface)

    def handle_victory(self) -> None:
        """处理游戏胜利"""
        if self.engine.debug_mode:
            print("游戏胜利!")

        # 使用游戏状态管理器切换到胜利状态
        if hasattr(self.engine, "game_state_manager"):
            # 保存玩家位置
            if self.player_controller.player:
                self.update_game_data(
                    "player_position",
                    (self.player_controller.player.x, self.player_controller.player.y),
                )
            self.engine.game_state_manager.change_state("victory")
        else:
            # 兼容没有状态管理器的情况
            self.game_over = True

    def toggle_pause(self) -> None:
        """切换游戏暂停状态"""
        if hasattr(self.engine, "game_state_manager"):
            current_state = self.engine.game_state_manager.current_state
            if current_state == "playing":
                self.engine.game_state_manager.change_state("paused")
            elif current_state == "paused":
                self.engine.game_state_manager.change_state("playing")

    def on_collision(self, entity1, entity2) -> None:
        """处理实体碰撞"""
        # 检测玩家与敌人的碰撞
        if (entity1.tag == "player" and entity2.tag == "enemy") or (
            entity1.tag == "enemy" and entity2.tag == "player"
        ):
            enemy = entity1 if entity1.tag == "enemy" else entity2
            # 处理敌人被击败
            if self.enemy_controller:
                self.enemy_controller.handle_enemy_defeated(enemy)

    def on_enter(self) -> None:
        """进入场景时调用"""
        super().on_enter()

        # 注册碰撞事件监听
        if hasattr(self.engine, "collision_manager"):
            self.engine.event_manager.add_listener("collision", self.on_collision)
            self.engine.collision_manager.register_collision_group("player", "enemy")

    def on_exit(self) -> None:
        """场景退出时清理资源"""
        # 清理所有控制器
        if self.player_controller:
            self.player_controller.cleanup()
        if self.enemy_controller:
            self.enemy_controller.cleanup()
        if self.map_handler:
            self.map_handler.cleanup()
        if self.ui_controller:
            self.ui_controller.cleanup()
        if self.input_handler:
            self.input_handler.cleanup()

        # 取消注册碰撞组和事件
        if hasattr(self.engine, "collision_manager"):
            self.engine.collision_manager.unregister_collision_group("player", "enemy")
            self.engine.event_manager.remove_listener("collision", self.on_collision)
