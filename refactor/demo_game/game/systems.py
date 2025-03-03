import pygame
import math
from typing import List, Tuple
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.inputs import InputManager
from framework.managers.renders import RenderManager
from framework.managers.events import EventManager
from game.components import Position, Velocity, Collider, Renderable, Player, Enemy, Obstacle

class MovementSystem(System):
    """移动系统，处理实体的移动"""
    
    def __init__(self):
        super().__init__([Position, Velocity], priority=1)
    
    def update(self, world: World, delta_time: float) -> None:
        # 更新所有具有位置和速度组件的实体
        entities = world.get_entities_with_components(Position, Velocity)
        for entity in entities:
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)
            
            # 更新位置
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time
            
            # 限制在屏幕范围内
            pos.x = max(0, min(pos.x, 800))
            pos.y = max(0, min(pos.y, 600))

class PlayerControlSystem(System):
    """玩家控制系统，处理玩家输入"""
    
    def __init__(self, input_manager: InputManager):
        super().__init__([Player, Velocity], priority=2)
        self.input_manager = input_manager
    
    def update(self, world: World, delta_time: float) -> None:
        # 获取玩家实体
        entities = world.get_entities_with_components(Player, Velocity)
        for entity in entities:
            player = world.get_component(entity, Player)
            vel = world.get_component(entity, Velocity)
            
            # 处理移动输入
            vel.x = 0
            vel.y = 0
            if self.input_manager.is_key_pressed(pygame.K_LEFT):
                vel.x = -player.speed
            if self.input_manager.is_key_pressed(pygame.K_RIGHT):
                vel.x = player.speed
            if self.input_manager.is_key_pressed(pygame.K_UP):
                vel.y = -player.speed
            if self.input_manager.is_key_pressed(pygame.K_DOWN):
                vel.y = player.speed

class EnemyAISystem(System):
    """敌人AI系统，控制敌人追逐玩家"""
    
    def __init__(self):
        super().__init__([Enemy, Position, Velocity], priority=3)
    
    def update(self, world: World, delta_time: float) -> None:
        # 获取玩家位置
        player_entities = world.get_entities_with_components(Player, Position)
        if not player_entities:
            return
            
        player_pos = world.get_component(player_entities[0], Position)
        
        # 更新所有敌人
        enemy_entities = world.get_entities_with_components(Enemy, Position, Velocity)
        for entity in enemy_entities:
            enemy = world.get_component(entity, Enemy)
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)
            
            # 计算到玩家的方向
            dx = player_pos.x - pos.x
            dy = player_pos.y - pos.y
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance > 0:
                # 标准化方向并设置速度
                vel.x = (dx / distance) * enemy.speed
                vel.y = (dy / distance) * enemy.speed

class CollisionSystem(System):
    """碰撞检测系统，只负责检测碰撞并处理碰撞事件"""
    
    def __init__(self, event_manager: EventManager):
        super().__init__([Position, Collider], priority=4)
        self.event_manager = event_manager
    
    def update(self, world: World, delta_time: float) -> None:
        # 检测碰撞
        entities = world.get_entities_with_components(Position, Collider)
        
        # 检查所有实体对之间的碰撞
        for i, entity1 in enumerate(entities):
                
            pos1 = world.get_component(entity1, Position)
            col1 = world.get_component(entity1, Collider)
            if not pos1 or not col1:
                print(f"{entity1} missing Position or Collider component")
                continue
            
            for entity2 in entities[i+1:]:
                    
                pos2 = world.get_component(entity2, Position)
                col2 = world.get_component(entity2, Collider)
                if not pos2 or not col2:
                    print(f"{entity2} missing Position or Collider component")
                    continue
                
                # 计算距离
                dx = pos2.x - pos1.x
                dy = pos2.y - pos1.y
                distance = math.sqrt(dx * dx + dy * dy)
                
                # 检查碰撞
                if distance < col1.radius + col2.radius:
                    # 处理障碍物碰撞
                    if world.has_component(entity1, Obstacle) or world.has_component(entity2, Obstacle):
                        # 计算碰撞反弹
                        overlap = (col1.radius + col2.radius - distance) / 2
                        if overlap > 0:
                            # 计算碰撞法线
                            nx = dx / distance
                            ny = dy / distance
                            
                            # 分开两个物体
                            if not world.has_component(entity1, Obstacle):
                                pos1.x -= overlap * nx
                                pos1.y -= overlap * ny
                                # 如果有速度组件，反弹
                                if world.has_component(entity1, Velocity):
                                    vel1 = world.get_component(entity1, Velocity)
                                    vel1.x = -vel1.x
                                    vel1.y = -vel1.y
                            
                            if not world.has_component(entity2, Obstacle):
                                pos2.x += overlap * nx
                                pos2.y += overlap * ny
                                # 如果有速度组件，反弹
                                if world.has_component(entity2, Velocity):
                                    vel2 = world.get_component(entity2, Velocity)
                                    vel2.x = -vel2.x
                                    vel2.y = -vel2.y
                            
                            if world.has_component(entity1, Obstacle):
                                self.event_manager.publish("obstacle_collision", {"entity": entity1})
                            if world.has_component(entity2, Obstacle):
                                self.event_manager.publish("obstacle_collision", {"entity": entity2})
                    
                    # 检测玩家和敌人碰撞，发布碰撞事件
                    if (world.has_component(entity1, Player) and world.has_component(entity2, Enemy)) or \
                       (world.has_component(entity1, Enemy) and world.has_component(entity2, Player)):
                        # 获取玩家和敌人实体
                        player_entity = entity1 if world.has_component(entity1, Player) else entity2
                        enemy_entity = entity1 if world.has_component(entity1, Enemy) else entity2
                        
                        player_vel = world.get_component(player_entity, Velocity)
                        player_speed = math.sqrt(player_vel.x**2 + player_vel.y**2)
                        
                        # 发布玩家与敌人碰撞事件
                        self.event_manager.publish("player_enemy_collision", {
                            "player_entity": player_entity,
                            "enemy_entity": enemy_entity,
                            "player_speed": player_speed
                        })

class GlowSystem(System):
    """发光效果系统，处理实体的发光效果"""
    
    def __init__(self,world,event_manager):
        super().__init__([Collider], priority=4)
        self.event_manager = event_manager
        self.world = world
        self.event_manager.subscribe("obstacle_collision", self._handle_obstacle_collision)
    
    def _handle_obstacle_collision(self, event_data):
        """处理障碍物碰撞事件"""
        entity = event_data.get("entity")
        if entity is not None:
            if self.world.has_component(entity, Collider):
                collider = self.world.get_component(entity, Collider)
                collider.is_glowing = True
                collider.glow_timer = 0.0
    
    def update(self, world: World, delta_time: float) -> None:
        # 更新发光计时器
        entities = world.get_entities_with_components(Collider)
        for entity in entities:
            collider = world.get_component(entity, Collider)
            if collider.is_glowing:
                collider.glow_timer += delta_time
                if collider.glow_timer >= 0.5:  # 发光持续0.5秒
                    collider.is_glowing = False
                    collider.glow_timer = 0.0
                        

class RenderSystem(System):
    """渲染系统"""
    
    def __init__(self, render_manager: RenderManager):
        super().__init__([Position, Renderable], priority=5)
        self.render_manager = render_manager
    
    def update(self, world: World, delta_time: float) -> None:
        """更新游戏逻辑"""
        
        # 渲染所有可渲染实体
        entities = world.get_entities_with_components(Position, Renderable)
        for entity in entities:
            pos = world.get_component(entity, Position)
            renderable = world.get_component(entity, Renderable)
            
            # 如果实体有碰撞组件且处于发光状态，先渲染发光效果
            if world.has_component(entity, Collider):
                collider = world.get_component(entity, Collider)
                if collider.is_glowing:
                    glow_radius = renderable.radius * 1.5
                    glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
                    # 根据实体类型选择不同的发光颜色
                    glow_color = (154, 205, 50, 64) if world.has_component(entity, Obstacle) else (255, 255, 0, 100)
                    pygame.draw.circle(glow_surface, glow_color,
                                     (glow_radius, glow_radius), 
                                     glow_radius)
                    self.render_manager.draw(glow_surface, 
                                           pygame.Rect(pos.x - glow_radius, 
                                                      pos.y - glow_radius,
                                                      glow_radius * 2, 
                                                      glow_radius * 2))
            
            # 创建表面并绘制实体
            surface = pygame.Surface((renderable.radius * 2, renderable.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surface, renderable.color, 
                             (renderable.radius, renderable.radius), 
                             renderable.radius)
            
            # 渲染实体
            self.render_manager.draw(surface, 
                                   pygame.Rect(pos.x - renderable.radius, 
                                              pos.y - renderable.radius,
                                              renderable.radius * 2, 
                                              renderable.radius * 2))