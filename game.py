# game.py
import sys
import pygame
import numpy as np
import os
from map_generator.map_data_generator import generate_map_data
from controller.unit import UnitController


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
            "forest",
            "bridge",
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

    # [弃用] : 改成静态环境地图 env_map 和 单位移动地图 unit_map, 方便控制与逻辑分离
    # TODO : 需要对 generate_map_data 进行修改，使其返回两个矩阵
    # def generate_map_matrix(self):
    #     """Generate random map matrix with place types"""
    #     map_matrix = generate_map_data(self.width)
    #     return map_matrix

    # [暂用] : 生成环境地图和单位地图, 但属于增量修改的临时方案,
    #         有弊端 map init 时刻的地形无法获取, 未来需要修改 generate_map_data
    def generate_maps(self, r_units, w_units):
        # 生成环境地图
        environment_map, unit_map = generate_map_data(self.width, r_units, w_units)
        # # unit_map 初始化为相同大小，全None
        # unit_map = np.full((self.height, self.width), None, dtype=object)

        # # 从environment_map中分离出单位
        # # 原本generate_map_data返回一个混合的地图，这里我们要把部队分离到unit_map中
        # for i in range(self.height):
        #     for j in range(self.width):
        #         cell = environment_map[i][j]
        #         if cell.startswith("R_") or cell.startswith("W_"):
        #             unit_map[i][j] = cell
        #             # 单位位置原地形设为plain（或检查原地形）
        #             environment_map[i][j] = "plain"
        return environment_map, unit_map

    def render_map(
        self, surface, environment_map, unit_map, highlight_pos=None, visible_map=None
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
                            # x = j * self.tile_size
                            # y = i * self.tile_size
                            # surface.blit(unit_tile, (x, y))
                            # # 如果有高亮位置，并且此单位是被选中的单位，则高亮
                            # if highlight_pos and highlight_pos == (i, j):
                            #     # 画一个半透明矩形以示高亮
                            #     s = pygame.Surface((self.tile_size, self.tile_size))
                            #     s.set_alpha(100)
                            #     s.fill((255, 255, 0))
                            #     surface.blit(s, (x, y))
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


def main():
    # 初始化 Pygame
    pygame.init()

    # 判断玩家模式
    if len(sys.argv) > 1 and sys.argv[1] == "ai":
        player_mode = "ai"
    else:
        player_mode = "human"

    # 设置地图尺寸
    map_width, map_height = 25, 25  # 可以根据需要调整
    tile_size = 32

    # 计算窗口尺寸
    window_width = map_width * tile_size
    window_height = map_height * tile_size

    r_units = 10
    w_units = 10

    # 创建窗口（必须在加载图像前）
    screen = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("Romance-of-the-Three-Kingdoms")

    # 创建地图生成器
    generator = MapGenerator(map_width, map_height)

    # 生成地图矩阵(弃用)
    # map_matrix = generator.generate_map_matrix()

    # 生成环境地图和单位地图
    environment_map, unit_map = generator.generate_maps(
        r_units=r_units, w_units=w_units
    )
    # 创建单位控制器
    unit_controller = UnitController(environment_map, unit_map, tile_size=tile_size)

    # 填充背景为黑色
    # screen.fill((0, 0, 0))

    # 找到一个可控制的军队单位(示例：第一个R开头的单位)
    # selected_unit_pos = None
    # selected_unit_type = None
    # for i in range(map_height):
    #     for j in range(map_width):
    #         cell = map_matrix[i][j]
    #         if cell.startswith("R_") or cell.startswith("W_"):
    #             selected_unit_pos = [i, j]  # 保存行为列表以便修改
    #             selected_unit_type = cell
    #             break
    #     if selected_unit_pos is not None:
    #         break

    font = pygame.font.SysFont(None, 24)
    win_font = pygame.font.SysFont(None, 72)
    vision_mode = 1
    winner = None

    running = True
    clock = pygame.time.Clock()

    # 主循环
    while running:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # 移动或切换单位
                if event.key == pygame.K_UP:
                    unit_controller.move_unit("up")
                elif event.key == pygame.K_DOWN:
                    unit_controller.move_unit("down")
                elif event.key == pygame.K_LEFT:
                    unit_controller.move_unit("left")
                elif event.key == pygame.K_RIGHT:
                    unit_controller.move_unit("right")
                elif event.key == pygame.K_TAB:
                    # 循环切换当前选择的单位
                    new_index = (unit_controller.selected_unit_index + 1) % len(
                        unit_controller.units_positions
                    )
                    unit_controller.select_unit_by_index(new_index)
                elif event.key == pygame.K_1:  # 上帝视角
                    vision_mode = 1
                elif event.key == pygame.K_2:  # R 阵营视角
                    vision_mode = 2
                elif event.key == pygame.K_3:  # W 阵营视角
                    vision_mode = 3
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键选择单位
                    pos = pygame.mouse.get_pos()
                    unit_controller.select_unit_by_mouse(pos)

        # 战斗后检查两方剩余单位，如果无单位则另一方获胜
        # 根据阵营计数单位
        R_units = [u for u in unit_controller.units_positions if u[2].startswith("R_")]
        W_units = [u for u in unit_controller.units_positions if u[2].startswith("W_")]
        if not R_units and not W_units:
            # 双方无单位？平局处理
            winner = "Peace"
        elif not R_units:
            winner = "W win"
        elif not W_units:
            winner = "R Win"

        screen.fill((0, 0, 0))
        highlight_pos = None
        selected = unit_controller.selected_unit
        if selected:
            highlight_pos = (selected[0], selected[1])

        # 根据vision_mode计算visible_map
        if vision_mode == 1:
            visible_map = None  # 上帝视角全部可见
        else:
            faction = "R" if vision_mode == 2 else "W"
            visible_map = unit_controller.compute_visibility(faction, vision_range=2)

        # 渲染地图
        generator.render_map(
            screen,
            environment_map,
            unit_map,
            highlight_pos=highlight_pos,
            visible_map=visible_map,
        )

        # 显示文字提示
        if selected:
            u_type = selected[2]
            text = font.render(
                f"selected: {u_type} at ({selected[1]}, {selected[0]})",
                True,
                (255, 255, 255),
            )
            screen.blit(text, (10, 10))
        else:
            text = font.render("Cannot select", True, (255, 255, 255))
            screen.blit(text, (10, 10))
        # 显示玩家模式
        mode_text = font.render(f"Play Mode: {player_mode}", True, (255, 255, 255))
        screen.blit(mode_text, (10, 30))

        # 显示视角模式
        vision_text = "God" if vision_mode == 1 else ("R" if vision_mode == 2 else "W")
        v_text = font.render(f"View Mode: {vision_text}", True, (255, 255, 255))
        screen.blit(v_text, (10, 50))

        # 如果有胜者，显示胜利信息并停止交互
        if winner is not None:
            if winner == "平局":
                win_color = (255, 0, 0)  # 平局红色
            else:
                win_color = (0, 255, 0)  # 获胜绿色
            win_text = win_font.render(winner, True, win_color)
            win_rect = win_text.get_rect(center=(window_width // 2, window_height // 2))
            screen.blit(win_text, win_rect)
        # 更新显示
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
