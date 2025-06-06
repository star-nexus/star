"""
围棋游戏系统 - 重构版
分离渲染系统，UI作为ECS组件
"""

import pygame
import random
import time
import math
from typing import Set, Type, List, Tuple, Optional

from framework_v2 import System, World
from framework_v2.engine.renders import render_engine
from framework_v2.engine.scenes import scene_manager
from framework_v2.engine.events import EventBus
from framework_v2.engine.engine_event import (
    KeyDownEvent,
    MouseButtonDownEvent,
    QuitEvent,
)

from .components import (
    Position,
    Stone,
    BoardPosition,
    Selectable,
    Clickable,
    Renderable,
    UIElement,
    UIPanel,
    UILabel,
    UIButton,
    BoardRenderer,
    StoneRenderer,
    GameBoard,
    GameState,
    GameStats,
    AIPlayer,
    UIState,
    MouseState,
    StoneColor,
    GameResultDialog,
    DialogOverlay,
)


class InputSystem(System):
    """输入处理系统"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        # 初始化鼠标状态
        if not world.get_singleton_component(MouseState):
            world.add_singleton_component(MouseState())

    def subscribe_events(self):
        """订阅输入事件"""
        EventBus().subscribe(KeyDownEvent, self.handle_event)
        EventBus().subscribe(MouseButtonDownEvent, self.handle_event)

    def handle_event(self, event) -> bool:
        """处理输入事件"""
        if isinstance(event, KeyDownEvent):
            if event.key == pygame.K_ESCAPE:
                EventBus().publish(
                    QuitEvent(
                        sender=type(self).__name__, timestamp=pygame.time.get_ticks()
                    )
                )
                return True

        elif isinstance(event, MouseButtonDownEvent):
            if event.button == 1:  # 左键点击
                mouse_state = self.world.get_singleton_component(MouseState)
                if mouse_state:
                    mouse_state.clicked = True
                    mouse_state.x, mouse_state.y = event.pos
                    self.handle_click(mouse_state.x, mouse_state.y)
                return True

    def update(self, delta_time: float):
        mouse_state = self.world.get_singleton_component(MouseState)
        ui_state = self.world.get_singleton_component(UIState)

        if not mouse_state or not ui_state:
            return

        # 获取鼠标位置
        mouse_x, mouse_y = pygame.mouse.get_pos()
        mouse_state.x = mouse_x
        mouse_state.y = mouse_y

        # 转换为棋盘坐标
        board_x, board_y = self._screen_to_board(mouse_x, mouse_y)
        mouse_state.board_x = board_x
        mouse_state.board_y = board_y

        # 更新悬停位置
        if 0 <= board_x < 19 and 0 <= board_y < 19:
            ui_state.hover_position = (board_x, board_y)
        else:
            ui_state.hover_position = None

    def _screen_to_board(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """屏幕坐标转棋盘坐标"""
        # 从棋盘渲染器获取参数
        board_entities = self.world.get_entities_with_component(BoardRenderer)
        if board_entities:
            entity = next(iter(board_entities))
            board_renderer = self.world.get_component(entity, BoardRenderer)
            if board_renderer:
                board_x = round(
                    (screen_x - board_renderer.start_x) / board_renderer.grid_size
                )
                board_y = round(
                    (screen_y - board_renderer.start_y) / board_renderer.grid_size
                )
                return board_x, board_y

        # 默认值
        board_start_x = 50
        board_start_y = 50
        grid_size = 30
        board_x = round((screen_x - board_start_x) / grid_size)
        board_y = round((screen_y - board_start_y) / grid_size)
        return board_x, board_y

    def handle_click(self, x: int, y: int):
        """处理点击事件"""
        mouse_state = self.world.get_singleton_component(MouseState)
        if mouse_state:
            mouse_state.clicked = True


class BoardRenderSystem(System):
    """棋盘渲染系统"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        # 创建棋盘渲染器实体
        if not world.get_entities_with_component(BoardRenderer):
            entity = world.create_entity()
            world.add_component(entity, BoardRenderer())
            world.add_component(entity, Renderable(layer=0))

    def update(self, delta_time: float):
        render = render_engine()
        if not render:
            return

        # 渲染棋盘背景
        render.fill((139, 69, 19))  # 棕色背景

        # 获取棋盘渲染器
        board_entities = self.world.get_entities_with_component(BoardRenderer)
        for entity_id in board_entities:
            board_renderer = self.world.get_component(entity_id, BoardRenderer)
            renderable = self.world.get_component(entity_id, Renderable)

            if board_renderer and renderable and renderable.visible:
                self._render_board_grid(board_renderer)

    def _render_board_grid(self, board_renderer: BoardRenderer):
        """渲染棋盘网格"""
        render = render_engine()

        board_size = 19

        # 绘制网格线
        for i in range(board_size):
            # 水平线
            start_x = board_renderer.start_x
            end_x = board_renderer.start_x + (board_size - 1) * board_renderer.grid_size
            y = board_renderer.start_y + i * board_renderer.grid_size
            render.line(board_renderer.line_color, (start_x, y), (end_x, y), 2)

            # 垂直线
            x = board_renderer.start_x + i * board_renderer.grid_size
            start_y = board_renderer.start_y
            end_y = board_renderer.start_y + (board_size - 1) * board_renderer.grid_size
            render.line(board_renderer.line_color, (x, start_y), (x, end_y), 2)

        # 绘制星位
        star_positions = [
            (3, 3),
            (3, 9),
            (3, 15),
            (9, 3),
            (9, 9),
            (9, 15),
            (15, 3),
            (15, 9),
            (15, 15),
        ]
        for star_x, star_y in star_positions:
            center_x = board_renderer.start_x + star_x * board_renderer.grid_size
            center_y = board_renderer.start_y + star_y * board_renderer.grid_size
            render.circle(board_renderer.line_color, (center_x, center_y), 4)


class StoneRenderSystem(System):
    """棋子渲染系统"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        # 创建棋子渲染器实体
        if not world.get_entities_with_component(StoneRenderer):
            entity = world.create_entity()
            world.add_component(entity, StoneRenderer())
            world.add_component(entity, Renderable(layer=1))

    def update(self, delta_time: float):
        render = render_engine()
        if not render:
            return

        # 获取棋子渲染器
        stone_renderer_entities = self.world.get_entities_with_component(StoneRenderer)
        stone_renderer = None
        for entity_id in stone_renderer_entities:
            stone_renderer = self.world.get_component(entity_id, StoneRenderer)
            break

        if not stone_renderer:
            return

        # 获取棋盘渲染器参数
        board_renderer = None
        board_entities = self.world.get_entities_with_component(BoardRenderer)
        for entity_id in board_entities:
            board_renderer = self.world.get_component(entity_id, BoardRenderer)
            break

        if not board_renderer:
            return

        # 渲染所有棋子
        stone_entities = self.world.get_entities_with_component(Stone)
        for entity_id in stone_entities:
            stone = self.world.get_component(entity_id, Stone)
            position = self.world.get_component(entity_id, Position)
            renderable = self.world.get_component(entity_id, Renderable)

            if stone and position and renderable and renderable.visible:
                self._render_stone(stone, position, stone_renderer, board_renderer)

    def _render_stone(
        self,
        stone: Stone,
        position: Position,
        stone_renderer: StoneRenderer,
        board_renderer: BoardRenderer,
    ):
        """渲染单个棋子"""
        render = render_engine()

        center_x = board_renderer.start_x + position.x * board_renderer.grid_size
        center_y = board_renderer.start_y + position.y * board_renderer.grid_size

        if stone.color == StoneColor.BLACK:
            color = stone_renderer.black_color
        else:
            color = stone_renderer.white_color

        # 绘制棋子
        render.circle(color, (center_x, center_y), stone_renderer.radius)
        render.circle(
            stone_renderer.border_color, (center_x, center_y), stone_renderer.radius, 2
        )


class UIRenderSystem(System):
    """UI渲染系统"""

    def __init__(self):
        super().__init__()
        self.font = None

    def initialize(self, world: World):
        super().initialize(world)
        pygame.font.init()
        self.font = pygame.font.SysFont("pingfang", 24)

        # 创建UI元素SceneManager
        self._create_ui_elements()

    def subscribe_events(self):
        pass

    def _create_ui_elements(self):
        """创建UI元素"""
        # 游戏状态面板
        status_panel = self.world.create_entity()
        self.world.add_component(
            status_panel, UIElement(position=(650, 50), size=(200, 400))
        )
        self.world.add_component(status_panel, UIPanel(background_color=(50, 50, 50)))
        self.world.add_component(status_panel, Renderable(layer=10))

        # 当前玩家标签
        current_player_label = self.world.create_entity()
        self.world.add_component(
            current_player_label, UIElement(position=(660, 70), size=(180, 30))
        )
        self.world.add_component(
            current_player_label, UILabel(text="当前玩家: 黑棋", font_size=20)
        )
        self.world.add_component(current_player_label, Renderable(layer=11))

        # 回合数标签
        turn_label = self.world.create_entity()
        self.world.add_component(
            turn_label, UIElement(position=(660, 100), size=(180, 30))
        )
        self.world.add_component(turn_label, UILabel(text="回合数: 0", font_size=16))
        self.world.add_component(turn_label, Renderable(layer=11))

        # 吃子数标签
        captures_label = self.world.create_entity()
        self.world.add_component(
            captures_label, UIElement(position=(660, 130), size=(180, 30))
        )
        self.world.add_component(
            captures_label, UILabel(text="黑棋吃子: 0", font_size=16)
        )
        self.world.add_component(captures_label, Renderable(layer=11))

        captures_label2 = self.world.create_entity()
        self.world.add_component(
            captures_label2, UIElement(position=(660, 160), size=(180, 30))
        )
        self.world.add_component(
            captures_label2, UILabel(text="白棋吃子: 0", font_size=16)
        )
        self.world.add_component(captures_label2, Renderable(layer=11))

        # 目数标签
        territory_label = self.world.create_entity()
        self.world.add_component(
            territory_label, UIElement(position=(660, 190), size=(180, 30))
        )
        self.world.add_component(
            territory_label, UILabel(text="黑棋目数: 0", font_size=16)
        )
        self.world.add_component(territory_label, Renderable(layer=11))

        territory_label2 = self.world.create_entity()
        self.world.add_component(
            territory_label2, UIElement(position=(660, 220), size=(180, 30))
        )
        self.world.add_component(
            territory_label2, UILabel(text="白棋目数: 0", font_size=16)
        )
        self.world.add_component(territory_label2, Renderable(layer=11))

        # 得分标签
        score_label = self.world.create_entity()
        self.world.add_component(
            score_label, UIElement(position=(660, 250), size=(180, 30))
        )
        self.world.add_component(
            score_label, UILabel(text="黑棋得分: 0.0", font_size=16)
        )
        self.world.add_component(score_label, Renderable(layer=11))

        score_label2 = self.world.create_entity()
        self.world.add_component(
            score_label2, UIElement(position=(660, 280), size=(180, 30))
        )
        self.world.add_component(
            score_label2, UILabel(text="白棋得分: 6.5", font_size=16)
        )
        self.world.add_component(score_label2, Renderable(layer=11))

        # 胜率标签
        winrate_label = self.world.create_entity()
        self.world.add_component(
            winrate_label, UIElement(position=(660, 310), size=(180, 30))
        )
        self.world.add_component(
            winrate_label,
            UILabel(text="黑棋胜率: 50.0%", font_size=16, text_color=(255, 255, 0)),
        )
        self.world.add_component(winrate_label, Renderable(layer=11))

        winrate_label2 = self.world.create_entity()
        self.world.add_component(
            winrate_label2, UIElement(position=(660, 340), size=(180, 30))
        )
        self.world.add_component(
            winrate_label2,
            UILabel(text="白棋胜率: 50.0%", font_size=16, text_color=(255, 255, 0)),
        )
        self.world.add_component(winrate_label2, Renderable(layer=11))

        # 判定胜负按钮
        judge_button = self.world.create_entity()
        self.world.add_component(
            judge_button, UIElement(position=(660, 380), size=(120, 35))
        )
        self.world.add_component(
            judge_button,
            UIButton(text="判定胜负", font_size=16, on_click=self._judge_game),
        )
        self.world.add_component(judge_button, Clickable())
        self.world.add_component(judge_button, Renderable(layer=11))

        # Pass按钮
        pass_button = self.world.create_entity()
        self.world.add_component(
            pass_button, UIElement(position=(660, 420), size=(120, 35))
        )
        self.world.add_component(
            pass_button,
            UIButton(text="跳过回合", font_size=16, on_click=self._pass_turn),
        )
        self.world.add_component(pass_button, Clickable())
        self.world.add_component(pass_button, Renderable(layer=11))

    def _judge_game(self):
        """主动判定游戏胜负"""
        game_logic_system = None
        for system in self.world.systems:
            if isinstance(system, GameLogicSystem):
                game_logic_system = system
                break

        if game_logic_system:
            game_logic_system.force_judge_game()

    def _pass_turn(self):
        """跳过回合"""
        game_logic_system = None
        for system in self.world.systems:
            if isinstance(system, GameLogicSystem):
                game_logic_system = system
                break

        if game_logic_system:
            game_logic_system.pass_turn()

    def update(self, delta_time: float):
        render = render_engine()
        if not render:
            return

        # 更新UI文本内容
        self._update_ui_content()

        # 渲染UI面板
        self._render_panels()

        # 渲染UI标签
        self._render_labels()

        # 渲染UI按钮
        self._render_buttons()

        # 渲染结果对话框
        self._render_result_dialog()

        # 渲染悬停效果
        # self._render_hover()

    def _update_ui_content(self):
        """更新UI内容"""
        game_state = self.world.get_singleton_component(GameState)
        stats = self.world.get_singleton_component(GameStats)

        if not game_state or not stats:
            return

        # 更新标签文本
        label_entities = self.world.get_entities_with_component(UILabel)
        label_count = 0

        for entity_id in label_entities:
            label = self.world.get_component(entity_id, UILabel)
            if label:
                if label_count == 0:  # 当前玩家
                    player_text = (
                        "黑棋"
                        if game_state.current_player == StoneColor.BLACK
                        else "白棋"
                    )
                    label.text = f"当前玩家: {player_text}"
                elif label_count == 1:  # 回合数
                    label.text = f"回合数: {game_state.move_count}"
                elif label_count == 2:  # 黑棋吃子
                    label.text = f"黑棋吃子: {stats.black_captures}"
                elif label_count == 3:  # 白棋吃子
                    label.text = f"白棋吃子: {stats.white_captures}"
                elif label_count == 4:  # 黑棋目数
                    label.text = f"黑棋目数: {stats.black_territory}"
                elif label_count == 5:  # 白棋目数
                    label.text = f"白棋目数: {stats.white_territory}"
                elif label_count == 6:  # 黑棋得分
                    label.text = f"黑棋得分: {stats.black_score:.1f}"
                elif label_count == 7:  # 白棋得分
                    label.text = f"白棋得分: {stats.white_score:.1f}"
                elif label_count == 8:  # 黑棋胜率
                    label.text = f"黑棋胜率: {stats.black_win_rate*100:.1f}%"
                elif label_count == 9:  # 白棋胜率
                    label.text = f"白棋胜率: {stats.white_win_rate*100:.1f}%"
                label_count += 1

    def _render_panels(self):
        """渲染UI面板"""
        render = render_engine()

        panel_entities = self.world.get_entities_with_component(UIPanel)
        for entity_id in panel_entities:
            panel = self.world.get_component(entity_id, UIPanel)
            element = self.world.get_component(entity_id, UIElement)
            renderable = self.world.get_component(entity_id, Renderable)

            if panel and element and renderable and renderable.visible:
                rect = pygame.Rect(
                    element.position[0],
                    element.position[1],
                    element.size[0],
                    element.size[1],
                )
                render.rect(panel.background_color, rect)

                if panel.border_color:
                    render.rect(panel.border_color, rect, panel.border_width)

    def _render_labels(self):
        """渲染UI标签"""
        render = render_engine()
        if not render:
            return

        label_entities = self.world.get_entities_with_component(UILabel)
        for entity_id in label_entities:
            label = self.world.get_component(entity_id, UILabel)
            element = self.world.get_component(entity_id, UIElement)
            renderable = self.world.get_component(entity_id, Renderable)

            if label and element and renderable and renderable.visible:
                # 创建字体并渲染文本
                font = pygame.font.SysFont("pingfang", label.font_size)
                text_surface = font.render(label.text, True, label.text_color)

                # 如果有背景色，先绘制背景
                if label.background_color:
                    bg_rect = pygame.Rect(
                        element.position[0],
                        element.position[1],
                        element.size[0],
                        element.size[1],
                    )
                    render.rect(label.background_color, bg_rect)

                # 绘制文本
                render.draw(text_surface, element.position, layer=renderable.layer)

    # def _render_hover(self):
    #     """渲染悬停效果"""
    #     render = render_engine()
    #     ui_state = self.world.get_singleton_component(UIState)

    #     if not ui_state or not ui_state.hover_position:
    #         return

    #     # 获取棋盘渲染器参数
    #     board_renderer = None
    #     board_entities = self.world.get_entities_with_component(BoardRenderer)
    #     for entity_id in board_entities:
    #         board_renderer = self.world.get_component(entity_id, BoardRenderer)
    #         break

    #     if not board_renderer:
    #         return

    #     hover_x, hover_y = ui_state.hover_position
    #     center_x = board_renderer.start_x + hover_x * board_renderer.grid_size
    #     center_y = board_renderer.start_y + hover_y * board_renderer.grid_size

    #     # 绘制悬停圆圈
    #     render.circle((100, 100, 100), (center_x, center_y), 8, 2)

    def _render_buttons(self):
        """渲染UI按钮"""
        render = render_engine()
        if not render:
            return

        mouse_state = self.world.get_singleton_component(MouseState)
        button_entities = self.world.get_entities_with_component(UIButton)

        for entity_id in button_entities:
            button = self.world.get_component(entity_id, UIButton)
            element = self.world.get_component(entity_id, UIElement)
            renderable = self.world.get_component(entity_id, Renderable)

            if button and element and renderable and renderable.visible:
                # 检查鼠标悬停
                button.is_hovered = False
                if mouse_state:
                    mx, my = mouse_state.x, mouse_state.y
                    ex, ey = element.position
                    ew, eh = element.size

                    if ex <= mx <= ex + ew and ey <= my <= ey + eh:
                        button.is_hovered = True

                # 选择按钮颜色
                if button.is_pressed:
                    bg_color = button.pressed_color
                elif button.is_hovered:
                    bg_color = button.hover_color
                else:
                    bg_color = button.background_color

                # 绘制按钮背景
                rect = pygame.Rect(
                    element.position[0],
                    element.position[1],
                    element.size[0],
                    element.size[1],
                )
                render.rect(bg_color, rect)

                # 绘制边框
                if button.border_color:
                    render.rect(button.border_color, rect, button.border_width)

                # 绘制按钮文本
                font = pygame.font.SysFont("pingfang", button.font_size)
                text_surface = font.render(button.text, True, button.text_color)

                # 居中文本
                text_rect = text_surface.get_rect()
                text_x = element.position[0] + (element.size[0] - text_rect.width) // 2
                text_y = element.position[1] + (element.size[1] - text_rect.height) // 2

                render.draw(text_surface, (text_x, text_y), layer=renderable.layer)

                # 重置按压状态
                button.is_pressed = False

    def _render_result_dialog(self):
        """渲染游戏结果对话框"""
        result_dialog = self.world.get_singleton_component(GameResultDialog)
        if not result_dialog or not result_dialog.visible:
            return

        render = render_engine()
        if not render:
            return

        # 获取屏幕尺寸
        screen = pygame.display.get_surface()
        screen_width, screen_height = screen.get_size()

        # 绘制半透明遮罩
        overlay_surface = pygame.Surface((screen_width, screen_height))
        overlay_surface.set_alpha(150)
        overlay_surface.fill((0, 0, 0))
        render.draw(overlay_surface, (0, 0), layer=20)

        # 对话框尺寸和位置
        dialog_width, dialog_height = 400, 350
        dialog_x = (screen_width - dialog_width) // 2
        dialog_y = (screen_height - dialog_height) // 2

        # 绘制对话框背景
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
        render.rect((50, 50, 50), dialog_rect)
        render.rect((200, 200, 200), dialog_rect, 3)

        # 绘制标题
        font_title = pygame.font.SysFont("pingfang", 28)
        title_text = "游戏结束"
        title_surface = font_title.render(title_text, True, (255, 255, 255))
        title_x = dialog_x + (dialog_width - title_surface.get_width()) // 2
        render.draw(title_surface, (title_x, dialog_y + 20), layer=21)

        # 绘制获胜者信息
        font_content = pygame.font.SysFont("pingfang", 20)
        y_offset = dialog_y + 70

        if result_dialog.winner == StoneColor.BLACK:
            winner_text = "黑棋获胜！"
            winner_color = (255, 255, 255)
        elif result_dialog.winner == StoneColor.WHITE:
            winner_text = "白棋获胜！"
            winner_color = (255, 255, 255)
        else:
            winner_text = "平局"
            winner_color = (255, 255, 0)

        winner_surface = font_content.render(winner_text, True, winner_color)
        winner_x = dialog_x + (dialog_width - winner_surface.get_width()) // 2
        render.draw(winner_surface, (winner_x, y_offset), layer=21)

        # 绘制比分信息
        y_offset += 40
        score_lines = [
            f"黑棋得分: {result_dialog.black_score:.1f}",
            f"白棋得分: {result_dialog.white_score:.1f}",
            f"分差: {abs(result_dialog.score_difference):.1f}",
            f"总回合数: {result_dialog.total_moves}",
            f"游戏时长: {result_dialog.game_duration:.0f}秒",
        ]

        font_small = pygame.font.SysFont("pingfang", 16)
        for line in score_lines:
            line_surface = font_small.render(line, True, (200, 200, 200))
            line_x = dialog_x + (dialog_width - line_surface.get_width()) // 2
            render.draw(line_surface, (line_x, y_offset), layer=21)
            y_offset += 25

        # 绘制按钮
        button_width, button_height = 120, 35
        button_y = dialog_y + dialog_height - 60

        # 返回主菜单按钮
        menu_button_x = dialog_x + 50
        menu_button_rect = pygame.Rect(
            menu_button_x, button_y, button_width, button_height
        )
        render.rect((70, 70, 70), menu_button_rect)
        render.rect((200, 200, 200), menu_button_rect, 2)

        menu_text = font_content.render("返回主菜单", True, (255, 255, 255))
        menu_text_x = menu_button_x + (button_width - menu_text.get_width()) // 2
        menu_text_y = button_y + (button_height - menu_text.get_height()) // 2
        render.draw(menu_text, (menu_text_x, menu_text_y), layer=21)

        # 继续复盘按钮
        review_button_x = dialog_x + dialog_width - 50 - button_width
        review_button_rect = pygame.Rect(
            review_button_x, button_y, button_width, button_height
        )
        render.rect((70, 70, 70), review_button_rect)
        render.rect((200, 200, 200), review_button_rect, 2)

        review_text = font_content.render("继续复盘", True, (255, 255, 255))
        review_text_x = review_button_x + (button_width - review_text.get_width()) // 2
        review_text_y = button_y + (button_height - review_text.get_height()) // 2
        render.draw(review_text, (review_text_x, review_text_y), layer=21)


class UIButtonSystem(System):
    """UI按钮交互系统"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)

    def subscribe_events(self):
        """订阅鼠标点击事件"""
        EventBus().subscribe(MouseButtonDownEvent, self.handle_mouse_click)

    def handle_mouse_click(self, event):
        """处理鼠标点击事件"""
        if event.button != 1:  # 只处理左键点击
            return

        mouse_state = self.world.get_singleton_component(MouseState)
        if not mouse_state:
            return

        # 检查是否点击了按钮
        self._check_button_clicks(event.pos[0], event.pos[1])

        # 检查是否点击了对话框按钮
        self._check_dialog_button_clicks(event.pos[0], event.pos[1])

    def _check_button_clicks(self, mx: int, my: int):
        """检查按钮点击"""
        button_entities = self.world.get_entities_with_component(UIButton)

        for entity_id in button_entities:
            button = self.world.get_component(entity_id, UIButton)
            element = self.world.get_component(entity_id, UIElement)
            clickable = self.world.get_component(entity_id, Clickable)

            if button and element and clickable and clickable.enabled:
                ex, ey = element.position
                ew, eh = element.size

                # 检查点击是否在按钮范围内
                if ex <= mx <= ex + ew and ey <= my <= ey + eh:
                    button.is_pressed = True
                    if button.on_click:
                        print(f"Button '{button.text}' clicked at ({mx}, {my})")
                        button.on_click()

    def _check_dialog_button_clicks(self, mx: int, my: int):
        """检查对话框按钮点击"""
        result_dialog = self.world.get_singleton_component(GameResultDialog)
        if not result_dialog or not result_dialog.visible:
            return

        # 获取屏幕尺寸计算对话框位置
        screen = pygame.display.get_surface()
        screen_width, screen_height = screen.get_size()

        dialog_width, dialog_height = 400, 350
        dialog_x = (screen_width - dialog_width) // 2
        dialog_y = (screen_height - dialog_height) // 2

        # 按钮尺寸和位置
        button_width, button_height = 120, 35
        button_y = dialog_y + dialog_height - 60

        # 返回主菜单按钮
        menu_button_x = dialog_x + 50
        if (
            menu_button_x <= mx <= menu_button_x + button_width
            and button_y <= my <= button_y + button_height
        ):
            self._return_to_menu()
            return

        # 继续复盘按钮
        review_button_x = dialog_x + dialog_width - 50 - button_width
        if (
            review_button_x <= mx <= review_button_x + button_width
            and button_y <= my <= button_y + button_height
        ):
            self._continue_review()

    def _return_to_menu(self):
        """返回主菜单"""
        from framework_v2.engine.scenes import scene_manager

        scene_manager().switch_to("menu")

    def _continue_review(self):
        """继续复盘 - 关闭对话框"""
        result_dialog = self.world.get_singleton_component(GameResultDialog)
        if result_dialog:
            result_dialog.visible = False

    def update(self, delta_time: float):
        """更新按钮状态"""
        # 重置所有按钮的按压状态
        button_entities = self.world.get_entities_with_component(UIButton)
        for entity_id in button_entities:
            button = self.world.get_component(entity_id, UIButton)
            if button and button.is_pressed:
                # 按压状态持续一帧后重置
                button.is_pressed = False


# 继续使用原有的其他系统，但简化RenderSystem
class BoardSystem(System):
    """棋盘系统 - 处理棋盘逻辑"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        # 初始化棋盘
        if not world.get_singleton_component(GameBoard):
            world.add_singleton_component(GameBoard())

    def place_stone(self, x: int, y: int, color: StoneColor) -> bool:
        """放置棋子"""
        board = self.world.get_singleton_component(GameBoard)
        game_state = self.world.get_singleton_component(GameState)

        if not board or not game_state:
            return False

        # 检查位置是否有效
        if not (0 <= x < board.size and 0 <= y < board.size):
            return False

        # 检查位置是否为空
        if board.board[y][x] != StoneColor.EMPTY:
            return False

        # 检查是否是合法移动（非自杀移动）
        if not self._is_legal_move(x, y, color):
            return False

        # 临时放置棋子以检查吃子
        board.board[y][x] = color

        # 检查并移除被吃掉的棋子
        captured = self._check_captures(x, y, color)

        # 检查自己的棋群是否有气（自杀检查）
        own_group = self._get_group(x, y)
        if not captured and not self._has_liberty(own_group):
            # 自杀移动，撤销放置
            board.board[y][x] = StoneColor.EMPTY
            return False

        # 创建棋子实体
        entity = self.world.create_entity()
        self.world.add_component(entity, Position(x, y))
        self.world.add_component(entity, Stone(color))
        self.world.add_component(entity, Renderable())

        # 更新统计
        stats = self.world.get_singleton_component(GameStats)
        if stats and captured:
            if color == StoneColor.BLACK:
                stats.white_captures += len(captured)
            else:
                stats.black_captures += len(captured)

        # 记录移动
        if stats:
            stats.moves_history.append((x, y, color))

        # 更新游戏状态
        game_state.move_count += 1
        game_state.last_move_time = time.time()
        game_state.pass_count = 0  # 重置pass计数

        return True

    def _is_legal_move(self, x: int, y: int, color: StoneColor) -> bool:
        """检查是否是合法移动"""
        board = self.world.get_singleton_component(GameBoard)

        # 创建临时棋盘状态
        temp_board = [row[:] for row in board.board]
        temp_board[y][x] = color

        # 检查是否能吃掉对手棋子
        opponent_color = (
            StoneColor.WHITE if color == StoneColor.BLACK else StoneColor.BLACK
        )
        can_capture = False

        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (
                0 <= nx < board.size
                and 0 <= ny < board.size
                and temp_board[ny][nx] == opponent_color
            ):
                # 检查对手棋群是否没有气
                opponent_group = self._get_group_from_temp_board(temp_board, nx, ny)
                if not self._has_liberty_in_temp_board(temp_board, opponent_group):
                    can_capture = True
                    break

        # 如果能吃掉对手棋子，则是合法移动
        if can_capture:
            return True

        # 检查自己的棋群是否有气
        own_group = self._get_group_from_temp_board(temp_board, x, y)
        return self._has_liberty_in_temp_board(temp_board, own_group)

    def _get_group_from_temp_board(
        self, temp_board: List[List[StoneColor]], x: int, y: int
    ) -> List[Tuple[int, int]]:
        """从临时棋盘获取棋群"""
        color = temp_board[y][x]
        if color == StoneColor.EMPTY:
            return []

        visited = set()
        group = []
        stack = [(x, y)]
        size = len(temp_board)

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue

            visited.add((cx, cy))
            group.append((cx, cy))

            # 检查四个方向
            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < size
                    and 0 <= ny < size
                    and (nx, ny) not in visited
                    and temp_board[ny][nx] == color
                ):
                    stack.append((nx, ny))

        return group

    def _has_liberty_in_temp_board(
        self, temp_board: List[List[StoneColor]], group: List[Tuple[int, int]]
    ) -> bool:
        """检查棋群在临时棋盘中是否有气"""
        size = len(temp_board)
        for x, y in group:
            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if (
                    0 <= nx < size
                    and 0 <= ny < size
                    and temp_board[ny][nx] == StoneColor.EMPTY
                ):
                    return True
        return False

    def _check_captures(
        self, x: int, y: int, color: StoneColor
    ) -> List[Tuple[int, int]]:
        """检查并移除被吃掉的棋子"""
        board = self.world.get_singleton_component(GameBoard)
        captured = []
        opponent_color = (
            StoneColor.WHITE if color == StoneColor.BLACK else StoneColor.BLACK
        )

        # 检查四个方向的对手棋群
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (
                0 <= nx < board.size
                and 0 <= ny < board.size
                and board.board[ny][nx] == opponent_color
            ):
                group = self._get_group(nx, ny)
                if not self._has_liberty(group):
                    captured.extend(group)
                    self._remove_stones(group)

        return captured

    def _get_group(self, x: int, y: int) -> List[Tuple[int, int]]:
        """获取棋子所在的棋群"""
        board = self.world.get_singleton_component(GameBoard)
        color = board.board[y][x]
        if color == StoneColor.EMPTY:
            return []

        visited = set()
        group = []
        stack = [(x, y)]

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue

            visited.add((cx, cy))
            group.append((cx, cy))

            # 检查四个方向
            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < board.size
                    and 0 <= ny < board.size
                    and (nx, ny) not in visited
                    and board.board[ny][nx] == color
                ):
                    stack.append((nx, ny))

        return group

    def _has_liberty(self, group: List[Tuple[int, int]]) -> bool:
        """检查棋群是否有气"""
        board = self.world.get_singleton_component(GameBoard)

        for x, y in group:
            directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if (
                    0 <= nx < board.size
                    and 0 <= ny < board.size
                    and board.board[ny][nx] == StoneColor.EMPTY
                ):
                    return True
        return False

    def _remove_stones(self, positions: List[Tuple[int, int]]):
        """移除棋子"""
        board = self.world.get_singleton_component(GameBoard)

        for x, y in positions:
            board.board[y][x] = StoneColor.EMPTY

            # 找到并移除对应的实体
            for entity_id in list(self.world.get_entities_with_component(Position)):
                pos = self.world.get_component(entity_id, Position)
                if pos and pos.x == x and pos.y == y:
                    self.world.destroy_entity(entity_id)
                    break


class GameLogicSystem(System):
    """游戏逻辑系统"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        # 初始化游戏状态
        if not world.get_singleton_component(GameState):
            world.add_singleton_component(GameState())
        if not world.get_singleton_component(GameStats):
            world.add_singleton_component(GameStats())

    def update(self, delta_time: float):
        game_state = self.world.get_singleton_component(GameState)
        mouse_state = self.world.get_singleton_component(MouseState)
        board_system = None

        # 找到棋盘系统
        for system in self.world.systems:
            if isinstance(system, BoardSystem):
                board_system = system
                break

        if not game_state or not mouse_state or not board_system:
            return

        # 处理鼠标点击
        if mouse_state.clicked and game_state.game_phase == "playing":
            mouse_state.clicked = False

            if 0 <= mouse_state.board_x < 19 and 0 <= mouse_state.board_y < 19:
                # 检查是否轮到人类玩家（黑棋）
                ai_player = self.world.get_singleton_component(AIPlayer)
                if ai_player and ai_player.enabled:
                    # AI模式下，只有轮到黑棋（人类）时才能操作
                    if game_state.current_player == StoneColor.BLACK:
                        if board_system.place_stone(
                            mouse_state.board_x,
                            mouse_state.board_y,
                            game_state.current_player,
                        ):
                            # 切换玩家
                            self._switch_player()
                else:
                    # 非AI模式，任何玩家都可以操作
                    if board_system.place_stone(
                        mouse_state.board_x,
                        mouse_state.board_y,
                        game_state.current_player,
                    ):
                        # 切换玩家
                        self._switch_player()

        # 检查游戏结束条件
        self._check_game_end()

    def _switch_player(self):
        """切换当前玩家"""
        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            game_state.current_player = (
                StoneColor.WHITE
                if game_state.current_player == StoneColor.BLACK
                else StoneColor.BLACK
            )

    def _check_game_end(self):
        """检查游戏是否结束"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return

        # 如果连续两次pass，游戏结束
        if game_state.pass_count >= 2:
            game_state.game_phase = "ended"
            self._calculate_winner()

    def _calculate_winner(self):
        """计算获胜者"""
        stats = self.world.get_singleton_component(GameStats)
        game_state = self.world.get_singleton_component(GameState)

        if not stats or not game_state:
            return

        # 计算最终得分
        self._calculate_final_scores()

        # 基于得分判定胜负
        if stats.black_score > stats.white_score:
            game_state.winner = StoneColor.BLACK
        elif stats.white_score > stats.black_score:
            game_state.winner = StoneColor.WHITE
        else:
            game_state.winner = None  # 平局

        # 显示结果对话框
        self._show_result_dialog()

    def _calculate_final_scores(self):
        """计算最终得分"""
        # 获取目数计算系统
        for system in self.world.systems:
            if isinstance(system, TerritorySystem):
                system.calculate_territory()
                system.calculate_scores()
                break

    def pass_turn(self):
        """跳过回合"""
        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            game_state.pass_count += 1
            self._switch_player()

    def force_judge_game(self):
        """强制判定游戏胜负"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or game_state.game_phase == "ended":
            return

        game_state.game_phase = "ended"
        self._calculate_winner()
        self._show_result_dialog()

    def _show_result_dialog(self):
        """显示结果对话框"""
        game_state = self.world.get_singleton_component(GameState)
        stats = self.world.get_singleton_component(GameStats)

        if not game_state or not stats:
            return

        # 确保结果对话框组件存在
        result_dialog = self.world.get_singleton_component(GameResultDialog)
        if not result_dialog:
            result_dialog = GameResultDialog()
            self.world.add_singleton_component(result_dialog)

        # 填充对话框数据
        result_dialog.visible = True
        result_dialog.winner = game_state.winner
        result_dialog.black_score = stats.black_score
        result_dialog.white_score = stats.white_score
        result_dialog.score_difference = stats.black_score - stats.white_score
        result_dialog.total_moves = game_state.move_count
        result_dialog.game_duration = time.time() - game_state.game_start_time


class AISystem(System):
    """AI系统"""

    def __init__(self):
        super().__init__()
        self.ai_player_instance = None

    def initialize(self, world: World):
        super().initialize(world)
        if not world.get_singleton_component(AIPlayer):
            world.add_singleton_component(AIPlayer())

        # 初始化AI实例
        from .ai import GoAI

        self.ai_player_instance = GoAI(StoneColor.WHITE, "medium")

    def update(self, delta_time: float):
        ai_player = self.world.get_singleton_component(AIPlayer)
        game_state = self.world.get_singleton_component(GameState)

        if (
            not ai_player
            or not ai_player.enabled
            or not game_state
            or game_state.current_player != StoneColor.WHITE
            or game_state.game_phase != "playing"
        ):
            return

        # AI思考时间控制
        current_time = time.time()
        if ai_player.is_thinking:
            if current_time - ai_player.last_move_time >= ai_player.thinking_time:
                self._make_ai_move()
                ai_player.is_thinking = False
        else:
            # 开始AI思考
            ai_player.is_thinking = True
            ai_player.last_move_time = current_time

    def _make_ai_move(self):
        """AI下棋"""
        board = self.world.get_singleton_component(GameBoard)
        board_system = None

        # 找到棋盘系统
        for system in self.world.systems:
            if isinstance(system, BoardSystem):
                board_system = system
                break

        if not board or not board_system or not self.ai_player_instance:
            return

        # 使用高级AI获取移动
        move = self.ai_player_instance.get_move(board)
        if move:
            x, y = move
            if board_system.place_stone(x, y, StoneColor.WHITE):
                # AI成功下棋后，切换到下一个玩家
                game_logic_system = None
                for system in self.world.systems:
                    if isinstance(system, GameLogicSystem):
                        game_logic_system = system
                        break
                if game_logic_system:
                    game_logic_system._switch_player()
        else:
            # 没有可行移动，pass
            game_logic_system = None
            for system in self.world.systems:
                if isinstance(system, GameLogicSystem):
                    game_logic_system = system
                    break
            if game_logic_system:
                game_logic_system.pass_turn()


class UISystem(System):
    """UI系统 - 处理UI交互逻辑"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)
        if not world.get_singleton_component(UIState):
            world.add_singleton_component(UIState())

    def update(self, delta_time: float):
        # UI交互逻辑处理
        pass


class MenuRenderSystem(System):
    """菜单渲染系统"""

    def __init__(self):
        super().__init__()
        self.selected_option = 0
        self.options = ["开始游戏", "设置", "退出"]
        self.title_font = None
        self.menu_font = None
        self.instruction_font = None

    def initialize(self, world: World):
        super().initialize(world)
        pygame.font.init()
        self.title_font = pygame.font.SysFont("pingfang", 72)
        self.menu_font = pygame.font.SysFont("pingfang", 48)
        self.instruction_font = pygame.font.SysFont("pingfang", 24)

    def subscribe_events(self) -> bool:
        """处理订阅事件"""
        EventBus().subscribe(KeyDownEvent, self.handle_event)
        return True

    def handle_event(self, event) -> bool:
        """处理键盘事件"""
        if event.key == pygame.K_UP:
            self.selected_option = (self.selected_option - 1) % len(self.options)
            return True
        elif event.key == pygame.K_DOWN:
            self.selected_option = (self.selected_option + 1) % len(self.options)
            return True
        elif event.key == pygame.K_RETURN:
            if self.selected_option == 0:  # 开始游戏
                scene_manager().switch_to("game")
            elif self.selected_option == 1:  # 设置
                # TODO: 实现设置界面
                pass
            elif self.selected_option == 2:  # 退出
                EventBus().publish(
                    QuitEvent(
                        sender=type(self).__name__,
                        timestamp=pygame.time.get_ticks(),
                    )
                )
            return True

        return False

    def update(self, delta_time: float):
        from framework_v2.engine.renders import render_engine

        render = render_engine()
        if not render:
            return

        # 背景
        render.fill((139, 69, 19))

        # 标题
        def draw_text(screen, text, pos, color, font):
            text_surface = font.render(text, True, color)
            text_rect = text_surface.get_rect(center=pos)
            screen.blit(text_surface, text_rect)

        render.custom(
            draw_text, "围棋游戏", (400, 150), (255, 255, 255), self.title_font
        )

        # 菜单选项
        for i, option in enumerate(self.options):
            color = (255, 255, 0) if i == self.selected_option else (200, 200, 200)
            y_pos = 250 + i * 60
            render.custom(draw_text, option, (400, y_pos), color, self.menu_font)

        # 说明文字
        instructions = [
            "操作说明:",
            "鼠标点击放置棋子",
            "P键 - 跳过回合",
            "R键 - 重新开始",
            "ESC键 - 返回菜单",
        ]

        for i, instruction in enumerate(instructions):
            render.custom(
                draw_text,
                instruction,
                (400, 450 + i * 25),
                (180, 180, 180),
                self.instruction_font,
            )


class TerritorySystem(System):
    """目数计算系统 - 计算势力范围和实时胜率"""

    def __init__(self):
        super().__init__()

    def initialize(self, world: World):
        super().initialize(world)

    def update(self, delta_time: float):
        """定期更新目数和胜率"""
        # 每秒更新一次
        if hasattr(self, "last_update"):
            if time.time() - self.last_update < 1.0:
                return

        self.last_update = time.time()

        self.calculate_territory()
        self.calculate_scores()
        self.calculate_win_rates()

    def calculate_territory(self):
        """计算势力范围"""
        board = self.world.get_singleton_component(GameBoard)
        stats = self.world.get_singleton_component(GameStats)

        if not board or not stats:
            return

        # 重置统计
        stats.black_territory = 0
        stats.white_territory = 0
        stats.black_stones = 0
        stats.white_stones = 0

        # 计算棋子数量
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.BLACK:
                    stats.black_stones += 1
                elif board.board[y][x] == StoneColor.WHITE:
                    stats.white_stones += 1

        # 使用简化的势力范围计算
        territory_map = self._calculate_territory_map(board)

        for y in range(board.size):
            for x in range(board.size):
                if territory_map[y][x] == StoneColor.BLACK:
                    stats.black_territory += 1
                elif territory_map[y][x] == StoneColor.WHITE:
                    stats.white_territory += 1

    def _calculate_territory_map(self, board: GameBoard) -> List[List[StoneColor]]:
        """计算势力范围地图"""
        territory = [
            [StoneColor.EMPTY for _ in range(board.size)] for _ in range(board.size)
        ]

        # 对每个空点进行势力判定
        for y in range(board.size):
            for x in range(board.size):
                if board.board[y][x] == StoneColor.EMPTY:
                    territory[y][x] = self._get_territory_owner(board, x, y)
                else:
                    territory[y][x] = board.board[y][x]

        return territory

    def _get_territory_owner(self, board: GameBoard, x: int, y: int) -> StoneColor:
        """判断某个空点的势力归属"""
        # 使用洪水填充算法找到连通的空域
        empty_area = []
        visited = set()
        stack = [(x, y)]

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited or board.board[cy][cx] != StoneColor.EMPTY:
                continue

            visited.add((cx, cy))
            empty_area.append((cx, cy))

            # 检查四个方向
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < board.size
                    and 0 <= ny < board.size
                    and (nx, ny) not in visited
                ):
                    stack.append((nx, ny))

        # 检查这个空域被哪种颜色的棋子包围
        surrounding_colors = set()
        for ex, ey in empty_area:
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = ex + dx, ey + dy
                if (
                    0 <= nx < board.size
                    and 0 <= ny < board.size
                    and board.board[ny][nx] != StoneColor.EMPTY
                ):
                    surrounding_colors.add(board.board[ny][nx])

        # 如果只被一种颜色包围，则属于该颜色的势力范围
        if len(surrounding_colors) == 1:
            return list(surrounding_colors)[0]
        else:
            return StoneColor.EMPTY  # 中性区域

    def calculate_scores(self):
        """计算双方得分"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        # 中国规则：目数 + 子数
        stats.black_score = (
            stats.black_territory + stats.black_stones + stats.white_captures
        )
        stats.white_score = (
            stats.white_territory
            + stats.white_stones
            + stats.black_captures
            + stats.komi
        )

    def calculate_win_rates(self):
        """计算实时胜率"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        # 基于目前得分差计算胜率
        score_diff = stats.black_score - stats.white_score

        # 使用sigmoid函数计算胜率
        # 得分差越大，胜率越接近100%或0%
        import math

        sigmoid_input = score_diff / 10.0  # 调整敏感度
        black_win_prob = 1.0 / (1.0 + math.exp(-sigmoid_input))

        stats.black_win_rate = black_win_prob
        stats.white_win_rate = 1.0 - black_win_prob
