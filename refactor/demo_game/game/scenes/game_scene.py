import pygame
import random
import time
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from game.components import (
    Position,
    Velocity,
    Collider,
    Renderable,
    Player,
    Enemy,
    Obstacle,
    MapPosition,
)
from game.managers.map_manager import MapManager


class GameScene(Scene):
    """游戏主场景，负责初始化游戏实体"""

    def __init__(self, engine):
        """初始化游戏场景

        Args:
            engine: 游戏引擎实例
        """
        super().__init__(engine)
        self.is_initialized = False
        self.game_over = False
        self.player_entity = None
        self.enemy_entity = None
        self.obstacle_entities = []
        self.score_label = None
        self.health_label = None
        self.player_health = 100
        # 添加游戏开始时间，用于计算相对时间
        self.game_start_time = 0
        # 添加游戏运行时间
        self.game_time = 0
        # 分数
        self.current_score = 0
        # 地图管理器
        self.map_manager = None

        # 订阅游戏重置事件
        self.engine.event_manager.subscribe("game_reset", self._on_game_reset)
        # 订阅地图生成和加载事件
        self.engine.event_manager.subscribe("map_generated", self._on_map_generated)
        self.engine.event_manager.subscribe("map_loaded", self._on_map_loaded)

    def enter(self) -> None:
        """进入场景时调用，初始化游戏实体"""
        print("GameScene: Entering game scene")

        # 初始化地图管理器（如果尚未初始化）
        if self.map_manager is None:
            self.map_manager = MapManager(self.world, self.engine.event_manager)

        # 重置游戏开始时间和游戏时间
        self.game_start_time = time.time()
        self.game_time = 0
        self.current_score = 0

        # 重置场景状态
        self.game_over = False
        self.player_health = 100

        # 重置游戏管理器
        self.engine.game_manager.reset()

        # 清理任何现有实体
        self._cleanup_entities()

        # 重新订阅游戏结束事件
        self.engine.event_manager.subscribe("game_over", self._on_game_over)

        # 生成随机地图
        if not self.map_manager.is_map_loaded():
            self.map_manager.generate_random_map(20, 15)

        # 初始化UI元素
        self._setup_ui()

        # 创建实体后初始化
        self._initialize_entities()

        self.is_initialized = True
        print("GameScene: Game scene initialized successfully")

    def _initialize_entities(self):
        """初始化游戏实体"""
        # 创建玩家实体
        self.player_entity = self.world.create_entity()
        self.world.add_component(self.player_entity, Position(400, 300))
        self.world.add_component(self.player_entity, Velocity(0, 0))
        self.world.add_component(self.player_entity, Collider(15))
        self.world.add_component(
            self.player_entity, Renderable((0, 0, 255), 15)
        )  # 蓝色玩家
        self.world.add_component(self.player_entity, Player())
        self.world.add_component(
            self.player_entity, MapPosition(10, 7)
        )  # 在地图中心位置

        # 创建敌人实体
        self.enemy_entity = self.world.create_entity()
        self.world.add_component(self.enemy_entity, Position(100, 100))
        self.world.add_component(self.enemy_entity, Velocity(0, 0))
        self.world.add_component(self.enemy_entity, Collider(15))
        self.world.add_component(
            self.enemy_entity, Renderable((255, 0, 0), 15)
        )  # 红色敌人
        self.world.add_component(self.enemy_entity, Enemy())
        self.world.add_component(self.enemy_entity, MapPosition(3, 3))  # 在地图左上位置

        # 创建4个障碍物实体
        obstacle_positions = [(200, 200), (600, 200), (200, 400), (600, 400)]
        map_positions = [(6, 6), (18, 6), (6, 12), (18, 12)]  # 对应的地图位置

        for i, pos in enumerate(obstacle_positions):
            obstacle = self.world.create_entity()
            self.world.add_component(obstacle, Position(pos[0], pos[1]))
            self.world.add_component(obstacle, Collider(25))
            self.world.add_component(
                obstacle, Renderable((100, 100, 100), 25)
            )  # 灰色障碍物
            self.world.add_component(obstacle, Obstacle())
            self.world.add_component(
                obstacle, MapPosition(map_positions[i][0], map_positions[i][1])
            )
            self.obstacle_entities.append(obstacle)

    def _cleanup_entities(self):
        """清理所有实体"""
        # 移除玩家实体
        if self.player_entity:
            self.world.remove_entity(self.player_entity)
            self.player_entity = None

        # 移除敌人实体
        if self.enemy_entity:
            self.world.remove_entity(self.enemy_entity)
            self.enemy_entity = None

        # 移除所有障碍物实体
        for obstacle in self.obstacle_entities:
            self.world.remove_entity(obstacle)
        self.obstacle_entities.clear()

        # 清理UI元素
        if self.score_label:
            self.engine.ui_manager.remove_element(self.score_label)
            self.score_label = None

        if self.health_label:
            self.engine.ui_manager.remove_element(self.health_label)
            self.health_label = None

        print("GameScene: All entities cleaned up")

    def _setup_ui(self):
        """设置游戏UI元素"""
        # 加载字体
        font = self.engine.resource_manager.load_font("default", None, 24)

        # 创建得分标签
        self.score_label = self.engine.ui_manager.create_label(
            position=(10, 10),
            size=(200, 30),
            text=f"Score: {self.current_score}",
            font=font,
            text_color=(255, 255, 255),
            background_color=None,
            z_index=10,
        )

        # 创建健康值标签
        self.health_label = self.engine.ui_manager.create_label(
            position=(10, 50),
            size=(200, 30),
            text=f"Health: {self.player_health}",
            font=font,
            text_color=(255, 255, 255),
            background_color=None,
            z_index=10,
        )

    def exit(self) -> None:
        """离开场景时调用，清理场景资源"""
        print("GameScene: Exiting game scene")

        # 取消订阅游戏结束事件
        self.engine.event_manager.unsubscribe("game_over", self._on_game_over)

        # 清理所有实体和UI元素
        self._cleanup_entities()

        # 重置场景状态
        self.is_initialized = False
        self.game_over = False
        print("GameScene: Exit complete")

    def _on_game_reset(self, message):
        """处理游戏重置事件"""
        print("GameScene: Received game reset event")
        # 重置游戏时间和分数
        self.game_start_time = time.time()
        self.game_time = 0
        self.current_score = 0
        self.player_health = 100

        # 如果场景已初始化，更新UI
        if self.is_initialized:
            if self.score_label:
                self.engine.ui_manager.set_text(
                    self.score_label, f"Score: {self.current_score}"
                )
            if self.health_label:
                self.engine.ui_manager.set_text(
                    self.health_label, f"Health: {self.player_health}"
                )

            # 重置游戏状态
            self.game_over = False

    def _on_map_generated(self, message):
        """处理地图生成事件"""
        print("GameScene: Map has been generated")
        # 如果场景未初始化，忽略
        if not self.is_initialized:
            return

        # 如果已经有实体，重新初始化它们的位置
        if self.player_entity and self.world.entity_exists(self.player_entity):
            map_pos = self.world.get_component(self.player_entity, MapPosition)
            if map_pos:
                # 更新实体的屏幕位置
                screen_x, screen_y = self.map_manager.get_screen_pos_from_grid(
                    map_pos.x, map_pos.y
                )
                pos = self.world.get_component(self.player_entity, Position)
                pos.x = screen_x + self.map_manager.tile_size // 2
                pos.y = screen_y + self.map_manager.tile_size // 2

    def _on_map_loaded(self, message):
        """处理地图加载事件"""
        print("GameScene: Map has been loaded")
        # 与地图生成事件处理相同
        self._on_map_generated(message)

    def update(self, delta_time: float) -> None:
        """更新场景

        Args:
            delta_time: 帧间隔时间
        """
        # 更新游戏时间（只有在游戏运行时更新）
        if self.is_initialized and not self.game_over:
            self.game_time += delta_time

            # 更新分数 - 使用游戏时间而不是系统时间
            self.current_score = int(self.game_time * 10)  # 每秒增加10分

            # 更新健康值 - 使用游戏时间而不是系统时间
            self.player_health = max(
                0, int(100 - (self.game_time * 2))
            )  # 每秒减少2点健康值

            # 更新UI显示
            if self.score_label:
                self.engine.ui_manager.set_text(
                    self.score_label, f"Score: {self.current_score}"
                )

            if self.health_label:
                self.engine.ui_manager.set_text(
                    self.health_label, f"Health: {self.player_health}"
                )

            # 如果血量为0，游戏结束
            if self.player_health <= 0 and not self.game_over:
                self.engine.event_manager.publish("game_over", {"victory": False})

            # 处理键盘输入 - 用于切换地图测试
            keys = pygame.key.get_pressed()
            if keys[pygame.K_m]:  # 按M键生成新地图
                if self.map_manager:
                    self.map_manager.generate_random_map(20, 15)

    def render(self, render_manager) -> None:
        """渲染场景

        Args:
            render_manager: 渲染管理器
        """
        # UI元素由UI系统自动渲染，这里不需要额外操作
        pass

    def _on_game_over(self, message):
        """处理游戏结束事件

        Args:
            message: 包含游戏结果的Message对象
        """
        self.game_over = True
        # 从Message对象的data属性中获取数据
        event_data = message.data if hasattr(message, "data") else message
        if event_data.get("victory"):
            self.engine.switch_scene("victory")
        else:
            self.engine.switch_scene("defeat")

    def cleanup(self):
        """清理资源"""
        # 取消事件订阅
        self.engine.event_manager.unsubscribe("game_reset", self._on_game_reset)
        self.engine.event_manager.unsubscribe("map_generated", self._on_map_generated)
        self.engine.event_manager.unsubscribe("map_loaded", self._on_map_loaded)

        # 清理地图管理器
        if self.map_manager:
            self.map_manager.cleanup()
            self.map_manager = None
