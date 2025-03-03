import pygame
from framework.ui.ui_element import UIElement
from rts.managers.game_state_manager import GameState, GameStateManager


class GameFlowUI:
    """管理游戏流程相关的UI元素"""

    def __init__(self, screen):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.game_state_manager = GameStateManager.get_instance()
        self.ui_elements = {
            GameState.MAIN_MENU: [],
            GameState.VICTORY: [],
            GameState.DEFEAT: [],
            GameState.PAUSED: [],
        }

        # 创建UI元素
        self.ui_elements[GameState.MAIN_MENU] = self._create_main_menu()
        self.ui_elements[GameState.VICTORY] = self._create_victory_screen()
        self.ui_elements[GameState.DEFEAT] = self._create_defeat_screen()
        self.ui_elements[GameState.PAUSED] = self._create_pause_menu()

        # 注册状态变更监听
        for state in [
            GameState.MAIN_MENU,
            GameState.VICTORY,
            GameState.DEFEAT,
            GameState.PAUSED,
        ]:
            self.game_state_manager.on_state_enter(state, self._on_state_enter)
            self.game_state_manager.on_state_exit(state, self._on_state_exit)

        self.active_elements = []

    def _on_state_enter(self, state, **kwargs):
        """状态进入时激活相应UI元素"""
        if state in self.ui_elements:
            self.active_elements = self.ui_elements[state]

    def _on_state_exit(self, state):
        """状态退出时清除UI元素"""
        if state in self.ui_elements:
            self.active_elements = []

    def _create_main_menu(self):
        """创建主菜单UI"""
        elements = []

        # 标题
        title = TextElement(
            self.width // 2,
            100,
            "战略指挥官",
            pygame.font.Font(None, 64),
            (255, 255, 255),
        )
        elements.append(title)

        # 新游戏按钮
        new_game_btn = ButtonElement(
            self.width // 2,
            250,
            200,
            50,
            "新游戏",
            lambda: self.game_state_manager.start_new_game(),
        )
        elements.append(new_game_btn)

        # 退出游戏按钮
        exit_btn = ButtonElement(
            self.width // 2,
            350,
            200,
            50,
            "退出游戏",
            lambda: pygame.event.post(pygame.event.Event(pygame.QUIT)),
        )
        elements.append(exit_btn)

        return elements

    def _create_victory_screen(self):
        """创建胜利屏幕UI"""
        elements = []

        # 胜利标题
        victory_title = TextElement(
            self.width // 2,
            150,
            "胜利！",
            pygame.font.Font(None, 72),
            (255, 215, 0),  # 金色
        )
        elements.append(victory_title)

        # 返回主菜单按钮
        menu_btn = ButtonElement(
            self.width // 2,
            350,
            200,
            50,
            "返回主菜单",
            lambda: self.game_state_manager.return_to_main_menu(),
        )
        elements.append(menu_btn)

        return elements

    def _create_defeat_screen(self):
        """创建失败屏幕UI"""
        elements = []

        # 失败标题
        defeat_title = TextElement(
            self.width // 2,
            150,
            "失败...",
            pygame.font.Font(None, 72),
            (180, 0, 0),  # 红色
        )
        elements.append(defeat_title)

        # 返回主菜单按钮
        menu_btn = ButtonElement(
            self.width // 2,
            350,
            200,
            50,
            "返回主菜单",
            lambda: self.game_state_manager.return_to_main_menu(),
        )
        elements.append(menu_btn)

        return elements

    def _create_pause_menu(self):
        """创建暂停菜单UI"""
        elements = []

        # 暂停标题
        pause_title = TextElement(
            self.width // 2,
            150,
            "游戏暂停",
            pygame.font.Font(None, 64),
            (255, 255, 255),
        )
        elements.append(pause_title)

        # 返回游戏按钮
        resume_btn = ButtonElement(
            self.width // 2,
            250,
            200,
            50,
            "返回游戏",
            lambda: self.game_state_manager.resume_game(),
        )
        elements.append(resume_btn)

        # 返回主菜单按钮
        menu_btn = ButtonElement(
            self.width // 2,
            350,
            200,
            50,
            "返回主菜单",
            lambda: self.game_state_manager.return_to_main_menu(),
        )
        elements.append(menu_btn)

        return elements

    def handle_event(self, event):
        """处理UI事件"""
        for element in self.active_elements:
            if hasattr(element, "handle_event"):
                element.handle_event(event)

    def update(self, dt):
        """更新UI元素"""
        for element in self.active_elements:
            if hasattr(element, "update"):
                element.update(dt)

    def render(self, surface=None):
        """渲染UI元素"""
        # Parameter added for compatibility with scene rendering system
        # but still using self.screen internally
        for element in self.active_elements:
            element.render(self.screen)


class TextElement(UIElement):
    """文本UI元素"""

    def __init__(self, x, y, text, font, color):
        super().__init__(x, y, 0, 0)
        self.text = text
        self.font = font
        self.color = color
        self._render_text()

    def _render_text(self):
        self.text_surface = self.font.render(self.text, True, self.color)
        self.rect = self.text_surface.get_rect(center=(self.x, self.y))

    def set_text(self, text):
        self.text = text
        self._render_text()

    def render(self, surface):
        surface.blit(self.text_surface, self.rect)


class ButtonElement(UIElement):
    """按钮UI元素"""

    def __init__(
        self,
        x,
        y,
        width,
        height,
        text,
        on_click,
        text_color=(255, 255, 255),
        bg_color=(50, 50, 50),
        hover_color=(80, 80, 80),
    ):
        super().__init__(x, y, width, height)
        self.text = text
        self.on_click = on_click
        self.text_color = text_color
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.current_color = bg_color
        self.font = pygame.font.Font(None, 32)
        self.rect = pygame.Rect(x - width // 2, y - height // 2, width, height)
        self.text_surface = self.font.render(text, True, text_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)
        self.is_hovering = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovering = self.rect.collidepoint(event.pos)
            self.current_color = self.hover_color if self.is_hovering else self.bg_color

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # 左键点击
            if self.is_hovering:
                self.on_click()

    def render(self, surface):
        # 绘制按钮背景
        pygame.draw.rect(surface, self.current_color, self.rect, border_radius=5)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=5)

        # 绘制按钮文本
        surface.blit(self.text_surface, self.text_rect)
