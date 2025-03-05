import pygame
import random
import time
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from rotk.systems import MapSystem, EntitySystem, MovementSystem
from rotk.managers import MapManager, CameraManager
from rotk.components import MapComponent, PositionComponent  # 添加这一行导入必要的组件


class GameScene(Scene):
    """游戏主场景，负责初始化游戏实体"""

    def __init__(self, engine):
        super().__init__(engine)
        self.map_system = None
        self.entity_system = None
        self.movement_system = None
        self.map_manager = None
        self.camera_manager = None

    def enter(self) -> None:
        """场景进入时调用"""
        # 创建相机管理器
        self.camera_manager = CameraManager(self.engine.width, self.engine.height)

        # 创建地图管理器
        self.map_manager = MapManager()

        # 初始化实体系统
        self.entity_system = EntitySystem()
        self.entity_system.initialize(self.world, self.map_manager)
        self.world.add_system(self.entity_system)

        # 初始化地图系统
        self.map_system = MapSystem()
        self.map_system.initialize(
            self.world, self.engine.event_manager, self.map_manager, self.camera_manager
        )
        self.world.add_system(self.map_system)

        # 创建和初始化地图
        self.map_manager.create_map(self.world, width=10, height=10)  # 10 40 60

        # 创建玩家和敌人实体
        player_entity = self.entity_system.create_player(self.world)
        enemy_entities = []
        for _ in range(3):
            enemy = self.entity_system.create_enemy(self.world)
            enemy_entities.append(enemy)

        # 初始化移动系统
        self.movement_system = MovementSystem()
        self.movement_system.initialize(
            self.world,
            self.engine.event_manager,
            self.map_manager,
            self.camera_manager,
            player_entity,
            enemy_entities,
        )
        self.world.add_system(self.movement_system)

        # 初始化相机位置，居中于玩家
        self.movement_system._center_camera_on_player(self.world)

        # 订阅空格键事件，用于重新生成地图
        self.engine.event_manager.subscribe("KEYDOWN", self._handle_global_input)

        print("游戏场景已加载。使用方向键移动玩家，按空格键重新生成地图。")
        print("按住鼠标中键拖动地图，使用+/-键缩放。")

    def exit(self) -> None:
        """场景退出时调用"""
        # 取消订阅
        self.engine.event_manager.unsubscribe("KEYDOWN", self._handle_global_input)

        # 清理资源
        if self.map_system:
            self.world.remove_system(self.map_system)
            self.map_system = None

        if self.entity_system:
            self.world.remove_system(self.entity_system)
            self.entity_system = None

        if self.movement_system:
            self.world.remove_system(self.movement_system)
            self.movement_system = None

        self.map_manager = None
        self.camera_manager = None

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
        # 1. 记录玩家当前位置（如果存在）
        player_pos = None
        if self.entity_system.player_entity:
            player_comp = self.world.get_component(
                self.entity_system.player_entity, PositionComponent
            )
            if player_comp:
                player_pos = (player_comp.x, player_comp.y)

        # 2. 移除所有敌人
        self.entity_system.remove_all_enemies(self.world)

        # 3. 重新生成地图
        self.map_manager.regenerate_map(self.world)

        # 4. 重新定位玩家（如果之前存在）
        if self.entity_system.player_entity and player_pos:
            player_comp = self.world.get_component(
                self.entity_system.player_entity, PositionComponent
            )
            if player_comp:
                # 确保位置在地图范围内
                map_comp = self.world.get_component(
                    self.map_manager.map_entity, MapComponent
                )
                if map_comp:
                    player_comp.x = min(max(0, player_pos[0]), map_comp.width - 1)
                    player_comp.y = min(max(0, player_pos[1]), map_comp.height - 1)
                    # 更新位置映射
                    map_comp.entities_positions[self.entity_system.player_entity] = (
                        player_comp.x,
                        player_comp.y,
                    )

        # 5. 创建新敌人
        enemy_entities = []
        for _ in range(3):
            enemy = self.entity_system.create_enemy(self.world)
            enemy_entities.append(enemy)

        # 6. 更新敌人列表
        self.movement_system.set_enemies(enemy_entities)

        # 7. 更新相机位置
        self.movement_system._center_camera_on_player(self.world)

        print("地图已重新生成!")
