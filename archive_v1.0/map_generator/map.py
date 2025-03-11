import numpy as np
from PIL import Image
import os
import random
from .map_data_generator import generate_map_data
from .unit_data_generator import generate_unit_data
import pygame


class MapGenerator:
    def __init__(self, width, height, image_dir="map_tiles"):
        """Initialize map generator with dimensions and image directory"""
        self.width = width
        self.height = height
        self.image_dir = image_dir
        self.place_types = [
            "mountain",
            "river",
            "plain",
            "city",
            "forest",
            "bridge",
            "R_ping",
            "R_shui",
            "R_shan",
            "W_ping",
            "W_shui",
            "W_shan",
        ]
        self.tile_size = 32  # Default tile size in pixels
        self.tile_images = self._load_tile_images()

    def _load_tile_images(self):
        """Load tile images from directory"""
        tile_images = {}
        for place_type in self.place_types:
            image_path = os.path.join(self.image_dir, f"{place_type}.png")
            try:
                if not os.path.exists(image_path):
                    print(f"Warning: Image file not found: {image_path}")
                    # Create a default colored tile as fallback
                    surface = pygame.Surface((self.tile_size, self.tile_size))
                    surface.fill((100, 100, 100))  # Gray color as default
                    tile_images[place_type] = surface
                else:
                    img = pygame.image.load(image_path).convert_alpha()
                    tile_images[place_type] = pygame.transform.scale(
                        img, (self.tile_size, self.tile_size)
                    )
            except Exception as e:
                print(f"Error loading {place_type}: {str(e)}")
                # Create a default colored tile
                surface = pygame.Surface((self.tile_size, self.tile_size))
                surface.fill((100, 100, 100))  # Gray color as default
                tile_images[place_type] = surface
        return tile_images

    def generate_maps(self, r_unit_count=3, w_unit_count=3):
        """Main method to generate complete map"""
        map_matrix = generate_map_data(self.width)
        unit_data = generate_unit_data(map_matrix, r_unit_count, w_unit_count)
        # print(unit_data)
        # print(map_matrix)
        return map_matrix, unit_data

    def render_map(
        self,
        surface,
        environment_map,
        unit_map,
        highlight_pos=None,
        visible_map=None,
        path_to_show=None,
    ):
        """Render the map onto the given Pygame surface"""

        # 在R/W模式下，仅渲染可见的单位。上帝视角仍渲染所有
        # 判断是否是上帝视角（vision_mode=1）还是R/W视角（2或3）
        # 可通过传入的visible_map是否为None判断，上帝视角visible_map=None
        for i in range(self.height):
            for j in range(self.width):
                # 先渲染环境
                place_type = environment_map[i][j]
                base_tile = self.tile_images.get(
                    place_type, self.tile_images.get("plain")
                )
                if base_tile:
                    x = j * self.tile_size
                    y = i * self.tile_size
                    surface.blit(base_tile, (x, y))

                # 再渲染单位（如果有）
                unit = unit_map[i][j]
                if unit is not None:
                    if visible_map is None or visible_map[i][j]:
                        unit_tile = self.tile_images.get(unit, None)
                        if unit_tile:
                            surface.blit(unit_tile, (x, y))
                            if highlight_pos and highlight_pos == (i, j):
                                s = pygame.Surface((self.tile_size, self.tile_size))
                                s.set_alpha(100)
                                s.fill((255, 255, 0))
                                surface.blit(s, (x, y))

        # 如果有路径，要高亮路径
        if path_to_show:
            for py, px in path_to_show:
                # 绘制半透明蓝色覆盖表示路径
                x = px * self.tile_size
                y = py * self.tile_size
                s = pygame.Surface((self.tile_size, self.tile_size))
                s.set_alpha(100)
                s.fill((0, 0, 255))
                surface.blit(s, (x, y))
        # 如果有 visible_map，进行战争迷雾处理
        if visible_map is not None:
            h, w = visible_map.shape
            for i in range(h):
                for j in range(w):
                    if not visible_map[i][j]:
                        # 不可见处盖一层黑色半透明遮罩
                        x = j * self.tile_size
                        y = i * self.tile_size
                        fog = pygame.Surface((self.tile_size, self.tile_size))
                        fog.fill((0, 0, 0))
                        fog.set_alpha(200)
                        surface.blit(fog, (x, y))


# Example usage:
# if __name__ == "__main__":

#     pygame.init()

#     # Set up display
#     width, height = 800, 800
#     screen = pygame.display.set_mode((width, height))
#     pygame.display.set_caption("Map Generator Test")

#     # Set up map
#     map_width = 20
#     map_height = 20
#     game_map = MapGenerator(map_width, map_height)
#     environment_map, unit_map = game_map.generate_map()

#     # Game loop
#     running = True
#     while running:
#         for event in pygame.event.get():
#             if event.type == pygame.QUIT:
#                 running = False

#         screen.fill((100, 100, 100))  # Fill the screen with black
#         game_map.render_map(screen, environment_map, unit_map)
#         pygame.display.flip()

#     pygame.quit()
