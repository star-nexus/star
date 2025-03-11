from typing import List, Optional
import random
from engine.entity import Entity
from .base_controller import BaseController


class EnemyController(BaseController):
    """处理敌人实体的逻辑和控制"""

    def __init__(self, scene):
        super().__init__(scene)
        self.enemies: List[Entity] = []
        self.defeated_enemies: List[Entity] = []

    def initialize(self) -> None:
        """初始化敌人控制器"""
        super().initialize()
        # 重置敌人列表
        self.enemies = []
        self.defeated_enemies = []

        # 生成初始敌人
        enemy_count = 5
        self.spawn_enemies(enemy_count)

        # 更新游戏数据中的敌人总数
        self.scene.update_game_data("total_enemies", enemy_count)

    def spawn_enemies(self, count: int) -> None:
        """生成指定数量的敌人

        Args:
            count: 要生成的敌人数量
        """
        attempts = 0
        spawned = 0
        max_attempts = count * 20  # 限制尝试次数，避免无限循环

        while spawned < count and attempts < max_attempts:
            # 使用实体工厂创建敌人
            enemy = self.scene.entity_factory.create_enemy()
            attempts += 1

            # 检查是否在可通行地形上
            if self.scene.map:
                tile_x = int(enemy.x // self.scene.map.tile_size)
                tile_y = int(enemy.y // self.scene.map.tile_size)
                if not self.scene.map.is_passable(tile_x, tile_y):
                    continue  # 重新尝试生成

            # 添加到场景和敌人列表
            self.scene.add_entity(enemy)
            self.enemies.append(enemy)
            spawned += 1

        if spawned < count:
            print(f"警告：只成功生成了 {spawned}/{count} 个敌人")

    def update(self, delta_time: float) -> None:
        """更新所有敌人

        Args:
            delta_time: 帧间时间(秒)
        """
        if (
            not hasattr(self.scene, "player_controller")
            or not self.scene.player_controller.player
        ):
            return

        player = self.scene.player_controller.player

        # 更新每个敌人AI
        for enemy in self.enemies:
            if not enemy.is_active():
                continue

            self._update_enemy_ai(enemy, player, delta_time)

    def _update_enemy_ai(
        self, enemy: Entity, player: Entity, delta_time: float
    ) -> None:
        """更新单个敌人的AI

        Args:
            enemy: 敌人实体
            player: 玩家实体
            delta_time: 帧间时间(秒)
        """
        enemy_movement = enemy.get_component("movement")
        if not enemy_movement:
            return

        # 计算方向向量
        dx = player.x - enemy.x
        dy = player.y - enemy.y

        # 归一化
        length = (dx**2 + dy**2) ** 0.5
        if length > 0:
            dx /= length
            dy /= length

        # 设置速度
        enemy_movement.set_velocity(dx * 0.5, dy * 0.5)

    def handle_enemy_defeated(self, enemy: Entity) -> None:
        """处理敌人被击败

        Args:
            enemy: 被击败的敌人实体
        """
        # 如果这个敌人已经被击败了，不再处理
        if enemy in self.defeated_enemies:
            return

        # 使敌人失活
        enemy.set_active(False)

        # 记录这个敌人已被击败
        self.defeated_enemies.append(enemy)

        # 从敌人列表中移除
        if enemy in self.enemies:
            self.enemies.remove(enemy)

        # 增加分数
        self.scene.score += 100
        if self.debug_mode:
            print(f"击败敌人! 当前分数: {self.scene.score}")

        # 更新游戏状态数据
        self.scene.update_game_data("score", self.scene.score)
        self.scene.update_game_data("defeated_enemies", len(self.defeated_enemies))

        # 检查是否所有敌人都被击败
        if not self.enemies:
            self.scene.handle_victory()  # 确保此方法调用

    def get_active_enemies(self) -> List[Entity]:
        """获取所有活动状态的敌人

        Returns:
            活动敌人列表
        """
        return [enemy for enemy in self.enemies if enemy.is_active()]

    def get_enemy_count(self) -> int:
        """获取当前敌人数量

        Returns:
            敌人数量
        """
        return len(self.enemies)

    def get_defeated_enemy_count(self) -> int:
        """获取已被击败的敌人数量

        Returns:
            已击败敌人数量
        """
        return len(self.defeated_enemies)

    def cleanup(self) -> None:
        """清理资源"""
        # 这里可以添加需要清理的资源
        pass
