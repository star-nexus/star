# game.py
import sys
import pygame
import numpy as np
import os
from map_generator.map import MapGenerator
from entity.unit import UnitController


class GameSettings:
    def __init__(self, player_mode="human"):
        # Map settings
        self.map_width = 25
        self.map_height = 25
        self.tile_size = 32
        
        # Window settings
        self.window_width = self.map_width * self.tile_size
        self.window_height = self.map_height * self.tile_size
        
        # Game state
        self.player_mode = player_mode
        self.vision_mode = 1
        self.winner = None
        self.show_mouse_pos = True
        
        # Frame settings
        self.save_interval = 300
        self.action_interval = 30


class Game:
    def __init__(self, settings: GameSettings):
        self.settings = settings
        self.init_pygame()

    def init_pygame(self):
        """Initialize Pygame and set up the display."""
        pygame.init()
        self.screen = pygame.display.set_mode((self.settings.window_width, self.settings.window_height))
        pygame.display.set_caption("Romance-of-the-Three-Kingdoms")
        self.font = pygame.font.SysFont(None, 24)
        self.win_font = pygame.font.SysFont(None, 72)
        
    def quit_pygame(self):
        """Quit pygame."""
        pygame.quit()



def main():
    # 初始化 Pygame
    settings = GameSettings()
    game = Game(settings)
    # 判断玩家模式
    if len(sys.argv) > 1 and sys.argv[1] == "ai":
        settings.player_mode = "ai"

    # 创建地图生成器
    generator = MapGenerator(settings.map_width, settings.map_height, "map_generator/map_tiles")

    # 生成环境地图和单位地图
    environment_map, unit_map = generator.generate_maps(r_unit_count=10, w_unit_count=10)
    # 创建单位控制器
    unit_controller = UnitController(environment_map, unit_map, tile_size=settings.tile_size)

    running = True
    clock = pygame.time.Clock()

    frame_count = 0

    def save_env_status():
        with open("run_log/env_status.txt", "w") as f:
            # 记录环境信息
            # 如地图大小、双方单位数量统计
            f.write(f"MapSize: {settings.map_width}x{settings.map_height}\n")
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
        mouse_grid_x = mouse_x // settings.tile_size
        mouse_grid_y = mouse_y // settings.tile_size
        frame_count += 1
        if frame_count % settings.save_interval == 0:
            # 周期性保存当前状态
            save_env_status()
            save_unit_status()
        # 如果是AI模式，每秒(30帧)执行一次动作周期
        if game.settings.player_mode == "ai" and frame_count % game.settings.action_interval == 0:
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

                        if sel_info is None:
                            # 未选中单位，无法攻击
                            continue
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

        game.screen.fill((0, 0, 0))
        highlight_pos = None
        selected = unit_controller.selected_unit
        if selected:
            highlight_pos = (selected[0], selected[1])

        # 根据vision_mode计算visible_map
        if game.settings.vision_mode == 1:
            visible_map = None  # 上帝视角全部可见
        else:
            faction = "R" if game.settings.vision_mode == 2 else "W"
            visible_map = unit_controller.compute_visibility(faction, vision_range=2)

        # 获取路径以显示
        path_to_show = unit_controller.get_unit_path()

        # 渲染地图
        generator.render_map(
            game.screen,
            environment_map,
            unit_map,
            highlight_pos=highlight_pos,
            visible_map=visible_map,
            path_to_show=path_to_show,
        )

        # 显示文字提示
        if selected:
            u_type = selected[2]
            text = game.font.render(
                f"selected: {u_type} at ({selected[1]}, {selected[0]})",
                True,
                (255, 255, 255),
            )
            game.screen.blit(text, (10, 10))
        else:
            text = game.font.render("Cannot select", True, (255, 255, 255))
            game.screen.blit(text, (10, 10))
        # 显示玩家模式
        mode_text = game.font.render(f"Play Mode: {game.settings.player_mode}", True, (255, 255, 255))
        game.screen.blit(mode_text, (10, 30))

        # 显示视角模式
        vision_text = "God" if game.settings.vision_mode == 1 else ("R" if game.settings.vision_mode == 2 else "W")
        v_text = game.font.render(f"View Mode: {vision_text}", True, (255, 255, 255))
        game.screen.blit(v_text, (10, 50))

        # 显示鼠标位置
        mouse_text = game.font.render(
            f"Mouse: ({mouse_grid_x}, {mouse_grid_y})", True, (255, 255, 255)
        )
        game.screen.blit(mouse_text, (10, 70))

        # 如果有目标点，显示目标点位置
        if unit_controller.selected_unit_index in unit_controller.target_positions:
            ty, tx = unit_controller.target_positions[
                unit_controller.selected_unit_index
            ]
            target_text = game.font.render(f"Aim: ({tx}, {ty})", True, (255, 255, 255))
            game.screen.blit(target_text, (10, 90))

        # 如果有胜者，显示胜利信息并停止交互
        if game.settings.winner is not None:
            if game.settings.winner == "平局":
                win_color = (255, 0, 0)  # 平局红色
            else:
                win_color = (0, 255, 0)  # 获胜绿色
            win_text = game.win_font.render(game.settings.winner, True, win_color)
            win_rect = win_text.get_rect(center=(game.settings.window_width // 2, game.settings.window_height // 2))
            game.screen.blit(win_text, win_rect)
        # 更新显示
        pygame.display.flip()

    game.quit_pygame()


if __name__ == "__main__":
    main()
