import sys
import os
import pygame
import math

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.game_engine import GameEngine
from framework_v2.engine.scenes import Scene, scene_manager
from framework_v2.engine.renders import render_engine


class MenuScene(Scene):
    """主菜单场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = None
        self.selected_option = 0
        self.options = ["开始游戏", "退出"]

    def enter(self, **kwargs):
        super().enter(**kwargs)
        self.font = pygame.font.Font(None, 48)
        print("进入主菜单")

    def exit(self):
        super().exit()
        print("退出主菜单")

    def update(self, delta_time: float):
        pass

    def render(self):
        render = render_engine()

        # 背景
        render.fill((20, 30, 50))

        # 标题
        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            text_rect = text_surface.get_rect(center=pos)
            screen.blit(text_surface, text_rect)

        render.custom(draw_text, "三国演义", (400, 150), (255, 255, 255), self.font)

        # 菜单选项
        for i, option in enumerate(self.options):
            color = (255, 255, 0) if i == self.selected_option else (200, 200, 200)
            y_pos = 250 + i * 60
            render.custom(draw_text, option, (400, y_pos), color, self.font)

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_option = (self.selected_option - 1) % len(self.options)
                return True
            elif event.key == pygame.K_DOWN:
                self.selected_option = (self.selected_option + 1) % len(self.options)
                return True
            elif event.key == pygame.K_RETURN:
                if self.selected_option == 0:  # 开始游戏
                    scene_manager().switch_to("game")
                elif self.selected_option == 1:  # 退出
                    self.engine.stop()
                return True
        return False


class GameScene(Scene):
    """游戏场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.player_pos = [400, 300]
        self.player_vel = [0, 0]
        self.enemies = []
        self.score = 0
        self.spawn_timer = 0

    def enter(self, **kwargs):
        super().enter(**kwargs)
        self.player_pos = [400, 300]
        self.enemies = []
        self.score = 0
        print("开始游戏")

    def update(self, delta_time: float):
        # 更新玩家位置
        keys = pygame.key.get_pressed()
        speed = 200

        self.player_vel = [0, 0]
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player_vel[0] = -speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player_vel[0] = speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.player_vel[1] = -speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.player_vel[1] = speed

        # 更新玩家位置
        self.player_pos[0] += self.player_vel[0] * delta_time
        self.player_pos[1] += self.player_vel[1] * delta_time

        # 边界检查
        self.player_pos[0] = max(25, min(775, self.player_pos[0]))
        self.player_pos[1] = max(25, min(575, self.player_pos[1]))

        # 生成敌人
        self.spawn_timer += delta_time
        if self.spawn_timer > 2.0:
            self.spawn_timer = 0
            enemy_x = 800 if len(self.enemies) % 2 == 0 else 0
            enemy_y = 100 + (len(self.enemies) * 50) % 400
            self.enemies.append([enemy_x, enemy_y, -100 if enemy_x > 400 else 100, 0])

        # 更新敌人
        for enemy in self.enemies[:]:
            enemy[0] += enemy[2] * delta_time
            enemy[1] += enemy[3] * delta_time

            # 移除屏幕外的敌人
            if enemy[0] < -50 or enemy[0] > 850:
                self.enemies.remove(enemy)
                continue

            # 碰撞检测
            dx = enemy[0] - self.player_pos[0]
            dy = enemy[1] - self.player_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < 40:
                scene_manager().switch_to("menu")
                return

        self.score += int(delta_time * 10)

    def render(self):
        render = render_engine()

        # 游戏背景
        render.fill((10, 50, 20))

        # 绘制玩家
        render.circle(
            (0, 255, 0), (int(self.player_pos[0]), int(self.player_pos[1])), 20
        )

        # 绘制敌人
        for enemy in self.enemies:
            render.rect(
                (255, 0, 0), pygame.Rect(int(enemy[0] - 15), int(enemy[1] - 15), 30, 30)
            )

        # 绘制UI
        font = pygame.font.Font(None, 36)

        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            screen.blit(text_surface, pos)

        render.custom(
            draw_text, f"分数: {self.score}", (10, 10), (255, 255, 255), font
        ).custom(draw_text, "WASD/方向键移动", (10, 50), (255, 255, 255), font).custom(
            draw_text, "ESC返回菜单", (10, 90), (255, 255, 255), font
        )

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                scene_manager().switch_to("menu")
                return True
        return False


def main():
    """主函数"""
    # 创建游戏引擎
    engine = GameEngine(title="简化游戏引擎示例", width=800, height=600, fps=60)

    # 注册场景
    sm = scene_manager()
    sm.register_scene("menu", MenuScene)
    sm.register_scene("game", GameScene)

    # 启动主菜单
    sm.switch_to("menu")

    # 运行游戏
    print("游戏启动...")
    print("控制说明：")
    print("- 方向键/WASD：移动")
    print("- 回车：选择")
    print("- ESC：返回菜单")
    print("- 避开红色方块，获得高分！")

    engine.run()


if __name__ == "__main__":
    main()
