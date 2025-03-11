import pygame
from framework.ui.ui_element import UIElement


class Minimap(UIElement):
    """小地图：显示整个游戏地图的缩略图"""

    def __init__(self, x, y, width, height, map_data=None, map_renderer=None):
        super().__init__(x, y, width, height)
        self.map_data = map_data
        self.map_renderer = map_renderer
        self.surface = None
        self.need_redraw = True
        self.cursor_pos = (0, 0)  # 当前视口在小地图上的位置
        self.cursor_size = (0, 0)  # 视口大小
        self.scale_x = 1.0
        self.scale_y = 1.0

    def set_map_data(self, map_data, map_renderer):
        """设置地图数据和渲染器"""
        self.map_data = map_data
        self.map_renderer = map_renderer
        self.need_redraw = True

        # 计算缩放比例
        if self.map_data:
            self.scale_x = self.width / self.map_data.width
            self.scale_y = self.height / self.map_data.height

    def update_viewport(self, offset_x, offset_y, viewport_width, viewport_height):
        """更新视口信息"""
        # 转换地图偏移和视口大小到小地图坐标
        if self.map_renderer and self.map_renderer.tile_size > 0:
            tile_size = self.map_renderer.tile_size * self.map_renderer.zoom
            map_x = offset_x / tile_size
            map_y = offset_y / tile_size
            width_tiles = viewport_width / tile_size
            height_tiles = viewport_height / tile_size

            # 计算视口在小地图上的位置和大小
            self.cursor_pos = (int(map_x * self.scale_x), int(map_y * self.scale_y))
            self.cursor_size = (
                int(width_tiles * self.scale_x),
                int(height_tiles * self.scale_y),
            )

    def redraw_minimap(self):
        """重新绘制小地图"""
        if not self.map_data:
            return

        self.surface = pygame.Surface((self.width, self.height))
        self.surface.fill((30, 30, 30))

        # 绘制地图格子
        for y in range(self.map_data.height):
            for x in range(self.map_data.width):
                tile = self.map_data.get_tile(x, y)
                if tile:
                    # 计算小地图上的像素坐标
                    pixel_x = int(x * self.scale_x)
                    pixel_y = int(y * self.scale_y)
                    pixel_width = max(1, int(self.scale_x))
                    pixel_height = max(1, int(self.scale_y))

                    # 绘制格子
                    rect = pygame.Rect(pixel_x, pixel_y, pixel_width, pixel_height)
                    pygame.draw.rect(self.surface, tile.color, rect)

        self.need_redraw = False

    def render(self, surface):
        """渲染小地图"""
        # 如果需要重新绘制小地图
        if self.need_redraw:
            self.redraw_minimap()

        # 绘制小地图背景
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, (40, 40, 40), panel_rect)

        # 绘制小地图内容
        if self.surface:
            surface.blit(self.surface, (self.x, self.y))

        # 绘制当前视口框
        if self.cursor_size[0] > 0 and self.cursor_size[1] > 0:
            cursor_rect = pygame.Rect(
                self.x + self.cursor_pos[0],
                self.y + self.cursor_pos[1],
                self.cursor_size[0],
                self.cursor_size[1],
            )
            pygame.draw.rect(surface, (255, 255, 255), cursor_rect, 2)

        # 绘制边框
        pygame.draw.rect(surface, (120, 120, 120), panel_rect, 2)

        super().render(surface)

    def handle_click(self, pos):
        """处理小地图上的点击，返回对应的地图坐标"""
        if not self.map_data:
            return None

        # 计算小地图内的相对坐标
        rel_x = pos[0] - self.x
        rel_y = pos[1] - self.y

        # 检查是否在小地图范围内
        if 0 <= rel_x < self.width and 0 <= rel_y < self.height:
            # 转换为地图格子坐标
            map_x = int(rel_x / self.scale_x)
            map_y = int(rel_y / self.scale_y)

            # 确保坐标合法
            map_x = max(0, min(map_x, self.map_data.width - 1))
            map_y = max(0, min(map_y, self.map_data.height - 1))

            return (map_x, map_y)

        return None
