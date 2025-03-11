import pygame
import time


class GameEngine:
    """游戏引擎核心类，管理游戏主循环和基本组件"""

    def __init__(self, title="Pygame Game", width=800, height=600, fps=60):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.running = False
        self.scene_manager = None
        self.input_manager = None
        self.asset_manager = None
        self.event_manager = None
        self.map_manager = None  # 添加地图管理器
        self.debug_mode = False  # 添加调试模式标志
        self.show_fps = False  # 显示FPS计数器
        self.show_player_debug = False  # 添加玩家调试信息显示标志
        self.debug_font = pygame.font.SysFont("arial", 14)  # 调试文本的字体

    def initialize(
        self,
        scene_manager,
        input_manager,
        asset_manager,
        event_manager,
        map_manager=None,
    ):
        self.scene_manager = scene_manager
        self.input_manager = input_manager
        self.asset_manager = asset_manager
        self.event_manager = event_manager
        self.map_manager = map_manager  # 初始化地图管理器

    def toggle_debug_mode(self):
        """切换调试模式"""
        self.debug_mode = not self.debug_mode

    def toggle_fps_display(self):
        """切换FPS显示"""
        self.show_fps = not self.show_fps

    def toggle_player_debug(self):
        """切换玩家调试信息显示"""
        self.show_player_debug = not self.show_player_debug

    def start(self):
        """开始游戏主循环"""
        self.running = True

        # 游戏主循环
        while self.running:
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                # 添加切换调试模式的快捷键
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F1:
                        self.toggle_debug_mode()
                    elif event.key == pygame.K_F2:
                        self.toggle_fps_display()
                    elif event.key == pygame.K_F3:
                        self.toggle_player_debug()

                # 首先让UI管理器处理事件
                ui_handled = False
                if hasattr(self, "ui_manager"):
                    ui_handled = self.ui_manager.handle_event(event)

                # 如果UI没有处理事件，则传递给输入管理器
                if not ui_handled:
                    self.input_manager.process_event(event)

            # 更新输入状态
            self.input_manager.update()

            # 更新当前场景
            delta_time = self.clock.get_time() / 1000.0
            self.scene_manager.update(delta_time)

            # 更新UI
            if hasattr(self, "ui_manager"):
                self.ui_manager.update(delta_time)

            # 渲染
            self.screen.fill((0, 0, 0))
            self.scene_manager.render(self.screen)

            # 渲染UI
            if hasattr(self, "ui_manager"):
                self.ui_manager.render(self.screen)

            # 在调试模式下显示额外信息
            if self.debug_mode:
                self.render_debug_info()

            # 显示FPS
            if self.show_fps:
                fps_text = self.debug_font.render(
                    f"FPS: {int(self.clock.get_fps())}", True, (255, 255, 0)
                )
                self.screen.blit(fps_text, (10, 10))

            pygame.display.flip()

            # 控制帧率
            self.clock.tick(self.fps)

        pygame.quit()

    def render_debug_info(self):
        """渲染调试信息"""
        # 示例：显示内存中的实体数量
        if self.scene_manager and self.scene_manager.current_scene:
            entity_count = len(self.scene_manager.current_scene.entities)
            debug_text = self.debug_font.render(
                f"实体数: {entity_count}", True, (255, 255, 0)
            )
            self.screen.blit(debug_text, (10, 30))

            # 如果有相机信息
            if hasattr(self.scene_manager.current_scene, "camera_x"):
                camera_text = self.debug_font.render(
                    f"相机: ({int(self.scene_manager.current_scene.camera_x)}, {int(self.scene_manager.current_scene.camera_y)})",
                    True,
                    (255, 255, 0),
                )
                self.screen.blit(camera_text, (10, 50))

        # 如果启用了玩家调试信息，并且当前场景是游戏场景
        if self.show_player_debug and hasattr(
            self.scene_manager.current_scene, "player"
        ):
            player = self.scene_manager.current_scene.player
            if player:
                collision = player.get_component("collision")
                if collision:
                    # 绘制玩家碰撞盒
                    rect = pygame.Rect(
                        player.x - self.scene_manager.current_scene.camera_x,
                        player.y - self.scene_manager.current_scene.camera_y,
                        collision.width,
                        collision.height,
                    )
                    pygame.draw.rect(self.screen, (255, 0, 0), rect, 1)

                # 显示玩家位置信息
                pos_text = self.debug_font.render(
                    f"玩家位置: ({int(player.x)}, {int(player.y)})", True, (255, 255, 0)
                )
                self.screen.blit(pos_text, (10, 70))

        # 可以在这里添加更多的调试信息
