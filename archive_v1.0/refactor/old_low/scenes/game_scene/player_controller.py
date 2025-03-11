from typing import Optional, Tuple
import pygame
from engine.entity import Entity
from .base_controller import BaseController


class PlayerController(BaseController):
    """处理玩家实体的逻辑和控制"""

    def __init__(self, scene):
        super().__init__(scene)
        self.player: Optional[Entity] = None

    def initialize(self) -> None:
        """初始化玩家控制器"""
        super().initialize()

        # 从游戏数据中获取玩家位置
        game_data = self.scene.get_game_data()
        player_pos = game_data.get("player_position", (400, 300))

        # 创建玩家实体
        self.player = self.scene.entity_factory.create_player(
            player_pos[0], player_pos[1]
        )
        self.scene.add_entity(self.player)

    def update(self, delta_time: float) -> None:
        """更新玩家状态

        Args:
            delta_time: 帧间时间(秒)
        """
        if not self.player or not self.player.is_active():
            return

        self._update_movement(delta_time)

    def _update_movement(self, delta_time: float) -> None:
        """更新玩家移动

        Args:
            delta_time: 帧间时间(秒)
        """
        movement = self.player.get_component("movement")
        if not movement:
            return

        # 保存原始位置
        original_x, original_y = self.player.x, self.player.y

        # 应用移动
        self.player.x += movement.velocity_x * movement.speed * delta_time
        self.player.y += movement.velocity_y * movement.speed * delta_time

        # 处理地图碰撞
        self._handle_map_collision(delta_time, original_x, original_y)

    def _handle_map_collision(
        self, delta_time: float, original_x: float, original_y: float
    ) -> None:
        """处理玩家与地图的碰撞

        Args:
            delta_time: 帧间时间(秒)
            original_x: 移动前的X坐标
            original_y: 移动前的Y坐标
        """
        # 获取地图，确保地图存在
        game_map = None
        if hasattr(self.scene, "map") and self.scene.map:
            game_map = self.scene.map
        elif hasattr(self.scene, "map_handler") and self.scene.map_handler.map:
            game_map = self.scene.map_handler.map

        if not game_map:
            return

        # 使用碰撞管理器检测地图碰撞
        if hasattr(self.engine, "collision_manager"):
            map_collisions = self.engine.collision_manager.check_map_collision(
                self.player, game_map
            )
            # 如果有碰撞，撤销移动
            if map_collisions:
                self.player.x = original_x
                self.player.y = original_y
        else:
            # 使用旧的碰撞检测方式，确保传递正确的地图引用
            self._check_map_collision_legacy(delta_time, game_map)

    def _check_map_collision_legacy(self, delta_time: float, game_map=None) -> None:
        """使用旧方式检测玩家与地图的碰撞

        Args:
            delta_time: 帧间时间(秒)
            game_map: 地图对象，如果为None则尝试从场景获取
        """
        if not self.player:
            return

        if not game_map:
            if hasattr(self.scene, "map") and self.scene.map:
                game_map = self.scene.map
            elif hasattr(self.scene, "map_handler") and self.scene.map_handler.map:
                game_map = self.scene.map_handler.map
            else:
                return

        movement = self.player.get_component("movement")
        collision = self.player.get_component("collision")
        if not movement or not collision:
            return

        # 获取玩家碰撞盒的四个角坐标
        player_left = self.player.x
        player_right = self.player.x + collision.width
        player_top = self.player.y
        player_bottom = self.player.y + collision.height

        # 计算四个角所在的瓦片坐标
        tile_size = game_map.tile_size
        tile_top_left = (int(player_left // tile_size), int(player_top // tile_size))
        tile_top_right = (int(player_right // tile_size), int(player_top // tile_size))
        tile_bottom_left = (
            int(player_left // tile_size),
            int(player_bottom // tile_size),
        )
        tile_bottom_right = (
            int(player_right // tile_size),
            int(player_bottom // tile_size),
        )

        # 检查这四个角是否在可通行的瓦片上
        corners = [tile_top_left, tile_top_right, tile_bottom_left, tile_bottom_right]

        for tile_x, tile_y in corners:
            if not game_map.is_passable(tile_x, tile_y):
                # 如果某个角不可通行，恢复位置
                self.player.x -= movement.velocity_x * movement.speed * delta_time
                self.player.y -= movement.velocity_y * movement.speed * delta_time
                break

    def handle_key_down(self, key: int) -> bool:
        """处理按键按下事件

        Args:
            key: 按键代码

        Returns:
            是否处理了此事件
        """
        if not self.player:
            return False

        movement = self.player.get_component("movement")
        if not movement:
            return False

        handled = True

        if key == pygame.K_w:
            movement.velocity_y = -1
        elif key == pygame.K_s:
            movement.velocity_y = 1
        elif key == pygame.K_a:
            movement.velocity_x = -1
        elif key == pygame.K_d:
            movement.velocity_x = 1
        elif key == pygame.K_SPACE:
            self._find_path_to_nearest_enemy()
        else:
            handled = False

        return handled

    def handle_key_up(self, key: int) -> bool:
        """处理按键释放事件

        Args:
            key: 按键代码

        Returns:
            是否处理了此事件
        """
        if not self.player:
            return False

        movement = self.player.get_component("movement")
        if not movement:
            return False

        handled = True

        if key == pygame.K_w and movement.velocity_y < 0:
            movement.velocity_y = 0
        elif key == pygame.K_s and movement.velocity_y > 0:
            movement.velocity_y = 0
        elif key == pygame.K_a and movement.velocity_x < 0:
            movement.velocity_x = 0
        elif key == pygame.K_d and movement.velocity_x > 0:
            movement.velocity_x = 0
        else:
            handled = False

        return handled

    def _find_path_to_nearest_enemy(self) -> None:
        """寻找到最近敌人的路径"""
        if (
            not self.player
            or not self.scene.map
            or not hasattr(self.scene, "enemy_controller")
        ):
            return

        # 获取活动的敌人
        active_enemies = self.scene.enemy_controller.get_active_enemies()
        if not active_enemies:
            return

        # 简单起见，选择第一个敌人作为目标
        target = active_enemies[0]
        tile_size = self.scene.map.tile_size
        start_x = int(self.player.x // tile_size)
        start_y = int(self.player.y // tile_size)
        end_x = int(target.x // tile_size)
        end_y = int(target.y // tile_size)

        path = self.scene.map.find_path(start_x, start_y, end_x, end_y)
        if self.debug_mode:
            print(f"找到从 ({start_x},{start_y}) 到 ({end_x},{end_y}) 的路径: {path}")

    def get_position(self) -> Tuple[float, float]:
        """获取玩家位置

        Returns:
            玩家位置元组 (x, y)，如果玩家不存在返回 (0, 0)
        """
        if not self.player:
            return (0, 0)
        return (self.player.x, self.player.y)

    def cleanup(self) -> None:
        """清理资源"""
        # 记录玩家位置到游戏数据
        if self.player:
            self.scene.update_game_data(
                "player_position", (self.player.x, self.player.y)
            )
