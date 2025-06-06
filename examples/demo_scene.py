import sys
import os
import pygame

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.scenes import Scene, SceneManager
from framework_v2.engine.renders import RenderEngine
from framework_v2.engine.inputs import InputSystem
from framework_v2.engine.events import EventBus


class MenuScene(Scene):
    """主菜单场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.font = None
        self.selected_option = 0
        self.options = ["开始游戏", "设置", "退出"]

    def enter(self, **kwargs):
        super().enter(**kwargs)
        self.font = pygame.font.SysFont("pingfang", 48)
        print(f"进入 {self.name} 场景")

    def exit(self):
        super().exit()
        print(f"退出 {self.name} 场景")

    def update(self, delta_time: float):
        # 菜单逻辑更新
        self.render()
        pass

    def render(self):

        # 清空背景
        self.engine.render.fill((50, 50, 100))

        # 绘制标题
        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            screen.blit(text_surface, pos)

        self.engine.render.custom(
            draw_text, "三国演义", (300, 100), (255, 255, 255), self.font
        )

        # 绘制菜单选项
        for i, option in enumerate(self.options):
            color = (255, 255, 0) if i == self.selected_option else (255, 255, 255)
            y_pos = 200 + i * 60
            self.engine.render.custom(draw_text, option, (350, y_pos), color, self.font)

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_option = (self.selected_option - 1) % len(self.options)
                return True
            elif event.key == pygame.K_DOWN:
                self.selected_option = (self.selected_option + 1) % len(self.options)
                return True
            elif event.key == pygame.K_RETURN:
                self._handle_selection()
                return True
        return False

    def _handle_selection(self):
        scene_manager = self.engine.scene_manager

        if self.selected_option == 0:  # 开始游戏
            scene_manager.switch_to("game", level=1)
        elif self.selected_option == 1:  # 设置
            scene_manager.push_scene("settings")
        elif self.selected_option == 2:  # 退出
            pygame.event.post(pygame.event.Event(pygame.QUIT))


class GameScene(Scene):
    """游戏场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.level = 1
        self.score = 0

    def enter(self, level=1, **kwargs):
        super().enter(**kwargs)
        self.level = level
        self.score = 0
        print(f"进入游戏场景 - 等级 {self.level}")

    def update(self, delta_time: float):
        # 游戏逻辑更新
        self.score += int(delta_time * 10)
        self.render()

    def render(self):

        # 游戏背景
        self.engine.render.fill((0, 100, 0))

        # 绘制游戏信息
        font = pygame.font.SysFont("pingfang", 36)

        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            screen.blit(text_surface, pos)

        self.engine.render.custom(
            draw_text, f"等级: {self.level}", (10, 10), (255, 255, 255), font
        ).custom(
            draw_text, f"分数: {self.score}", (10, 50), (255, 255, 255), font
        ).custom(
            draw_text, "按ESC返回菜单", (10, 90), (255, 255, 255), font
        )

        # 绘制简单的游戏元素
        self.engine.render.rect((255, 0, 0), pygame.Rect(100, 100, 50, 50)).circle(
            (0, 0, 255), (300, 200), 30
        )

    def subscribe_events(self) -> bool:
        """订阅事件"""
        self.events.subscribe(pygame.KEYDOWN, self.handle_keydown)
        return True

    def handle_keydown(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.engine.scene_manager.switch_to("menu")
                return True
        return False


class SettingsScene(Scene):
    """设置场景"""

    def enter(self, **kwargs):
        super().enter(**kwargs)
        print("进入设置场景")

    def update(self, delta_time: float):
        self.render()

    def render(self):
        # self.engine.render = render_engine()

        # 设置界面背景
        self.engine.render.fill((100, 50, 100))

        font = pygame.font.SysFont("pingfang", 48)

        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            screen.blit(text_surface, pos)

        self.engine.render.custom(
            draw_text, "设置", (350, 100), (255, 255, 255), font
        ).custom(draw_text, "按ESC返回", (300, 300), (255, 255, 255), font)

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.engine.scene_manager.pop_scene()
                return True
        return False


class GameEngine:
    """简单的游戏引擎"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("场景管理示例")
        self.clock = pygame.time.Clock()

        # 初始化渲染引擎
        self.render = RenderEngine(self.screen)
        self.inputs = InputSystem()
        self.events = EventBus()
        # 初始化场景管理器
        self.scene_manager = SceneManager(self)
        self._setup_scenes()

    def _setup_scenes(self):
        """设置场景"""
        self.scene_manager.register_scene("menu", MenuScene)
        self.scene_manager.register_scene("game", GameScene)
        self.scene_manager.register_scene("settings", SettingsScene)

        # 启动主菜单
        self.scene_manager.switch_to("menu")

    def run(self):
        """运行游戏循环"""
        running = True
        last_time = pygame.time.get_ticks()

        while running:
            current_time = pygame.time.get_ticks()
            delta_time = (current_time - last_time) / 1000.0
            last_time = current_time

            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # 更新场景
            self.scene_manager.update(delta_time)

            # 渲染场景
            self.render.update()

            pygame.display.flip()
            self.clock.tick(60)

        # 清理资源
        self.scene_manager.shutdown()
        pygame.quit()


if __name__ == "__main__":
    print("启动场景管理示例...")
    print("功能演示：")
    print("- 场景切换和栈管理")
    print("- 事件处理")
    print("- 渲染集成")
    print("- 简化的API")
    print()
    print("控制说明：")
    print("- 方向键：菜单导航")
    print("- 回车：选择")
    print("- ESC：返回/退出")
    print()

    engine = GameEngine()
    engine.run()
