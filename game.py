# map_pygame.py
import pygame
import numpy as np
import os
from map_generator.map_data_generator import generate_map_data


class MapGenerator:

    def __init__(self, width, height, image_dir="map_generator/map_tiles"):
        """Initialize map generator with dimensions and image directory"""
        self.width = width
        self.height = height
        self.image_dir = image_dir
        self.place_types = [
            "mountain",
            "river",
            "plain",
            "city",
            "R_ping",
            "R_shui",
            "R_shan",
            "W_ping",
            "W_shui",
            "W_shan",
        ]
        self.tile_size = 32  # Tile size in pixels
        self.tile_images = self._load_tile_images()

    def _load_tile_images(self):
        """Load tile images from directory using pygame"""
        tile_images = {}
        for place_type in self.place_types:
            image_path = os.path.join(
                self.image_dir, f"{place_type}.png"
            )  # 使用 PNG 格式更适合 Pygame
            if not os.path.exists(image_path):
                print(f"Warning: Image for {place_type} not found at {image_path}")
                continue
            try:
                img = pygame.image.load(image_path).convert_alpha()
                tile_images[place_type] = pygame.transform.scale(
                    img, (self.tile_size, self.tile_size)
                )
            except pygame.error as e:
                print(f"Error loading image {image_path}: {e}")
        return tile_images

    def generate_map_matrix(self):
        """Generate random map matrix with place types"""
        map_matrix = generate_map_data(self.width)
        return map_matrix

    def render_map(self, surface, map_matrix):
        """Render the map onto the given Pygame surface"""
        for i in range(self.height):
            for j in range(self.width):
                place_type = map_matrix[i][j]
                tile_image = self.tile_images.get(
                    place_type, self.tile_images.get("plain")
                )  # 默认使用 plain
                if tile_image:
                    x = j * self.tile_size
                    y = i * self.tile_size
                    surface.blit(tile_image, (x, y))


def main():
    # 初始化 Pygame
    pygame.init()

    # 设置地图尺寸
    map_width, map_height = 25, 25  # 可以根据需要调整
    tile_size = 32

    # 计算窗口尺寸
    window_width = map_width * tile_size
    window_height = map_height * tile_size

    # 创建窗口（必须在加载图像前）
    screen = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("Map Generator")

    # 创建地图生成器
    generator = MapGenerator(map_width, map_height)

    # 生成地图矩阵
    map_matrix = generator.generate_map_matrix()

    # 填充背景为黑色
    screen.fill((0, 0, 0))

    # 找到一个可控制的军队单位(示例：第一个R开头的单位)
    selected_unit_pos = None
    selected_unit_type = None
    for i in range(map_height):
        for j in range(map_width):
            cell = map_matrix[i][j]
            if cell.startswith("R_") or cell.startswith("W_"):
                selected_unit_pos = [i, j]  # 保存行为列表以便修改
                selected_unit_type = cell
                break
        if selected_unit_pos is not None:
            break

    # 渲染地图
    generator.render_map(screen, map_matrix)

    # 更新显示
    pygame.display.flip()

    running = True
    clock = pygame.time.Clock()

    # 主循环
    while running:
        clock.tick(30)  # 每秒30帧

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and selected_unit_pos is not None:
                # 控制单位移动
                new_pos = selected_unit_pos.copy()
                if event.key == pygame.K_UP:
                    new_pos[0] -= 1
                elif event.key == pygame.K_DOWN:
                    new_pos[0] += 1
                elif event.key == pygame.K_LEFT:
                    new_pos[1] -= 1
                elif event.key == pygame.K_RIGHT:
                    new_pos[1] += 1

                # 检查新位置是否在地图范围内
                if 0 <= new_pos[0] < map_height and 0 <= new_pos[1] < map_width:
                    # 根据需求，可以检查一下新地形是否允许通过
                    # 例如我们简单的规则：不要走到河流上
                    target_cell = map_matrix[new_pos[0]][new_pos[1]]
                    if target_cell not in [
                        "river",
                        "mountain",
                    ]:  # 假设不能走到河流和山上
                        # 将旧位置还原为plain（或其他记忆的原本地形，这里简化）
                        old_y, old_x = selected_unit_pos
                        # 假设单位之前所在的格子为plain（简单起见）
                        # 如果希望恢复原本地形，需要额外记录或使用更复杂的逻辑
                        map_matrix[old_y][old_x] = "plain"

                        # 更新新位置为单位
                        map_matrix[new_pos[0]][new_pos[1]] = selected_unit_type
                        selected_unit_pos = new_pos

                        # 移动后重新渲染地图
                        screen.fill((0, 0, 0))
                        generator.render_map(screen, map_matrix)
                        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
