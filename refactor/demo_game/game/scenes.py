import pygame
import random
from framework.core.ecs.world import World
from framework.managers.scenes import Scene
from game.components import Position, Velocity, Collider, Renderable, Player, Enemy, Obstacle

class GameScene(Scene):
    """游戏主场景，负责初始化游戏实体"""
    
    def __init__(self, world: World):
        """初始化游戏场景
        
        Args:
            world: ECS世界实例
        """
        super().__init__(world)
        self.is_initialized = False
        self.game_over = False
        self.player_entity = None
        self.enemy_entity = None
        self.obstacle_entities = []
        
    def enter(self) -> None:
        """进入场景时调用，初始化游戏实体"""
        # 如果已经初始化过，先清理现有实体
        if self.is_initialized:
            self.exit()
            print("Re-initializing game scene...")
        
        # 重置场景状态
        self.is_initialized = False
        self.game_over = False
        self.player_entity = None
        self.enemy_entity = None
        self.obstacle_entities = []
        
        print("Initializing game scene...")
            
        # 重新订阅游戏结束事件
        self.engine.event_manager.subscribe("game_over", self._on_game_over)
            
        # 创建玩家实体
        self.player_entity = self.world.create_entity()
        self.world.add_component(self.player_entity, Position(400, 300))
        self.world.add_component(self.player_entity, Velocity(0, 0))
        self.world.add_component(self.player_entity, Collider(15))
        self.world.add_component(self.player_entity, Renderable((0, 0, 255), 15))  # 蓝色玩家
        self.world.add_component(self.player_entity, Player())
        
        # 创建敌人实体
        self.enemy_entity = self.world.create_entity()
        self.world.add_component(self.enemy_entity, Position(100, 100))
        self.world.add_component(self.enemy_entity, Velocity(0, 0))
        self.world.add_component(self.enemy_entity, Collider(15))
        self.world.add_component(self.enemy_entity, Renderable((255, 0, 0), 15))  # 红色敌人
        self.world.add_component(self.enemy_entity, Enemy())
        
        # 创建4个障碍物实体
        obstacle_positions = [
            (200, 200),
            (600, 200),
            (200, 400),
            (600, 400)
        ]
        
        for pos in obstacle_positions:
            obstacle = self.world.create_entity()
            self.world.add_component(obstacle, Position(pos[0], pos[1]))
            self.world.add_component(obstacle, Collider(25))
            self.world.add_component(obstacle, Renderable((100, 100, 100), 25))  # 灰色障碍物
            self.world.add_component(obstacle, Obstacle())
            self.obstacle_entities.append(obstacle)
        
        self.is_initialized = True
    
    def exit(self) -> None:
        """离开场景时调用，清理场景资源"""
        # 取消订阅游戏结束事件
        self.engine.event_manager.unsubscribe("game_over", self._on_game_over)
        
        # 移除所有实体
        if self.player_entity:
            self.world.remove_entity(self.player_entity)
            self.player_entity = None
            
        if self.enemy_entity:
            self.world.remove_entity(self.enemy_entity)
            self.enemy_entity = None
            
        for obstacle in self.obstacle_entities:
            self.world.remove_entity(obstacle)
        self.obstacle_entities.clear()
        
        # 重置场景状态
        self.is_initialized = False
        self.game_over = False
        print("退出游戏场景")
    
    def update(self, delta_time: float) -> None:
        """更新场景
        
        Args:
            delta_time: 帧间隔时间
        """
        # 场景特定的更新逻辑可以在这里实现
        pass
    
    def render(self, render_manager) -> None:
        """渲染场景
        
        Args:
            render_manager: 渲染管理器
        """
        # 场景特定的渲染逻辑可以在这里实现
        # 注意：实体的渲染由RenderSystem处理
        pass
        
    def _on_game_over(self, event_data):
        """处理游戏结束事件
        
        Args:
            event_data: 包含游戏结果的事件数据
        """
        if event_data.get("victory"):
            self.engine.switch_scene("victory")
        else:
            self.engine.switch_scene("defeat")