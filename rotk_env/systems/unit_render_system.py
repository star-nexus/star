"""
单位渲染系统 - 负责单位、血条、图标和状态的渲染
"""

import pygame
from typing import List
from pathlib import Path
from framework_v2 import System, RMS
from ..components import (
    HexPosition,
    Unit,
    Health,
    UnitStatus,
    Camera,
    GameState,
    FogOfWar,
)
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter


class UnitRenderSystem(System):
    """单位渲染系统"""

    def __init__(self):
        super().__init__(priority=2)  # 在地图之上渲染单位
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE)
        self.font = None
        self.small_font = None

        # 初始化字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """初始化单位渲染系统"""
        self.world = world

    def subscribe_events(self):
        """订阅事件（单位渲染系统不需要订阅事件）"""
        pass

    def update(self, delta_time: float) -> None:
        """更新单位渲染"""
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # 计算摄像机偏移
        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        # 渲染单位
        self._render_units(camera_offset, zoom)
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.render_damage_numbers()

    def _render_units(self, camera_offset: List[float], zoom: float = 1.0):
        """渲染单位"""
        # 获取动画系统以获取正确的渲染位置
        animation_system = self._get_animation_system()

        for entity in self.world.query().with_all(HexPosition, Unit, Health).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)

            if not position or not unit or not health:
                continue

            # 检查单位是否可见
            if not self._is_unit_visible(entity):
                continue

            # 获取渲染位置（考虑动画）
            if animation_system:
                render_pos = animation_system.get_unit_render_position(entity)
                if render_pos:
                    world_x, world_y = render_pos
                else:
                    world_x, world_y = self.hex_converter.hex_to_pixel(
                        position.col, position.row
                    )
            else:
                world_x, world_y = self.hex_converter.hex_to_pixel(
                    position.col, position.row
                )

            # 应用缩放
            screen_x = (world_x * zoom) + camera_offset[0]
            screen_y = (world_y * zoom) + camera_offset[1]

            # 检查是否在屏幕范围内（考虑缩放）
            hex_size_scaled = GameConfig.HEX_SIZE * zoom
            if (
                screen_x < -hex_size_scaled
                or screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
                or screen_y < -hex_size_scaled
                or screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
            ):
                continue

            # 获取单位颜色
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))

            # 绘制单位圆圈（应用缩放）
            unit_radius = int((GameConfig.HEX_SIZE // 3) * zoom)
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

            # 绘制生命值条
            self._render_health_bar(screen_x, screen_y, health, unit_radius, zoom)

            # 绘制单位类型图标
            self._render_unit_icon(screen_x, screen_y, unit, zoom)

            # 绘制单位状态指示器
            status = self.world.get_component(entity, UnitStatus)
            if status:
                self._render_unit_status(screen_x, screen_y, status, unit_radius, zoom)

    def _render_health_bar(
        self, x: float, y: float, health: Health, radius: int, zoom: float = 1.0
    ):
        """渲染生命值条"""
        if health.percentage >= 1.0:
            return  # 满血不显示

        bar_width = int(radius * 2 * zoom)
        bar_height = int(4 * zoom)
        bar_x = x - bar_width // 2
        bar_y = y - radius - int(10 * zoom)

        # 背景
        RMS.rect((128, 128, 128), (bar_x, bar_y, bar_width, bar_height))

        # 生命值
        health_width = int(bar_width * health.percentage)
        health_color = (
            (255, 0, 0)
            if health.percentage < 0.3
            else (255, 255, 0) if health.percentage < 0.7 else (0, 255, 0)
        )
        RMS.rect(health_color, (bar_x, bar_y, health_width, bar_height))

    def _render_unit_icon(self, x: float, y: float, unit: Unit, zoom: float = 1.0):
        """渲染单位类型图标"""
        icon_map = {
            "infantry": "兵",
            "cavalry": "骑",
            "archer": "弓",
            "siege": "攻",
        }

        # 将UnitType枚举转换为字符串
        unit_type_str = (
            unit.unit_type.value
            if hasattr(unit.unit_type, "value")
            else str(unit.unit_type).lower()
        )
        icon_text = icon_map.get(unit_type_str, "?")

        # 根据缩放调整字体大小
        font_size = max(8, int(16 * zoom))
        font = pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), font_size)

        text_surface = font.render(icon_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(int(x), int(y)))

        RMS.draw(text_surface, text_rect)

    def _render_unit_status(
        self,
        screen_x: float,
        screen_y: float,
        status: UnitStatus,
        unit_radius: int,
        zoom: float = 1.0,
    ):
        """渲染单位状态指示器"""
        if not status:  # or status.current_status == "idle":  # "normal":
            return

        # 状态颜色映射
        # status_colors = {
        #     "moved": (100, 100, 255),      # 蓝色 - 已移动
        #     "attacked": (255, 100, 100),   # 红色 - 已攻击
        #     "exhausted": (150, 150, 150),  # 灰色 - 精疲力竭
        #     "defending": (100, 255, 100),  # 绿色 - 防御状态
        # }
        # 状态颜色映射
        status_colors = {
            "idle": (128, 128, 128),  # 灰色 - 待机
            "moving": (0, 255, 255),  # 青色 - 移动
            "combat": (255, 0, 0),  # 红色 - 战斗
            "hidden": (128, 0, 128),  # 紫色 - 隐蔽
            "resting": (0, 255, 0),  # 绿色 - 休整
        }

        status_text_map = {
            "moved": "移",
            "attacked": "攻",
            "exhausted": "疲",
            "defending": "防",
        }

        if status.current_status in status_colors:
            # 绘制状态指示器圆圈
            # status_radius = int(8 * zoom)
            # status_x = x + radius + int(10 * zoom)
            # status_y = y - radius - int(10 * zoom)

            # RMS.circle(color, (int(status_x), int(status_y)), status_radius)
            # RMS.circle((0, 0, 0), (int(status_x), int(status_y)), status_radius, 1)

            # 在单位右上角绘制状态指示器
            indicator_size = int(4 * zoom)
            indicator_x = screen_x + unit_radius * 0.7
            indicator_y = screen_y - unit_radius * 0.7

            color = status_colors[status.current_status]
            RMS.circle(color, (int(indicator_x), int(indicator_y)), indicator_size)
            RMS.circle(
                (0, 0, 0), (int(indicator_x), int(indicator_y)), indicator_size, 1
            )

            # 绘制状态文字
            status_text = status_text_map.get(status.current_status, "")
            if status_text:
                font_size = max(10, int(12 * zoom))
                font = pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), font_size)

                text_surface = font.render(status_text, True, (255, 255, 255))
                # text_rect = text_surface.get_rect(center=(int(status_x), int(status_y)))
                text_rect = text_surface.get_rect(
                    center=(int(indicator_x), int(indicator_y))
                )
                RMS.draw(text_surface, text_rect)

    def _is_unit_visible(self, unit_entity: int) -> bool:
        """检查单位是否可见"""
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

    def _get_animation_system(self):
        """获取动画系统"""
        # 这里可以从world中获取动画系统
        # 暂时返回None，如果需要可以实现
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None
