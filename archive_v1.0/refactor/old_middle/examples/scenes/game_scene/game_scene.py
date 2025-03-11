import pygame
from framework.scene.scene import Scene
from .entity_factory import EntityFactory
from .game_scene_logic import GameSceneLogic
from .game_scene_ui import GameSceneUI
from .pause_menu import PauseMenuManager
from examples.systems import (
    MovementSystem,
    InputSystem,
    RenderSystem,
    CollisionSystem,
    GlowSystem,
    EnemySystem,
    HealthSystem,
)


class GameScene(Scene):
    """
    游戏场景 - 重构后的主类，负责协调各个子模块
    """

    def __init__(self, game):
        super().__init__(game)
        # 核心组件
        self.entity_factory = None
        self.game_logic = None
        self.ui_manager = None
        self.pause_menu = None

        # 游戏状态
        self.player = None
        self.obstacles = []
        self.enemies = []
        self.collision_system = None
        self.timer = 30.0
        self.score = 0
        self.enemy_spawn_timer = 0
        self.enemy_spawn_interval = 5.0

        # 存储系统引用
        self.enemy_system = None

    def load(self):
        """加载场景"""
        # 清空世界
        self.game.world.systems.clear()

        # 初始化系统
        self._init_systems()

        # 初始化管理器
        self.entity_factory = EntityFactory(self.game, self.game.world)
        self.game_logic = GameSceneLogic(self.game, self.collision_system)
        self.ui_manager = GameSceneUI(self.game, self)
        self.pause_menu = PauseMenuManager(self.game, self)

        # 创建实体
        self._create_entities()

        # 更新敌人系统的玩家引用
        if self.enemy_system:
            self.enemy_system.player_entity = self.player

        # 设置游戏逻辑引用
        self.game_logic.player = self.player
        self.game_logic.obstacles = self.obstacles
        self.game_logic.enemies = self.enemies

        # 创建UI
        pause_button = self.ui_manager.create_game_ui(
            self.player, self.timer, self.score
        )
        pause_button.callback = self.pause_game

        # 创建暂停菜单
        self.pause_menu.create_pause_menu()
        self.pause_menu.continue_button.callback = self.resume_game
        self.pause_menu.cancel_button.callback = self.resume_game
        self.pause_menu.main_menu_button.callback = self.return_to_menu

        # 重置游戏状态
        self.score = 0
        self.timer = 30.0
        self.enemy_spawn_timer = 0

    def _init_systems(self):
        """初始化游戏系统"""
        input_system = InputSystem(self.game.input)
        render_system = RenderSystem(self.game.screen, self.game.resources)
        movement_system = MovementSystem()
        self.collision_system = CollisionSystem()
        glow_system = GlowSystem()
        health_system = HealthSystem()

        # 创建玩家实体占位，用于敌人系统初始化
        temp_player = self.game.world.create_entity()
        self.enemy_system = EnemySystem(temp_player)

        # 注册系统
        self.game.world.register_system(health_system)
        self.game.world.register_system(input_system)
        self.game.world.register_system(movement_system)
        self.game.world.register_system(self.collision_system)
        self.game.world.register_system(glow_system)
        self.game.world.register_system(self.enemy_system)
        self.game.world.register_system(render_system)

    def _create_entities(self):
        """创建游戏实体"""
        # 移除临时玩家占位符
        if self.player:
            self.game.world.destroy_entity(self.player.id)

        # 创建真正的玩家
        self.player = self.entity_factory.create_player()

        # 创建障碍物
        self.obstacles = self.entity_factory.create_obstacles(5)

        # 初始化敌人列表
        self.enemies = []

    def process_event(self, event):
        """处理输入事件"""
        # 检测ESC键按下事件以暂停/恢复游戏
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.pause_menu.is_paused:
                self.resume_game()
            else:
                self.pause_game()

        super().process_event(event)

    def update(self, delta_time):
        """更新场景"""
        # 如果游戏已暂停，不更新游戏逻辑
        if self.pause_menu.is_paused:
            return

        # 更新世界
        self.game.world.update(delta_time)

        # 更新计时器
        self.timer -= delta_time
        if self.timer <= 0:
            # 时间到，玩家赢了
            self._game_won()
            return

        # 生成敌人
        self.enemy_spawn_timer += delta_time
        if self.enemy_spawn_timer >= self.enemy_spawn_interval:
            self.enemy_spawn_timer = 0
            enemy = self.entity_factory.create_enemy(self.game.width, self.game.height)
            self.enemies.append(enemy)
            self.game_logic.enemies = self.enemies  # 更新逻辑引用

        # 检测碰撞
        result = self.game_logic.check_collisions()
        if result == "game_over":
            self._game_over()
            return

        # 检查玩家是否出界
        if self.game_logic.check_out_of_bounds(self.game.width, self.game.height):
            self._game_over()
            return

        # 更新分数
        self.score = self.game_logic.score

        # 更新UI显示
        self.ui_manager.update_ui(self.timer, self.score, self.player)

    def pause_game(self):
        """暂停游戏"""
        self.pause_menu.toggle_pause(True)

    def resume_game(self):
        """恢复游戏"""
        self.pause_menu.toggle_pause(False)

    def _game_over(self):
        """游戏失败"""
        self.game.scene_manager.change_scene(
            "game_over", result="defeat", score=self.score
        )

    def _game_won(self):
        """游戏胜利"""
        self.game.scene_manager.change_scene(
            "game_over", result="victory", score=self.score
        )

    def render(self):
        """渲染场景"""
        # 渲染游戏元素
        super().render()

        # 如果游戏暂停，渲染半透明覆盖层
        self.pause_menu.render_overlay(self.game.screen)

    def unload(self):
        """卸载场景"""
        # 清空世界
        for entity_id in list(self.game.world.entities.keys()):
            self.game.world.destroy_entity(entity_id)

        # 卸载UI元素
        super().unload()

    def return_to_menu(self):
        """返回主菜单"""
        self.game.scene_manager.change_scene("main_menu")
