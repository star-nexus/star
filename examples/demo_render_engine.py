import sys
import os
import pygame
import math

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.renders import render_engine


def main():
    """测试渲染引擎功能"""
    # 初始化 Pygame
    pygame.init()

    # 设置窗口
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("渲染引擎测试")
    clock = pygame.time.Clock()

    # 获取渲染引擎实例
    render = render_engine()
    render.set_screen(screen)

    # 创建一些测试表面
    sprite_surface = pygame.Surface((50, 50))
    sprite_surface.fill((255, 255, 0))  # 黄色方块

    # 定义颜色
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    PURPLE = (128, 0, 128)
    ORANGE = (255, 165, 0)

    frame_count = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # 清空屏幕 (背景层)
        render.fill(BLACK, layer=0)

        # 测试基础形状绘制 (第1层)
        render.set_layer(1)
        render.rect(RED, pygame.Rect(50, 50, 100, 80)).circle(
            GREEN, (200, 100), 40
        ).line(BLUE, (300, 50), (400, 150), 3)

        # 测试多边形和椭圆 (第2层)
        with render.layer(2):
            # 绘制三角形
            triangle_points = [(500, 50), (450, 150), (550, 150)]
            render.polygon(PURPLE, triangle_points)

            # 绘制椭圆
            render.ellipse(ORANGE, pygame.Rect(600, 50, 120, 80), 2)

        # 测试动画效果 (第3层)
        angle = frame_count * 0.1
        center_x, center_y = 400, 300

        # 旋转的线条
        for i in range(8):
            line_angle = angle + i * math.pi / 4
            start_x = center_x + math.cos(line_angle) * 20
            start_y = center_y + math.sin(line_angle) * 20
            end_x = center_x + math.cos(line_angle) * 80
            end_y = center_y + math.sin(line_angle) * 80

            render.line(
                WHITE,
                (int(start_x), int(start_y)),
                (int(end_x), int(end_y)),
                2,
                layer=3,
            )

        # 绘制移动的精灵 (第4层)
        sprite_x = 100 + math.sin(frame_count * 0.05) * 200
        sprite_y = 400 + math.cos(frame_count * 0.03) * 100
        render.draw(sprite_surface, (int(sprite_x), int(sprite_y)), layer=4)

        # 测试弧形和连线 (第5层)
        render.set_layer(5)

        # 绘制弧形
        arc_rect = pygame.Rect(50, 400, 100, 100)
        render.arc(RED, arc_rect, 0, math.pi, 3)
        render.arc(GREEN, arc_rect, math.pi, 2 * math.pi, 3)

        # 绘制波浪线
        wave_points = []
        for x in range(0, 200, 10):
            y = 500 + math.sin((x + frame_count * 2) * 0.1) * 30
            wave_points.append((x + 200, int(y)))

        if len(wave_points) > 1:
            render.lines(BLUE, False, wave_points, 2)

        # 测试自定义绘制函数 (第6层)
        def draw_gradient_rect(screen, rect, color1, color2):
            """绘制渐变矩形"""
            for i in range(rect.height):
                ratio = i / rect.height
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                pygame.draw.line(
                    screen,
                    (r, g, b),
                    (rect.x, rect.y + i),
                    (rect.x + rect.width, rect.y + i),
                )

        gradient_rect = pygame.Rect(600, 400, 150, 100)
        render.custom(draw_gradient_rect, gradient_rect, RED, BLUE, layer=6)

        # 绘制信息文本 (最上层)
        font = pygame.font.SysFont("pingfang", 36)

        def draw_text(screen, text, pos, color):
            text_surface = font.render(text, True, color)
            screen.blit(text_surface, pos)

        render.custom(
            draw_text, f"帧数: {frame_count}", (10, 10), WHITE, layer=10
        ).custom(draw_text, "按ESC退出", (10, 560), WHITE, layer=10)

        # 执行渲染
        render.update()

        # 更新显示
        pygame.display.flip()
        clock.tick(60)
        frame_count += 1

    pygame.quit()


if __name__ == "__main__":
    print("启动渲染引擎测试...")
    print("功能演示：")
    print("- 多层渲染")
    print("- 基础几何图形")
    print("- 动画效果")
    print("- 自定义绘制函数")
    print("- 链式调用API")
    print("- 上下文管理器")
    print()

    main()
