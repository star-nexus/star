"""
面板渲染系统 - 负责左上角单位信息、右下角战况记录    def __init__(self):
        super().__init__(priority=4)  # 在效果之上渲染面板
        self.font = None角小地图的渲染
"""

import pygame
import time
from pathlib import Path
from framework_v2 import System, RMS
from ..components import (
    UIState,
    Unit,
    Health,
    Movement,
    Combat,
    HexPosition,
    UnitStatus,
    BattleLog,
    MapData,
    Terrain,
    Camera,
    FogOfWar,
    GameState,
)
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter


class PanelRenderSystem(System):
    """面板渲染系统"""

    def __init__(self):
        super().__init__(priority=2)  # 较低优先级
        self.font = None
        self.small_font = None

        # 初始化字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """初始化面板渲染系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件（面板渲染系统不需要订阅事件）"""
        pass

    def update(self, delta_time: float) -> None:
        """更新面板渲染"""
        self._render_selected_unit_info()
        self._render_battle_log()
        # self._render_minimap()

    def _render_selected_unit_info(self):
        """渲染选中单位信息（左上角）"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.selected_unit:
            return

        unit_entity = ui_state.selected_unit
        unit = self.world.get_component(unit_entity, Unit)
        health = self.world.get_component(unit_entity, Health)
        movement = self.world.get_component(unit_entity, Movement)
        combat = self.world.get_component(unit_entity, Combat)
        position = self.world.get_component(unit_entity, HexPosition)
        status = self.world.get_component(unit_entity, UnitStatus)

        if not unit:
            return

        # 创建信息面板背景
        panel_width = 250
        panel_height = 180
        panel_x = 10
        panel_y = 80

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(220)
        panel_surface.fill((0, 0, 30))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 绘制边框
        RMS.rect((100, 150, 200), (panel_x, panel_y, panel_width, panel_height), 2)

        # 渲染单位信息
        y_offset = panel_y + 10
        line_height = 20

        # 单位类型和阵营
        unit_type_text = f"类型: {unit.unit_type.value}"
        faction_text = f"阵营: {unit.faction.value}"
        faction_color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))

        type_surface = self.small_font.render(unit_type_text, True, (255, 255, 255))
        faction_surface = self.small_font.render(faction_text, True, faction_color)

        RMS.draw(type_surface, (panel_x + 10, y_offset))
        y_offset += line_height
        RMS.draw(faction_surface, (panel_x + 10, y_offset))
        y_offset += line_height

        # 生命值
        if health:
            health_text = f"生命值: {health.current}/{health.maximum}"
            health_color = (
                (255, 0, 0)
                if health.percentage < 0.3
                else (255, 255, 0) if health.percentage < 0.7 else (0, 255, 0)
            )
            health_surface = self.small_font.render(health_text, True, health_color)
            RMS.draw(health_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # 移动力
        if movement:
            movement_text = (
                f"移动力: {movement.current_movement}/{movement.max_movement}"
            )
            movement_surface = self.small_font.render(
                movement_text, True, (0, 255, 255)
            )
            RMS.draw(movement_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # 攻击力
        if combat:
            attack_text = f"攻击力: {combat.attack}"
            attack_surface = self.small_font.render(attack_text, True, (255, 200, 0))
            RMS.draw(attack_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # 位置
        if position:
            pos_text = f"位置: ({position.col}, {position.row})"
            pos_surface = self.small_font.render(pos_text, True, (200, 200, 200))
            RMS.draw(pos_surface, (panel_x + 10, y_offset))
            y_offset += line_height

        # 状态
        if status:
            status_text = f"状态: {status.current_status}"
            status_colors = {
                "idle": (128, 128, 128),
                "moving": (0, 255, 255),
                "combat": (255, 0, 0),
                "hidden": (128, 0, 128),
                "resting": (0, 255, 0),
            }
            status_color = status_colors.get(status.current_status, (255, 255, 255))
            status_surface = self.small_font.render(status_text, True, status_color)
            RMS.draw(status_surface, (panel_x + 10, y_offset))

    def _render_battle_log(self):
        """渲染战况记录（右下角）"""
        battle_log = self.world.get_singleton_component(BattleLog)
        if not battle_log or not battle_log.show_log:
            return

        # 创建日志面板背景
        panel_width = 400
        panel_height = 200
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = GameConfig.WINDOW_HEIGHT - panel_height - 10

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(200)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 绘制边框
        RMS.rect((150, 150, 150), (panel_x, panel_y, panel_width, panel_height), 2)

        # 渲染标题
        title_surface = self.small_font.render("战况记录", True, (255, 255, 255))
        RMS.draw(title_surface, (panel_x + 10, panel_y + 5))

        # 渲染滚动指示器
        if len(battle_log.entries) > battle_log.visible_lines:
            scroll_info = f"({battle_log.scroll_offset + 1}-{min(battle_log.scroll_offset + battle_log.visible_lines, len(battle_log.entries))}/{len(battle_log.entries)})"
            scroll_surface = self.small_font.render(scroll_info, True, (180, 180, 180))
            RMS.draw(scroll_surface, (panel_x + panel_width - 100, panel_y + 5))

        # 渲染日志条目（使用可见条目）
        visible_entries = battle_log.get_visible_entries()
        y_offset = panel_y + 25
        line_height = 20

        for entry in visible_entries:
            if y_offset + line_height > panel_y + panel_height - 5:
                break

            # 渲染时间戳（简化）
            elapsed = time.time() - entry.timestamp
            if elapsed < 60:
                time_str = f"{int(elapsed)}s"
            else:
                time_str = f"{int(elapsed/60)}m"

            # 渲染消息
            message_text = f"[{time_str}] {entry.message}"
            # 限制文本长度
            if len(message_text) > 45:
                message_text = message_text[:42] + "..."

            message_surface = self.small_font.render(message_text, True, entry.color)
            RMS.draw(message_surface, (panel_x + 10, y_offset))
            y_offset += line_height

    def _render_minimap(self):
        """渲染小地图（右上角）"""
        # 小地图尺寸
        minimap_size = 120
        minimap_x = GameConfig.WINDOW_WIDTH - minimap_size - 10
        minimap_y = 10

        # 创建小地图背景
        minimap_surface = pygame.Surface((minimap_size, minimap_size))
        minimap_surface.set_alpha(200)
        minimap_surface.fill((20, 20, 40))
        RMS.draw(minimap_surface, (minimap_x, minimap_y))

        # 绘制边框
        RMS.rect((100, 100, 100), (minimap_x, minimap_y, minimap_size, minimap_size), 2)

        # 获取地图数据
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 计算缩放比例
        scale_x = minimap_size / GameConfig.MAP_WIDTH
        scale_y = minimap_size / GameConfig.MAP_HEIGHT
        scale = min(scale_x, scale_y)

        # 渲染地形（简化）
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 转换坐标
            pixel_x = (q + GameConfig.MAP_WIDTH // 2) * scale
            pixel_y = (r + GameConfig.MAP_HEIGHT // 2) * scale

            mini_x = minimap_x + pixel_x
            mini_y = minimap_y + pixel_y

            # 简化的地形颜色
            color = GameConfig.TERRAIN_COLORS.get(terrain.terrain_type, (128, 128, 128))
            # 画小点
            RMS.circle(color, (int(mini_x), int(mini_y)), 1)

        # 渲染单位
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if not position or not unit:
                continue

            # 检查单位是否可见
            if not self._is_unit_visible(entity):
                continue

            # 转换坐标
            pixel_x = (position.col + GameConfig.MAP_WIDTH // 2) * scale
            pixel_y = (position.row + GameConfig.MAP_HEIGHT // 2) * scale

            mini_x = minimap_x + pixel_x
            mini_y = minimap_y + pixel_y

            # 单位颜色
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(mini_x), int(mini_y)), 2)
            RMS.circle((0, 0, 0), (int(mini_x), int(mini_y)), 2, 1)

        # 渲染摄像机视野范围
        camera = self.world.get_singleton_component(Camera)
        if camera:
            # 简化的视野指示器
            view_size = 20
            camera_x = minimap_x + minimap_size // 2
            camera_y = minimap_y + minimap_size // 2
            RMS.rect(
                (255, 255, 0),
                (
                    camera_x - view_size // 2,
                    camera_y - view_size // 2,
                    view_size,
                    view_size,
                ),
                1,
            )

    def _is_unit_visible(self, unit_entity: int) -> bool:
        """检查单位是否可见（考虑战争迷雾）"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not fog_of_war or not position or not unit:
            return True

        # 自己阵营的单位总是可见
        if unit.faction == game_state.current_player:
            return True

        # 检查是否在当前玩家的视野内
        current_vision = fog_of_war.faction_vision.get(game_state.current_player, set())
        return (position.col, position.row) in current_vision
