import random
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager

from rotk.components import (
    MapComponent,
    PositionComponent,
    MovableComponent,
    PlayerComponent,
    EnemyComponent,
    RenderableComponent,
)

from rotk.managers import MapManager


class EntitySystem(System):
    """实体系统，负责创建和管理玩家和敌人实体"""

    def __init__(self):
        super().__init__([], priority=5)  # 不需要特定组件约束
        self.player_entity = None
        self.enemy_entities = []
        self.map_manager = None

    def initialize(self, world: World, map_manager: MapManager) -> None:
        """初始化实体系统

        Args:
            world: 游戏世界
            map_manager: 地图管理器
        """
        self.map_manager = map_manager

    def create_player(self, world: World) -> int:
        """创建玩家实体

        Args:
            world: 游戏世界

        Returns:
            int: 创建的玩家实体ID
        """
        # 如果已经有玩家，不再创建
        if self.player_entity and world.has_component(
            self.player_entity, PlayerComponent
        ):
            return self.player_entity

        # 在地图中找一个合适的位置
        x, y = self.map_manager.find_walkable_position(world)

        # 创建玩家实体
        player = world.create_entity()
        world.add_component(player, PlayerComponent())
        world.add_component(player, PositionComponent(x=x, y=y, prev_x=x, prev_y=y))
        world.add_component(player, MovableComponent(speed=2, movement_points=2))
        world.add_component(
            player, RenderableComponent(color=(0, 0, 255), symbol="P", size=24)
        )

        self.player_entity = player

        # 更新实体位置映射
        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        if map_comp:
            map_comp.entities_positions[player] = (x, y)

        return player

    def create_enemy(self, world: World) -> int:
        """创建敌人实体

        Args:
            world: 游戏世界

        Returns:
            int: 创建的敌人实体ID
        """
        # 在地图中找一个合适的位置
        x, y = self.map_manager.find_walkable_position(world)

        # 创建敌人实体
        enemy = world.create_entity()
        world.add_component(enemy, EnemyComponent())
        world.add_component(enemy, PositionComponent(x=x, y=y, prev_x=x, prev_y=y))
        world.add_component(enemy, MovableComponent(speed=1, movement_points=1))
        world.add_component(
            enemy, RenderableComponent(color=(255, 0, 0), symbol="E", size=20)
        )

        self.enemy_entities.append(enemy)

        # 更新实体位置映射
        map_comp = world.get_component(self.map_manager.map_entity, MapComponent)
        if map_comp:
            map_comp.entities_positions[enemy] = (x, y)

        return enemy

    def remove_all_enemies(self, world: World) -> None:
        """移除所有敌人实体

        Args:
            world: 游戏世界
        """
        for enemy in self.enemy_entities:
            world.remove_entity(enemy)
        self.enemy_entities = []

    def update(self, world: World, delta_time: float) -> None:
        """更新实体系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 恢复实体的移动点数
        for entity in world.get_entities_with_components(MovableComponent):
            movable_comp = world.get_component(entity, MovableComponent)
            movable_comp.movement_points = movable_comp.speed
