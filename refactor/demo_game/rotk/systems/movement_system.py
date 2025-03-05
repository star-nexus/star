import random
import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    MapComponent,
    PositionComponent,
    MovableComponent,
    PlayerComponent,
    EnemyComponent,
    TERRAIN_MOVEMENT_COST,
)

from rotk.managers import MapManager, CameraManager


class MovementSystem(System):
    """移动系统，负责处理实体的移动和碰撞"""

    def __init__(self):
        super().__init__([PositionComponent, MovableComponent], priority=20)
        self.map_manager = None
        self.camera_manager = None
        self.player_entity = None
        self.enemy_entities = []

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager: MapManager,
        camera_manager: CameraManager = None,
        player_entity=None,
        enemy_entities=None,
    ) -> None:
        """初始化移动系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            camera_manager: 相机管理器
            player_entity: 玩家实体
            enemy_entities: 敌人实体列表
        """
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.camera_manager = camera_manager
        self.player_entity = player_entity
        self.enemy_entities = enemy_entities if enemy_entities else []

        # 订阅键盘事件
        self.event_manager.subscribe(
            "KEYDOWN", lambda message: self._handle_input(world, message)
        )

    def set_player(self, player_entity):
        """设置玩家实体

        Args:
            player_entity: 玩家实体
        """
        self.player_entity = player_entity

    def set_enemies(self, enemy_entities):
        """设置敌人实体列表

        Args:
            enemy_entities: 敌人实体列表
        """
        self.enemy_entities = enemy_entities

    def _handle_input(self, world: World, message: Message) -> None:
        """处理输入事件

        Args:
            world: 游戏世界
            message: 事件消息
        """
        if message.topic == "KEYDOWN" and self.player_entity:
            key = message.data
            # 处理玩家移动
            player_pos = world.get_component(self.player_entity, PositionComponent)
            if player_pos:
                new_x, new_y = player_pos.x, player_pos.y

                if key == pygame.K_UP:
                    new_y -= 1
                elif key == pygame.K_DOWN:
                    new_y += 1
                elif key == pygame.K_LEFT:
                    new_x -= 1
                elif key == pygame.K_RIGHT:
                    new_x += 1
                else:
                    return  # 不是移动键

                # 移动玩家
                if self.move_entity(world, self.player_entity, new_x, new_y):
                    # 如果有相机，跟随玩家移动
                    if self.camera_manager:
                        self._center_camera_on_player(world)

    def _center_camera_on_player(self, world: World) -> None:
        """让相机居中于玩家位置

        Args:
            world: 游戏世界
        """
        if not self.camera_manager or not self.player_entity:
            return

        player_pos = world.get_component(self.player_entity, PositionComponent)
        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)

        if player_pos and map_comp:
            # 计算玩家在世界坐标系中的位置
            world_x = player_pos.x * map_comp.cell_size
            world_y = player_pos.y * map_comp.cell_size

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

    def move_entity(self, world, entity, new_x, new_y):
        """移动实体到新位置

        Args:
            world: 游戏世界
            entity: 要移动的实体
            new_x: 新的X坐标
            new_y: 新的Y坐标

        Returns:
            bool: 移动是否成功
        """
        # 检查位置是否有效
        if not self.map_manager.is_position_valid(world, new_x, new_y):
            return False

        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        if not map_comp:
            return False

        # 检查该位置是否有其他实体
        for e, pos in map_comp.entities_positions.items():
            if pos == (new_x, new_y) and e != entity:
                # 如果是敌人移动到玩家位置，或玩家移动到敌人位置，触发战斗
                if (
                    world.has_component(entity, PlayerComponent)
                    and world.has_component(e, EnemyComponent)
                ) or (
                    world.has_component(entity, EnemyComponent)
                    and world.has_component(e, PlayerComponent)
                ):
                    print("战斗发生!")
                return False

        # 获取移动组件和位置组件
        pos_comp = world.get_component(entity, PositionComponent)
        movable_comp = world.get_component(entity, MovableComponent)

        if not pos_comp or not movable_comp:
            return False

        # 获取地形类型和移动消耗
        terrain_type = self.map_manager.get_terrain_at(world, new_x, new_y)
        movement_cost = self.map_manager.get_movement_cost(terrain_type)

        # 检查是否有足够的移动点数
        if movable_comp.movement_points < movement_cost:
            print("移动点数不足!")
            return False

        # 更新位置
        old_x, old_y = pos_comp.x, pos_comp.y
        pos_comp.prev_x, pos_comp.prev_y = old_x, old_y
        pos_comp.x, pos_comp.y = new_x, new_y

        # 更新移动点数
        movable_comp.movement_points -= movement_cost

        # 更新实体位置映射
        map_comp.entities_positions[entity] = (new_x, new_y)

        return True

    def update(self, world: World, delta_time: float) -> None:
        """更新移动系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 更新敌人AI
        for enemy in self.enemy_entities:
            # 简单的随机移动AI
            if random.random() < 0.05:  # 每帧有5%的概率移动
                pos_comp = world.get_component(enemy, PositionComponent)
                if pos_comp:
                    # 随机选择一个方向
                    dx, dy = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
                    self.move_entity(world, enemy, pos_comp.x + dx, pos_comp.y + dy)
