"""
渲染系统
"""

import pygame
from typing import Tuple, Optional, Set, List
from framework_v2 import System, RMS
from ..components import (
    MapData,
    Terrain,
    GameState,
    FogOfWar,
    HexPosition,
    Unit,
    Health,
    UIState,
    InputState,
    GameStats,
    Movement,
    Combat,
    Tile,
    Camera,
)
from ..prefabs.config import GameConfig, UnitType, Faction
from ..utils.hex_utils import HexConverter, HexMath, PathFinding
from pathlib import Path


class RenderSystem(System):
    """渲染系统"""

    def __init__(
        self,
    ):
        super().__init__(priority=1)  # 低优先级，最后渲染
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE)
        self.font = None
        self.small_font = None

        # 初始化字体
        pygame.font.init()
        file_path = Path("rotk/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """初始化渲染系统"""
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """渲染游戏"""
        # 获取摄像机组件
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            # 如果没有摄像机组件，使用默认偏移
            camera_offset = [400, 300]
        else:
            camera_offset = list(camera.get_offset())

        # 渲染地图
        self._render_map(camera_offset)

        # 渲染战争迷雾
        self._render_fog_of_war(camera_offset)

        # 渲染单位
        self._render_units(camera_offset)

        # 渲染选择和悬停效果
        self._render_selection_effects(camera_offset)

        # 渲染UI
        self._render_ui()

    def _render_map(self, camera_offset: List[float]):
        """渲染地图"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        for (q, r), tile_entity in map_data.tiles.items():
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue

            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x + camera_offset[0]
            screen_y = world_y + camera_offset[1]

            # 检查是否在屏幕范围内
            if (
                screen_x < -GameConfig.HEX_SIZE
                or screen_x > GameConfig.WINDOW_WIDTH + GameConfig.HEX_SIZE
                or screen_y < -GameConfig.HEX_SIZE
                or screen_y > GameConfig.WINDOW_HEIGHT + GameConfig.HEX_SIZE
            ):
                continue

            # 获取地形颜色
            color = GameConfig.TERRAIN_COLORS.get(terrain.terrain_type, (128, 128, 128))

            # 绘制六边形
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                (x + camera_offset[0], y + camera_offset[1]) for x, y in corners
            ]
            RMS.polygon(color, screen_corners)

            RMS.polygon((0, 0, 0), screen_corners, 2)

    def _render_fog_of_war(self, camera_offset: List[float]):
        """渲染战争迷雾 - 三种状态：未探索(黑色)、已探索但非视野(半透明黑色)、当前视野(绿色轮廓)"""
        game_state = self.world.get_singleton_component(GameState)
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if not game_state or not fog_of_war or not game_state.current_player:
            return

        # 获取当前玩家的视野
        current_faction = game_state.current_player
        visible_tiles = fog_of_war.faction_vision.get(current_faction, set())
        explored_tiles = fog_of_war.explored_tiles.get(current_faction, set())

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # 创建已探索但非视野区域的半透明迷雾层
        explored_fog_surface = pygame.Surface(
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
        )

        # 第一步：绘制未探索和已探索但非视野区域
        for (q, r), tile_entity in map_data.tiles.items():
            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x + camera_offset[0]
            screen_y = world_y + camera_offset[1]

            # 检查是否在屏幕范围内
            if (
                screen_x < -GameConfig.HEX_SIZE * 2
                or screen_x > GameConfig.WINDOW_WIDTH + GameConfig.HEX_SIZE * 2
                or screen_y < -GameConfig.HEX_SIZE * 2
                or screen_y > GameConfig.WINDOW_HEIGHT + GameConfig.HEX_SIZE * 2
            ):
                continue

            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                (x + camera_offset[0], y + camera_offset[1]) for x, y in corners
            ]

            if (q, r) in visible_tiles:
                # 当前视野区域：暂时跳过，稍后处理边界
                continue
            elif (q, r) in explored_tiles:
                # 已探索但非视野区域：绘制半透明黑色遮罩
                pygame.draw.polygon(
                    explored_fog_surface, GameConfig.FOG_EXPLORED_COLOR, screen_corners
                )
            else:
                # 未探索区域：绘制完全黑色
                RMS.polygon(GameConfig.FOG_UNEXPLORED_COLOR[:3], screen_corners)

        # 应用已探索区域的半透明遮罩
        RMS.draw(explored_fog_surface, (0, 0))

        # 第二步：绘制视野区域的外边界绿色轮廓
        self._render_vision_boundary(visible_tiles, camera_offset)

    def _render_vision_boundary(
        self, visible_tiles: Set[Tuple[int, int]], camera_offset: List[float]
    ):
        """绘制以单位为中心的单个视野圆圈"""
        if not visible_tiles:
            return

        # 获取当前玩家的所有单位
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return

        current_faction = game_state.current_player

        # 为每个己方单位绘制一个视野圆圈
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position or unit.faction != current_faction:
                continue

            # 计算单位中心的屏幕坐标
            center_world_x, center_world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            center_screen_x = center_world_x + camera_offset[0]
            center_screen_y = center_world_y + camera_offset[1]

            # 检查单位是否在屏幕范围内
            if (
                center_screen_x < -100
                or center_screen_x > GameConfig.WINDOW_WIDTH + 100
                or center_screen_y < -100
                or center_screen_y > GameConfig.WINDOW_HEIGHT + 100
            ):
                continue

            unit_stats = GameConfig.UNIT_STATS.get(unit.unit_type)
            if not unit_stats:
                continue

            vision_range = unit_stats.vision_range

            # 绘制单个视野圆圈（最大视野范围）
            circle_radius = vision_range * GameConfig.HEX_SIZE * 1.5

            # 绘制视野圆圈轮廓

            RMS.circle(
                GameConfig.CURRENT_VISION_OUTLINE_COLOR,
                (int(center_screen_x), int(center_screen_y)),
                int(circle_radius),
                2,
            )

    def _render_units(self, camera_offset: List[float]):
        """渲染单位"""
        for entity in self.world.query().with_all(HexPosition, Unit, Health).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)

            if not position or not unit or not health:
                continue

            # 检查单位是否可见
            if not self._is_unit_visible(entity):
                continue

            # 计算屏幕位置
            world_x, world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            screen_x = world_x + camera_offset[0]
            screen_y = world_y + camera_offset[1]

            # 检查是否在屏幕范围内
            if (
                screen_x < -GameConfig.HEX_SIZE
                or screen_x > GameConfig.WINDOW_WIDTH + GameConfig.HEX_SIZE
                or screen_y < -GameConfig.HEX_SIZE
                or screen_y > GameConfig.WINDOW_HEIGHT + GameConfig.HEX_SIZE
            ):
                continue

            # 获取单位颜色
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))

            # 绘制单位圆圈
            unit_radius = GameConfig.HEX_SIZE // 3
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

            # 绘制生命值条
            self._render_health_bar(screen_x, screen_y, health, unit_radius)

            # 绘制单位类型图标
            self._render_unit_icon(screen_x, screen_y, unit)

    def _render_health_bar(self, x: float, y: float, health: Health, radius: int):
        """渲染生命值条"""
        if health.percentage >= 1.0:
            return  # 满血不显示

        bar_width = radius * 2
        bar_height = 4
        bar_x = x - bar_width // 2
        bar_y = y - radius - 10

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

    def _render_unit_icon(self, x: float, y: float, unit: Unit):
        """渲染单位类型图标"""
        # 简单的文字图标
        icon_map = {
            UnitType.INFANTRY: "I",
            UnitType.CAVALRY: "C",
            UnitType.ARCHER: "A",
            UnitType.SIEGE: "S",
        }

        icon_text = icon_map.get(unit.unit_type, "?")
        text_surface = self.small_font.render(icon_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(int(x), int(y)))
        RMS.draw(text_surface, text_rect)

    def _render_selection_effects(self, camera_offset: List[float]):
        """渲染选择和悬停效果"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state:
            return

        # 渲染选中单位的效果
        if ui_state.selected_unit:
            self._render_unit_selection(ui_state.selected_unit, camera_offset)

        # 渲染悬停地块的效果
        if ui_state.hovered_tile:
            self._render_tile_hover(ui_state.hovered_tile, camera_offset)

    def _render_unit_selection(self, unit_entity: int, camera_offset: List[float]):
        """渲染选中单位的效果"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, Movement)
        combat = self.world.get_component(unit_entity, Combat)

        if not position:
            return

        # 计算屏幕位置
        world_x, world_y = self.hex_converter.hex_to_pixel(position.col, position.row)
        screen_x = world_x + camera_offset[0]
        screen_y = world_y + camera_offset[1]

        # 绘制选中圆圈
        RMS.circle(
            (255, 255, 0), (int(screen_x), int(screen_y)), GameConfig.HEX_SIZE // 2, 3
        )

        # 显示移动范围
        if movement and not movement.has_moved:
            self._render_movement_range(unit_entity, camera_offset)

        # 显示攻击范围
        if combat and not combat.has_attacked:
            self._render_attack_range(unit_entity, camera_offset)

    def _render_movement_range(self, unit_entity: int, camera_offset: List[float]):
        """渲染移动范围"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, Movement)

        if not position or not movement:
            return

        # 获取障碍物
        obstacles = self._get_obstacles()

        # 计算移动范围
        movement_range = PathFinding.get_movement_range(
            (position.col, position.row), movement.current_movement, obstacles
        )

        # 绘制移动范围
        for q, r in movement_range:
            if (q, r) == (position.col, position.row):
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x + camera_offset[0]
            screen_y = world_y + camera_offset[1]

            # 绘制半透明蓝色覆盖
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                (x + camera_offset[0], y + camera_offset[1]) for x, y in corners
            ]

            overlay = pygame.Surface((GameConfig.HEX_SIZE * 2, GameConfig.HEX_SIZE * 2))
            overlay.set_alpha(100)
            overlay.fill((0, 0, 255))

            # 创建六边形蒙版
            mask_surface = pygame.Surface(
                (GameConfig.HEX_SIZE * 2, GameConfig.HEX_SIZE * 2), pygame.SRCALPHA
            )
            mask_corners = [
                (x - world_x + GameConfig.HEX_SIZE, y - world_y + GameConfig.HEX_SIZE)
                for x, y in corners
            ]
            pygame.draw.polygon(mask_surface, (0, 0, 255, 100), mask_corners)

            RMS.draw(
                mask_surface,
                (screen_x - GameConfig.HEX_SIZE, screen_y - GameConfig.HEX_SIZE),
            )

    def _render_attack_range(self, unit_entity: int, camera_offset: List[float]):
        """渲染攻击范围"""
        position = self.world.get_component(unit_entity, HexPosition)
        combat = self.world.get_component(unit_entity, Combat)

        if not position or not combat:
            return

        # 计算攻击范围
        attack_range = HexMath.hex_in_range(
            position.col, position.row, combat.attack_range
        )

        # 绘制攻击范围
        for q, r in attack_range:
            if (q, r) == (position.col, position.row):
                continue

            # 检查是否有敌人在此位置
            enemy = self._get_enemy_at_position((q, r), unit_entity)
            if not enemy:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x + camera_offset[0]
            screen_y = world_y + camera_offset[1]

            # 绘制红色攻击指示器
            RMS.circle(
                (255, 0, 0),
                (int(screen_x), int(screen_y)),
                GameConfig.HEX_SIZE // 4,
                3,
            )

    def _render_tile_hover(self, tile_pos: Tuple[int, int], camera_offset: List[float]):
        """渲染悬停地块效果"""
        q, r = tile_pos
        world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
        screen_x = world_x + camera_offset[0]
        screen_y = world_y + camera_offset[1]

        # 绘制悬停边框
        corners = self.hex_converter.get_hex_corners(q, r)
        screen_corners = [
            (x + camera_offset[0], y + camera_offset[1]) for x, y in corners
        ]
        # pygame.draw.polygon(self.screen, (255, 255, 255), screen_corners, 2)
        RMS.polygon((255, 255, 255), screen_corners, 2)

    def _render_ui(self):
        """渲染UI界面"""
        self._render_game_info()

        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            if ui_state.show_stats:
                self._render_stats_panel()
            if ui_state.show_help:
                self._render_help_panel()

        # 渲染小地图

    def _render_game_info(self):
        """渲染游戏信息"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return

        # 渲染回合信息
        turn_text = f"回合: {game_state.turn_number}/{game_state.max_turns}"
        turn_surface = self.font.render(turn_text, True, (255, 255, 255))
        RMS.draw(turn_surface, (10, 10))

        # 渲染当前玩家
        if game_state.current_player:
            player_text = f"当前玩家: {game_state.current_player.value}"
            # 确保使用正确的阵营作为键
            faction_key = game_state.current_player
            if hasattr(faction_key, "value"):
                # 处理枚举类型
                for faction, color in GameConfig.FACTION_COLORS.items():
                    if faction.value == faction_key.value:
                        faction_color = color
                        break
                else:
                    faction_color = (255, 255, 255)  # 默认白色
            else:
                faction_color = GameConfig.FACTION_COLORS.get(
                    faction_key, (255, 255, 255)
                )

            player_surface = self.font.render(player_text, True, faction_color)
            RMS.draw(player_surface, (10, 40))

        # 渲染控制提示
        help_text = "空格键:结束回合 | Tab:统计 | F1:帮助 | ESC:取消选择"
        help_surface = self.small_font.render(help_text, True, (200, 200, 200))
        RMS.draw(help_surface, (10, GameConfig.WINDOW_HEIGHT - 25))

    def _render_stats_panel(self):
        """渲染统计面板"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        # 创建半透明背景
        panel_width = 300
        panel_height = 400
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = 10

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(200)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 渲染边框
        RMS.rect((255, 255, 255), (panel_x, panel_y, panel_width, panel_height), 2)

        # 渲染标题
        title_surface = self.font.render("游戏统计", True, (255, 255, 255))
        RMS.draw(title_surface, (panel_x + 10, panel_y + 10))

        # 渲染各阵营统计
        y_offset = 50
        for faction, faction_stats in stats.faction_stats.items():
            # 安全获取阵营颜色
            color = GameConfig.FACTION_COLORS.get(faction, (255, 255, 255))

            # 阵营名称
            faction_text = f"{faction.value}:"
            faction_surface = self.font.render(faction_text, True, color)
            RMS.draw(faction_surface, (panel_x + 10, panel_y + y_offset))
            y_offset += 25

            # 统计数据
            for stat_name, stat_value in faction_stats.items():
                stat_text = f"  {stat_name}: {stat_value}"
                stat_surface = self.small_font.render(stat_text, True, (255, 255, 255))
                RMS.draw(stat_surface, (panel_x + 10, panel_y + y_offset))
                y_offset += 20

            y_offset += 10

    def _render_help_panel(self):
        """渲染帮助面板"""
        # 创建半透明背景
        panel_width = 400
        panel_height = 300
        panel_x = (GameConfig.WINDOW_WIDTH - panel_width) // 2
        panel_y = (GameConfig.WINDOW_HEIGHT - panel_height) // 2

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(230)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 渲染边框
        RMS.rect((255, 255, 255), (panel_x, panel_y, panel_width, panel_height), 2)

        # 渲染帮助内容
        help_texts = [
            "游戏帮助",
            "",
            "鼠标左键: 选择单位/移动/攻击",
            "鼠标右键: 取消选择",
            "WASD/方向键: 移动摄像机",
            "空格键: 结束回合",
            "Tab键: 显示/隐藏统计",
            "F1键: 显示/隐藏帮助",
            "ESC键: 取消选择",
            "",
            "游戏目标:",
            "消灭所有敌方单位或在回合结束时",
            "获得最高的积分",
        ]

        y_offset = 10
        for text in help_texts:
            if text == "游戏帮助":
                surface = self.font.render(text, True, (255, 255, 255))
            else:
                surface = self.small_font.render(text, True, (200, 200, 200))
            RMS.draw(surface, (panel_x + 10, panel_y + y_offset))
            y_offset += 20

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

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """获取所有障碍物位置"""
        obstacles = set()

        # 添加其他单位的位置
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        return obstacles

    def _get_enemy_at_position(
        self, position: Tuple[int, int], friendly_unit: int
    ) -> Optional[int]:
        """获取指定位置的敌方单位"""
        friendly_unit_comp = self.world.get_component(friendly_unit, Unit)
        if not friendly_unit_comp:
            return None

        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if (
                pos
                and unit
                and (pos.col, pos.row) == position
                and unit.faction != friendly_unit_comp.faction
            ):
                return entity

        return None
