import pygame
from typing import Dict, Any, Tuple
from .base_controller import BaseController


class MapHandler(BaseController):
    """处理游戏地图的生成和管理"""

    def __init__(self, scene):
        super().__init__(scene)
        self.map = None

    def initialize(self) -> None:
        """初始化地图处理器"""
        super().initialize()

        # 创建游戏地图
        self._create_game_map()

    def _create_game_map(self) -> None:
        """创建游戏地图"""
        if not self.engine.map_manager:
            return

        # 创建简单的瓦片图像
        grass_tile = pygame.Surface((32, 32))
        grass_tile.fill((0, 128, 0))

        water_tile = pygame.Surface((32, 32))
        water_tile.fill((0, 0, 196))

        mountain_tile = pygame.Surface((32, 32))
        mountain_tile.fill((128, 128, 128))

        # 定义瓦片类型
        tile_types = {
            "grass": {"image": grass_tile, "passable": True},
            "water": {"image": water_tile, "passable": False},
            "mountain": {"image": mountain_tile, "passable": False},
        }

        # 生成随机地图 (50x50 瓦片)
        map_width = 50
        map_height = 50
        self.map = self.engine.map_manager.generate_random_map(
            map_width, map_height, tile_types, 32
        )

        # 确保玩家初始位置附近是可通行的
        self._ensure_passable_area_around_player()

        # 设置场景的地图
        self.scene.set_map(self.map)

    def _ensure_passable_area_around_player(self) -> None:
        """确保玩家周围区域是可通行的"""
        if not self.map:
            return

        # 获取玩家位置 - 改用更安全的方式
        player_pos = (400, 300)  # 默认位置

        if (
            hasattr(self.scene, "player_controller")
            and self.scene.player_controller.player
        ):
            player = self.scene.player_controller.player
            player_pos = (player.x, player.y)
        else:
            # 从游戏数据中获取玩家位置
            game_data = self.scene.get_game_data()
            if "player_position" in game_data:
                player_pos = game_data["player_position"]

        player_tile_x = int(player_pos[0] // self.map.tile_size)
        player_tile_y = int(player_pos[1] // self.map.tile_size)

        # 确保玩家位置和周围区域为可通行区域（草地）
        for x in range(
            max(0, player_tile_x - 2), min(self.map.width, player_tile_x + 3)
        ):
            for y in range(
                max(0, player_tile_y - 2), min(self.map.height, player_tile_y + 3)
            ):
                self.map.set_tile(x, y, "grass")

    def find_path(self, start_x: int, start_y: int, end_x: int, end_y: int) -> list:
        """寻找从起点到终点的路径

        Args:
            start_x: 起点X坐标(瓦片)
            start_y: 起点Y坐标(瓦片)
            end_x: 终点X坐标(瓦片)
            end_y: 终点Y坐标(瓦片)

        Returns:
            路径坐标列表，如果没有路径则返回空列表
        """
        if not self.map:
            return []

        return self.map.find_path(start_x, start_y, end_x, end_y)

    def is_passable(self, tile_x: int, tile_y: int) -> bool:
        """检查指定瓦片是否可通行

        Args:
            tile_x: 瓦片X坐标
            tile_y: 瓦片Y坐标

        Returns:
            瓦片是否可通行
        """
        if not self.map:
            return False

        return self.map.is_passable(tile_x, tile_y)

    def update(self, delta_time: float) -> None:
        """更新地图

        Args:
            delta_time: 帧间时间(秒)
        """
        # 地图目前不需要每帧更新
        pass

    def cleanup(self) -> None:
        """清理资源"""
        # 这里可以添加需要清理的资源
        pass
