"""
单位行动面板渲染系统
"""

import pygame
from pathlib import Path
from framework import System, RMS
from ..components import (
    UIState,
    GameState,
    UnitActionPanel,
    ActionConfirmDialog,
    UnitActionButton,
    Unit,
    Player,
)
from ..prefabs.config import GameConfig, Faction, ActionType


class UnitActionPanelSystem(System):
    """单位行动面板系统"""

    def __init__(self):
        super().__init__(priority=4)  # 在UI渲染系统之前
        self.font = None
        self.small_font = None
        self.title_font = None

        # 初始化字体
        pygame.font.init()
        font_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(font_path, 18)
        self.small_font = pygame.font.Font(font_path, 14)
        self.title_font = pygame.font.Font(font_path, 20)

        # 颜色定义
        self.panel_bg_color = (40, 40, 50, 180)  # 半透明深色背景
        self.button_bg_color = (60, 60, 70)
        self.button_hover_color = (80, 80, 90)
        self.button_disabled_color = (30, 30, 35)
        self.text_color = (255, 255, 255)
        self.text_disabled_color = (128, 128, 128)
        self.border_color = (100, 100, 110)

        # 阵营颜色
        self.faction_colors = {
            Faction.WEI: (100, 150, 255),
            Faction.SHU: (255, 100, 100),
            Faction.WU: (100, 255, 100),
        }

    def initialize(self, world) -> None:
        """初始化系统"""
        self.world = world

        # 初始化单位行动面板
        action_panel = UnitActionPanel()
        self.world.add_singleton_component(action_panel)

        # 初始化确认对话框
        confirm_dialog = ActionConfirmDialog()
        self.world.add_singleton_component(confirm_dialog)

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新系统"""
        ui_state = self.world.get_singleton_component(UIState)
        action_panel = self.world.get_singleton_component(UnitActionPanel)

        if not ui_state or not action_panel:
            return

        # 检查是否需要更新面板
        if ui_state.selected_unit != action_panel.selected_unit:
            if ui_state.selected_unit:
                self._update_action_panel(ui_state.selected_unit, action_panel)
            else:
                action_panel.clear()

        # 渲染面板
        if action_panel.visible:
            self._render_action_panel(action_panel)

        # 渲染确认对话框
        confirm_dialog = self.world.get_singleton_component(ActionConfirmDialog)
        if confirm_dialog and confirm_dialog.visible:
            self._render_confirm_dialog(confirm_dialog)

    def _update_action_panel(self, unit_entity: int, action_panel: UnitActionPanel):
        """更新行动面板"""
        # 检查单位是否属于当前玩家
        if not self._is_player_unit(unit_entity):
            action_panel.clear()
            return

        # 更新单位信息和可用行动
        action_panel.update_unit_info(unit_entity, self.world)
        action_panel.update_available_actions(unit_entity, self.world)
        action_panel.visible = True

    def _is_player_unit(self, unit_entity: int) -> bool:
        """检查单位是否属于人类玩家"""
        unit = self.world.get_component(unit_entity, Unit)
        if not unit:
            return False

        # 查找该阵营的玩家
        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == unit.faction:
                # 检查是否是人类玩家（不是AI控制）
                from ..components import AIControlled

                return not self.world.has_component(entity, AIControlled)

        return False

    def _render_action_panel(self, action_panel: UnitActionPanel):
        """渲染行动面板"""
        # 创建面板背景
        panel_surface = pygame.Surface(
            (action_panel.width, action_panel.height), pygame.SRCALPHA
        )
        panel_surface.fill(self.panel_bg_color)

        # 绘制边框
        pygame.draw.rect(
            panel_surface,
            self.border_color,
            (0, 0, action_panel.width, action_panel.height),
            2,
        )

        y_offset = 10

        # 渲染标题
        title_text = self.title_font.render("单位行动", True, self.text_color)
        panel_surface.blit(title_text, (10, y_offset))
        y_offset += 30

        # 渲染单位信息
        y_offset = self._render_unit_info(
            panel_surface, action_panel.unit_info, y_offset
        )

        # 分隔线
        pygame.draw.line(
            panel_surface,
            self.border_color,
            (10, y_offset),
            (action_panel.width - 10, y_offset),
        )
        y_offset += 10

        # 渲染行动按钮
        self._render_action_buttons(
            panel_surface, action_panel.available_actions, y_offset
        )

        # 将面板绘制到屏幕
        RMS.draw(panel_surface, (action_panel.x, action_panel.y))

    def _render_unit_info(self, surface, unit_info, y_offset):
        """渲染单位信息"""
        info_items = [
            ("名称", unit_info.get("name", "未知")),
            ("阵营", unit_info.get("faction", "未知")),
            ("类型", unit_info.get("type", "未知")),
            ("位置", unit_info.get("position", "未知")),
            ("兵力", unit_info.get("soldiers", "0/0")),
            ("士气", unit_info.get("morale", "100.0%")),
            ("行动力", unit_info.get("action_points", "0/0")),
            ("移动力", unit_info.get("movement", "0/0")),
            ("攻击力", unit_info.get("attack", 0)),
            ("防御力", unit_info.get("defense", 0)),
            ("射程", unit_info.get("range", 1)),
        ]

        for label, value in info_items:
            # 标签
            label_text = self.small_font.render(f"{label}:", True, self.text_color)
            surface.blit(label_text, (10, y_offset))

            # 值
            value_text = self.small_font.render(str(value), True, self.text_color)
            surface.blit(value_text, (100, y_offset))

            y_offset += 20

        # 显示状态
        if unit_info.get("is_decimated"):
            status_text = self.small_font.render("状态: 残破", True, (255, 100, 100))
            surface.blit(status_text, (10, y_offset))
            y_offset += 20

        if unit_info.get("has_moved"):
            status_text = self.small_font.render("状态: 已移动", True, (255, 200, 100))
            surface.blit(status_text, (10, y_offset))
            y_offset += 20

        if unit_info.get("has_attacked"):
            status_text = self.small_font.render("状态: 已攻击", True, (255, 200, 100))
            surface.blit(status_text, (10, y_offset))
            y_offset += 20

        return y_offset + 10

    def _render_action_buttons(self, surface, actions, y_offset):
        """渲染行动按钮"""
        button_height = 35
        button_margin = 5

        for i, action in enumerate(actions):
            button_y = y_offset + i * (button_height + button_margin)
            button_rect = pygame.Rect(
                10, button_y, surface.get_width() - 20, button_height
            )

            # 按钮背景色
            bg_color = (
                self.button_bg_color if action.enabled else self.button_disabled_color
            )
            pygame.draw.rect(surface, bg_color, button_rect)
            pygame.draw.rect(surface, self.border_color, button_rect, 1)

            # 按钮文本
            text_color = self.text_color if action.enabled else self.text_disabled_color

            # 主要标签
            label_text = self.font.render(action.label, True, text_color)
            surface.blit(label_text, (button_rect.x + 5, button_rect.y + 2))

            # 热键提示
            if action.hotkey:
                hotkey_text = self.small_font.render(
                    f"[{action.hotkey}]", True, text_color
                )
                surface.blit(hotkey_text, (button_rect.right - 35, button_rect.y + 2))

            # 消耗描述
            if action.cost_description:
                cost_text = self.small_font.render(
                    action.cost_description, True, text_color
                )
                surface.blit(cost_text, (button_rect.x + 5, button_rect.y + 18))

    def _render_confirm_dialog(self, confirm_dialog: ActionConfirmDialog):
        """渲染确认对话框"""
        dialog_width = 300
        dialog_height = 150
        dialog_x = (GameConfig.WINDOW_WIDTH - dialog_width) // 2
        dialog_y = (GameConfig.WINDOW_HEIGHT - dialog_height) // 2

        # 创建对话框背景
        dialog_surface = pygame.Surface((dialog_width, dialog_height), pygame.SRCALPHA)
        dialog_surface.fill((20, 20, 30, 220))

        # 绘制边框
        pygame.draw.rect(
            dialog_surface, self.border_color, (0, 0, dialog_width, dialog_height), 3
        )

        # 标题
        title_text = self.title_font.render("确认行动", True, self.text_color)
        title_rect = title_text.get_rect(centerx=dialog_width // 2, y=10)
        dialog_surface.blit(title_text, title_rect)

        # 消息文本
        message_lines = self._wrap_text(
            confirm_dialog.message, self.font, dialog_width - 20
        )
        y_offset = 40
        for line in message_lines:
            line_text = self.font.render(line, True, self.text_color)
            line_rect = line_text.get_rect(centerx=dialog_width // 2, y=y_offset)
            dialog_surface.blit(line_text, line_rect)
            y_offset += 25

        # 按钮
        button_width = 80
        button_height = 30
        button_y = dialog_height - 40

        # 确认按钮
        confirm_rect = pygame.Rect(
            dialog_width // 2 - button_width - 10, button_y, button_width, button_height
        )
        pygame.draw.rect(dialog_surface, (100, 150, 100), confirm_rect)
        pygame.draw.rect(dialog_surface, self.border_color, confirm_rect, 1)
        confirm_text = self.font.render("确认", True, self.text_color)
        confirm_text_rect = confirm_text.get_rect(center=confirm_rect.center)
        dialog_surface.blit(confirm_text, confirm_text_rect)

        # 取消按钮
        cancel_rect = pygame.Rect(
            dialog_width // 2 + 10, button_y, button_width, button_height
        )
        pygame.draw.rect(dialog_surface, (150, 100, 100), cancel_rect)
        pygame.draw.rect(dialog_surface, self.border_color, cancel_rect, 1)
        cancel_text = self.font.render("取消", True, self.text_color)
        cancel_text_rect = cancel_text.get_rect(center=cancel_rect.center)
        dialog_surface.blit(cancel_text, cancel_text_rect)

        # 将对话框绘制到屏幕
        RMS.draw(dialog_surface, (dialog_x, dialog_y))

    def _wrap_text(self, text, font, max_width):
        """文本换行"""
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            test_width = font.size(test_line)[0]

            if test_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def handle_panel_click(self, mouse_pos):
        """处理面板点击"""
        action_panel = self.world.get_singleton_component(UnitActionPanel)
        if not action_panel or not action_panel.visible:
            return False

        # 检查是否点击在面板内
        panel_rect = pygame.Rect(
            action_panel.x, action_panel.y, action_panel.width, action_panel.height
        )
        if not panel_rect.collidepoint(mouse_pos):
            return False

        # 计算点击的按钮
        button_start_y = action_panel.y + 200  # 估算按钮开始位置
        button_height = 35
        button_margin = 5

        relative_y = mouse_pos[1] - button_start_y
        if relative_y < 0:
            return True  # 点击在面板上但不在按钮区域

        button_index = relative_y // (button_height + button_margin)

        if 0 <= button_index < len(action_panel.available_actions):
            action = action_panel.available_actions[button_index]
            if action.enabled:
                self._execute_action(action.action_type, action_panel.selected_unit)

        return True

    def _execute_action(self, action_type, unit_entity):
        """执行行动"""
        # 这里可以触发相应的行动系统
        print(f"执行行动: {action_type} on unit {unit_entity}")

        # 根据行动类型执行不同的逻辑
        if action_type == ActionType.WAIT:
            self._execute_wait_action(unit_entity)
        elif action_type == ActionType.GARRISON:
            self._execute_garrison_action(unit_entity)
        elif action_type == ActionType.CAPTURE:
            self._execute_capture_action(unit_entity)
        elif action_type == ActionType.FORTIFY:
            self._execute_fortify_action(unit_entity)
        # 移动和攻击需要用户选择目标，在输入系统中处理

    def _execute_wait_action(self, unit_entity):
        """执行待命行动"""
        from ..components import ActionPoints

        action_points = self.world.get_component(unit_entity, ActionPoints)
        if action_points and action_points.can_perform_action(ActionType.WAIT):
            action_points.consume_ap(ActionType.WAIT)
            print(f"单位 {unit_entity} 结束行动")

    def _execute_garrison_action(self, unit_entity):
        """执行驻扎行动"""
        from ..components import ActionPoints

        action_points = self.world.get_component(unit_entity, ActionPoints)
        if action_points and action_points.can_perform_action(ActionType.GARRISON):
            action_points.consume_ap(ActionType.GARRISON)
            print(f"单位 {unit_entity} 开始驻扎")

    def _execute_capture_action(self, unit_entity):
        """执行占领行动"""
        from ..components import HexPosition

        position = self.world.get_component(unit_entity, HexPosition)
        if position:
            territory_system = self._get_territory_system()
            if territory_system:
                territory_system.start_capture(
                    unit_entity, (position.col, position.row)
                )

    def _execute_fortify_action(self, unit_entity):
        """执行工事建设行动"""
        from ..components import HexPosition

        position = self.world.get_component(unit_entity, HexPosition)
        if position:
            territory_system = self._get_territory_system()
            if territory_system:
                territory_system.build_fortification(
                    unit_entity, (position.col, position.row)
                )

    def _get_territory_system(self):
        """获取领土系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None
