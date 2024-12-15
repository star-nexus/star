# game.py
import sys
import pygame
import numpy as np
import os
from map_generator.map_data_generator import generate_map_data
from entity.unit import UnitController


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
    # 用于显示坐标信息
    show_mouse_pos = True

    running = True
    clock = pygame.time.Clock()

    frame_count = 0
    save_interval = 300  # 每300帧执行一次读写
    action_interval = 30

    def save_env_status():
        with open("run_log/env_status.txt", "w") as f:
            # 记录环境信息
            # 如地图大小、双方单位数量统计
            f.write(f"MapSize: {map_width}x{map_height}\n")
            faction_counts = unit_controller.get_faction_unit_counts()
            f.write(
                "R Force: ping={ping} shui={shui} shan={shan}\n".format(
                    **faction_counts["R"]
                )
            )
            f.write(
                "W Force: ping={ping} shui={shui} shan={shan}\n".format(
                    **faction_counts["W"]
                )
            )
            # 还可记录其他环境信息，例如terrain统计（可选）

    def save_unit_status():
        with open("run_log/unit_status.txt", "w") as f:
            units_info = unit_controller.get_all_units_info()
            # 格式: unit_id, utype, x, y, state
            for uid, uy, ux, ut, state in units_info:
                f.write(f"unit_id:{uid} type:{ut} x:{ux} y:{uy} state:{state}\n")

    def load_unit_actions():
        # 尝试读取 unit_action.txt，如有则解析指令
        if not os.path.exists("run_log/unit_action.txt"):
            return
        with open("run_log/unit_action.txt", "r") as f:
            lines = f.readlines()
        # 格式设定为: unit_id action param...
        # move命令： <unit_id> move ty tx
        # attack命令：<unit_id> attack target_unit_id
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            unit_id = int(parts[0])
            action = parts[1]
            if action == "move" and len(parts) == 4:
                ty, tx = int(parts[2]), int(parts[3])
                unit_controller.execute_action(unit_id, "move", (ty, tx))
            elif action == "attack" and len(parts) == 3:
                target_uid = int(parts[2])
                unit_controller.execute_action(unit_id, "attack", target_uid)
        # 读取后可清空文件或重命名
        # 避免重复执行同样指令:
        # os.remove("unit_action.txt")
        # 或者将其清空
        # open("unit_action.txt", "w").close()

    # 主循环
    while running:
        clock.tick(30)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        mouse_grid_x = mouse_x // tile_size
        mouse_grid_y = mouse_y // tile_size
        frame_count += 1
        if frame_count % save_interval == 0:
            # 周期性保存当前状态
            save_env_status()
            save_unit_status()
        # 如果是AI模式，每秒(30帧)执行一次动作周期
        if player_mode == "ai" and frame_count % action_interval == 0:
            # 读取AI指令并执行
            load_unit_actions()
            # 执行所有单位的移动与攻击动作
            # step_along_path()可被多次调用，一般对selected_unit_index操作
            # 可遍历所有单位来进行移动执行:
            for uid, (uy, ux, ut) in unit_controller.unit_id_map.copy().items():
                # 为了处理多个单位，可暂时选中相应unit_id，再step
                unit_controller.selected_unit_index = uid
                unit_controller.step_along_path()  # 每秒走一步
                # 攻击逻辑如有需要在step_along_path或execute_action里触发

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
                elif event.key == pygame.K_g:
                    # 假设按下 G 键后，为选中单位规划路径到某个目标坐标(ty, tx)

                    pos_info = unit_controller.get_unit_info_by_pos(
                        mouse_grid_y, mouse_grid_x
                    )
                    uid = unit_controller.selected_unit_id
                    if pos_info == None:
                        # unit_controller.plan_path_to(mouse_grid_y, mouse_grid_x, "move")
                        if uid is not None:
                            # 尝试移动或攻击到鼠标格子
                            unit_controller.execute_action(
                                uid, "move", (mouse_grid_y, mouse_grid_x)
                            )
                    else:
                        sel_info = unit_controller.get_selected_unit_info()

                        if pos_info["utype"][0] != sel_info["utype"][0]:
                            if uid is not None:
                                # 尝试移动或攻击到鼠标格子
                                tid = unit_controller.find_unit_id_by_pos(
                                    mouse_grid_y, mouse_grid_x
                                )
                                unit_controller.execute_action(uid, "attack", tid)
                        else:
                            if uid is not None:
                                # 尝试移动或攻击到鼠标格子
                                unit_controller.execute_action(
                                    uid, "move", (mouse_grid_y, mouse_grid_x)
                                )
                            # unit_controller.plan_path_to(
                            #     mouse_grid_y, mouse_grid_x, "move"
                            # )

                    # unit_controller.plan_path_to(ty, tx)
                elif event.key == pygame.K_h:
                    # 按下 H 键让单位沿路径前进一步
                    unit_controller.step_along_path()
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

        # 获取路径以显示
        path_to_show = unit_controller.get_unit_path()

        # 渲染地图
        generator.render_map(
            screen,
            environment_map,
            unit_map,
            highlight_pos=highlight_pos,
            visible_map=visible_map,
            path_to_show=path_to_show,
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

        # 显示鼠标位置
        mouse_text = font.render(
            f"Mouse: ({mouse_grid_x}, {mouse_grid_y})", True, (255, 255, 255)
        )
        screen.blit(mouse_text, (10, 70))

        # 如果有目标点，显示目标点位置
        if unit_controller.selected_unit_index in unit_controller.target_positions:
            ty, tx = unit_controller.target_positions[
                unit_controller.selected_unit_index
            ]
            target_text = font.render(f"Aim: ({tx}, {ty})", True, (255, 255, 255))
            screen.blit(target_text, (10, 90))

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
