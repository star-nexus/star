"""
UI渲染系统 - 负责游戏信息、    def __init__(self):
        super().__init__(priority=5)  # 最高优先级，最后渲染（顶层）
        self.font = None帮助等UI元素的渲染
"""

import pygame
from pathlib import Path
from framework_v2 import System, RMS
from ..components import (
    GameState,
    GameStats,
    UIState,
    TurnOrder,
    Player,
)
from ..prefabs.config import GameConfig


class UIRenderSystem(System):
    """UI渲染系统"""

    def __init__(self):
        super().__init__(priority=3)  # 较低优先级
        self.font = None
        self.small_font = None

        # 初始化字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """初始化UI渲染系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件（UI渲染系统不需要订阅事件）"""
        pass

    def update(self, delta_time: float) -> None:
        """更新UI渲染"""
        self._render_ui()

    def _render_ui(self):
        """渲染UI界面"""
        self._render_game_info()
        self._render_stats_panel()
        self._render_help_panel()

    def _render_game_info(self):
        """渲染游戏信息（顶部）"""
        game_state = self.world.get_singleton_component(GameState)
        turn_order = self.world.get_singleton_component(TurnOrder)

        if not game_state or not turn_order:
            return

        # 渲染回合信息
        turn_text = f"回合 {game_state.turn_number}"
        turn_surface = self.font.render(turn_text, True, (255, 255, 255))
        RMS.draw(turn_surface, (10, 10))

        # 渲染当前玩家
        if turn_order.current_player_index < len(turn_order.players):
            current_player = turn_order.players[turn_order.current_player_index]
            player_comp = self.world.get_component(current_player, Player)
            if player_comp:
                player_text = f"当前玩家: {player_comp.name}"
                player_color = GameConfig.FACTION_COLORS.get(
                    player_comp.faction, (255, 255, 255)
                )
                player_surface = self.font.render(player_text, True, player_color)
                RMS.draw(player_surface, (250, 10))

        # 渲染游戏阶段
        phase_text = f"阶段: {game_state.phase.value}"
        phase_surface = self.small_font.render(phase_text, True, (200, 200, 200))
        RMS.draw(phase_surface, (10, 40))

    def _render_stats_panel(self):
        """渲染统计面板"""
        ui_state = self.world.get_singleton_component(UIState)
        game_stats = self.world.get_singleton_component(GameStats)

        if not ui_state or not ui_state.show_stats or not game_stats:
            return

        # 创建统计面板背景
        panel_width = 300
        panel_height = 400
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = 150

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(200)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 绘制边框
        RMS.rect((150, 150, 150), (panel_x, panel_y, panel_width, panel_height), 2)

        # 渲染标题
        title_surface = self.font.render("游戏统计", True, (255, 255, 255))
        RMS.draw(title_surface, (panel_x + 10, panel_y + 10))

        # 渲染各阵营统计
        y_offset = panel_y + 50
        line_height = 25

        for faction, faction_stats in game_stats.faction_stats.items():
            if y_offset + line_height > panel_y + panel_height - 20:
                break

            # 安全获取阵营颜色
            color = GameConfig.FACTION_COLORS.get(faction, (255, 255, 255))

            # 阵营名称
            faction_text = f"{faction.value}:"
            faction_surface = self.font.render(faction_text, True, color)
            RMS.draw(faction_surface, (panel_x + 10, y_offset))
            y_offset += line_height

            # 统计数据
            for stat_name, stat_value in faction_stats.items():
                if y_offset + 20 > panel_y + panel_height - 20:
                    break
                stat_text = f"  {stat_name}: {stat_value}"
                stat_surface = self.small_font.render(stat_text, True, (255, 255, 255))
                RMS.draw(stat_surface, (panel_x + 10, y_offset))
                y_offset += 20

            y_offset += 10

    def _render_help_panel(self):
        """渲染帮助面板"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.show_help:
            return

        # 创建帮助面板背景
        panel_width = 500
        panel_height = 400
        panel_x = (GameConfig.WINDOW_WIDTH - panel_width) // 2
        panel_y = (GameConfig.WINDOW_HEIGHT - panel_height) // 2

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(240)
        panel_surface.fill((0, 0, 30))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 绘制边框
        RMS.rect((100, 150, 200), (panel_x, panel_y, panel_width, panel_height), 3)

        # 渲染标题
        title_surface = self.font.render("游戏帮助", True, (255, 255, 255))
        title_rect = title_surface.get_rect(
            center=(panel_x + panel_width // 2, panel_y + 30)
        )
        RMS.draw(title_surface, title_rect)

        # 渲染帮助内容
        help_content = [
            "基本操作:",
            "  鼠标左键 - 选择单位",
            "  鼠标右键 - 移动单位",
            "  鼠标中键 - 攻击敌方单位",
            "",
            "键盘快捷键:",
            "  空格键 - 结束回合",
            "  ESC键 - 取消选择",
            "  H键 - 显示/隐藏帮助",
            "  S键 - 显示/隐藏统计",
            "  B键 - 显示/隐藏战况记录",
            "",
            "游戏规则:",
            "  每个单位每回合可移动一次",
            "  攻击后单位无法再移动",
            "  单位血量为0时会死亡",
            "  消灭所有敌方单位获胜",
            "",
            "按H键关闭此帮助面板",
        ]

        y_offset = panel_y + 70
        line_height = 18

        for line in help_content:
            if y_offset + line_height > panel_y + panel_height - 20:
                break

            if line == "":
                y_offset += line_height // 2
                continue

            color = (255, 255, 255)
            if line.endswith(":"):
                color = (255, 255, 0)  # 标题用黄色
            elif line.startswith("  "):
                color = (200, 200, 200)  # 缩进内容用浅灰色

            line_surface = self.small_font.render(line, True, color)
            RMS.draw(line_surface, (panel_x + 20, y_offset))
            y_offset += line_height
