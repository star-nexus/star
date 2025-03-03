import pygame
from .tile import TileType


class MapRenderer:
    """
    地图渲染系统：负责将地图数据渲染到屏幕上
    """

    def __init__(self, tile_size=32):
        self.tile_size = tile_size  # 单个格子的像素大小
        self.offset_x = 0  # 渲染偏移X（用于视口移动）
        self.offset_y = 0  # 渲染偏移Y
        self.zoom = 1.0  # 缩放级别

        # 加载地形贴图
        self.textures = {}
        self._load_textures()

    def _load_textures(self):
        """加载地形贴图"""
        # 这里是简化实现，实际项目中应该加载真实的纹理
        # 为每种地形创建一个简单的纹理表面
        for tile_type in TileType.COLORS:
            texture = pygame.Surface((self.tile_size, self.tile_size))
            texture.fill(TileType.COLORS[tile_type])

            # 添加一些视觉区分特征
            if tile_type == TileType.MOUNTAIN:
                # 山地纹理：添加三角形
                points = [
                    (self.tile_size // 2, 5),
                    (self.tile_size - 5, self.tile_size - 5),
                    (5, self.tile_size - 5),
                ]
                pygame.draw.polygon(texture, (100, 100, 100), points)
            elif tile_type == TileType.WATER:
                # 水面纹理：添加波浪线
                for y in range(5, self.tile_size, 10):
                    pygame.draw.aaline(
                        texture, (80, 160, 230), (0, y), (self.tile_size, y + 5)
                    )
            elif tile_type == TileType.FOREST:
                # 森林纹理：添加树形
                tree_color = (30, 100, 30)
                pygame.draw.circle(
                    texture,
                    tree_color,
                    (self.tile_size // 2, self.tile_size // 3),
                    self.tile_size // 4,
                )
            elif tile_type == TileType.SWAMP:
                # 沼泽纹理：添加小圆点
                for _ in range(10):
                    x = 5 + (self.tile_size - 10) * ((_ * 73) % 100) / 100
                    y = 5 + (self.tile_size - 10) * ((_ * 51) % 100) / 100
                    pygame.draw.circle(texture, (110, 130, 70), (int(x), int(y)), 2)

            self.textures[tile_type] = texture

    def render(self, surface, map_data):
        """
        渲染地图到指定表面
        :param surface: 渲染目标表面（通常是游戏屏幕）
        :param map_data: 地图数据对象
        """
        # 确定可见区域（基于偏移和屏幕尺寸）
        screen_width, screen_height = surface.get_size()

        # 计算可见的格子范围
        effective_tile_size = int(self.tile_size * self.zoom)
        start_x = max(0, int(self.offset_x / effective_tile_size))
        start_y = max(0, int(self.offset_y / effective_tile_size))
        end_x = min(map_data.width, start_x + screen_width // effective_tile_size + 2)
        end_y = min(map_data.height, start_y + screen_height // effective_tile_size + 2)

        # 渲染可见范围内的所有格子
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = map_data.get_tile(x, y)
                if not tile:
                    continue

                # 计算屏幕位置
                screen_x = int(x * effective_tile_size - self.offset_x)
                screen_y = int(y * effective_tile_size - self.offset_y)

                # 渲染格子
                texture = self.textures.get(tile.type)
                if texture:
                    # 如果有缩放，先缩放纹理
                    if self.zoom != 1.0:
                        scaled_texture = pygame.transform.scale(
                            texture, (effective_tile_size, effective_tile_size)
                        )
                        surface.blit(scaled_texture, (screen_x, screen_y))
                    else:
                        surface.blit(texture, (screen_x, screen_y))
                else:
                    # 如果没有纹理，则使用颜色填充
                    rect = pygame.Rect(
                        screen_x, screen_y, effective_tile_size, effective_tile_size
                    )
                    pygame.draw.rect(surface, tile.color, rect)
                    pygame.draw.rect(surface, (0, 0, 0), rect, 1)  # 边框

    def screen_to_map(self, screen_x, screen_y):
        """
        将屏幕坐标转换为地图格子坐标
        :return: (map_x, map_y) 地图格子坐标
        """
        effective_tile_size = int(self.tile_size * self.zoom)
        map_x = int((screen_x + self.offset_x) / effective_tile_size)
        map_y = int((screen_y + self.offset_y) / effective_tile_size)
        return map_x, map_y

    def map_to_screen(self, map_x, map_y):
        """
        将地图格子坐标转换为屏幕坐标
        :return: (screen_x, screen_y) 屏幕坐标
        """
        effective_tile_size = int(self.tile_size * self.zoom)
        # 确保正确转换像素坐标
        if isinstance(map_x, int) and isinstance(map_y, int):
            # 如果是地图格子坐标，转换为像素
            screen_x = int(map_x * effective_tile_size - self.offset_x)
            screen_y = int(map_y * effective_tile_size - self.offset_y)
        else:
            # 如果已经是像素坐标，只需应用缩放和偏移
            screen_x = int(map_x * self.zoom - self.offset_x)
            screen_y = int(map_y * self.zoom - self.offset_y)
        return screen_x, screen_y

    def move_view(self, dx, dy):
        """移动视图"""
        self.offset_x += dx
        self.offset_y += dy
        # 确保不会移出边界
        self.offset_x = max(0, self.offset_x)
        self.offset_y = max(0, self.offset_y)

    def set_zoom(self, zoom):
        """设置缩放级别"""
        # 限制缩放范围
        self.zoom = max(0.5, min(2.0, zoom))
