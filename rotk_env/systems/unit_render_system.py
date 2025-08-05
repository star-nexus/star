"""
单位渲染系统 - 负责单位、血条、图标和状态的渲染
"""

import pygame
import os
from typing import List, Dict, Optional
from pathlib import Path
from framework import System, RMS
from ..components import (
    HexPosition,
    Unit,
    UnitCount,
    UnitStatus,
    Camera,
    GameState,
    FogOfWar,
    UIState,
)
from ..prefabs.config import GameConfig, HexOrientation, UnitType, Faction
from ..utils.hex_utils import HexConverter


class UnitRenderSystem(System):
    """单位渲染系统"""

    def __init__(self):
        super().__init__(priority=2)  # 在地图之上渲染单位
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.font = None
        self.small_font = None
        
        # 单位贴图缓存
        self.unit_textures: Dict[str, pygame.Surface] = {}
        self.textures_loaded = False

        # 初始化字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """初始化单位渲染系统"""
        self.world = world
        self._load_unit_textures()

    def _load_unit_textures(self) -> None:
        """加载单位贴图"""
        assets_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "texture", "units"
        )

        if not os.path.exists(assets_path):
            print(f"警告：单位贴图目录不存在: {assets_path}")
            return

        # 遍历所有阵营和兵种组合
        for faction in Faction:
            faction_dir = os.path.join(assets_path, faction.value)
            if not os.path.exists(faction_dir):
                continue
                
            for unit_type in UnitType:
                texture_file = f"{unit_type.value}.png"
                texture_path = os.path.join(faction_dir, texture_file)
                
                if os.path.exists(texture_path):
                    try:
                        texture = pygame.image.load(texture_path).convert_alpha()
                        # 缩放贴图到合适的大小 (基于HEX_SIZE)
                        size = GameConfig.HEX_SIZE
                        texture = pygame.transform.scale(texture, (size, size))
                        
                        # 使用 "阵营_兵种" 作为key存储
                        key = f"{faction.value}_{unit_type.value}"
                        self.unit_textures[key] = texture
                        print(f"成功加载单位贴图: {key}")
                    except pygame.error as e:
                        print(f"警告：无法加载贴图 {texture_path}: {e}")

        # 检查加载结果
        if len(self.unit_textures) > 0:
            self.textures_loaded = True
            print(f"单位贴图加载完成，共加载 {len(self.unit_textures)} 个贴图")
        else:
            print("警告：没有加载到任何单位贴图，将使用默认圆形渲染")

    def _get_unit_texture(self, faction: Faction, unit_type: UnitType) -> Optional[pygame.Surface]:
        """获取指定阵营和兵种的贴图"""
        key = f"{faction.value}_{unit_type.value}"
        return self.unit_textures.get(key)

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

        # 收集所有可见单位并按位置分组
        units_by_position = {}

        for entity in (
            self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        ):
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            if not position or not unit or not unit_count:
                continue

            # 检查单位是否可见
            if not self._is_unit_visible(entity):
                continue

            # 获取基础位置（不考虑动画，因为我们需要按逻辑位置分组）
            pos_key = (position.col, position.row)
            if pos_key not in units_by_position:
                units_by_position[pos_key] = []
            units_by_position[pos_key].append(entity)

        # 渲染每个位置的单位组
        for pos_key, units in units_by_position.items():
            self._render_unit_group(
                pos_key, units, camera_offset, zoom, animation_system
            )

    def _render_unit_group(self, pos_key, units, camera_offset, zoom, animation_system):
        """渲染同一位置的单位组"""
        # 按阵营分组
        units_by_faction = {}
        for entity in units:
            unit = self.world.get_component(entity, Unit)
            if unit:
                if unit.faction not in units_by_faction:
                    units_by_faction[unit.faction] = []
                units_by_faction[unit.faction].append(entity)

        # 获取基础位置
        base_world_x, base_world_y = self.hex_converter.hex_to_pixel(
            pos_key[0], pos_key[1]
        )
        base_screen_x = (base_world_x * zoom) + camera_offset[0]
        base_screen_y = (base_world_y * zoom) + camera_offset[1]

        # 检查是否在屏幕范围内
        hex_size_scaled = GameConfig.HEX_SIZE * zoom
        if (
            base_screen_x < -hex_size_scaled
            or base_screen_x > GameConfig.WINDOW_WIDTH + hex_size_scaled
            or base_screen_y < -hex_size_scaled
            or base_screen_y > GameConfig.WINDOW_HEIGHT + hex_size_scaled
        ):
            return

        factions = list(units_by_faction.keys())
        total_factions = len(factions)

        if total_factions == 1:
            # 同一阵营：在六边形内等分排列
            faction = factions[0]
            faction_units = units_by_faction[faction]
            self._render_same_faction_units(
                faction_units, base_screen_x, base_screen_y, zoom, animation_system
            )
        else:
            # 多个阵营：分两半，每半各自等分排列
            self._render_multi_faction_units(
                units_by_faction, base_screen_x, base_screen_y, zoom, animation_system
            )

    def _render_same_faction_units(self, units, base_x, base_y, zoom, animation_system):
        """渲染同一阵营的多个单位"""
        unit_count = len(units)
        if unit_count == 1:
            # 只有一个单位，正常渲染在中心
            self._render_single_unit(units[0], base_x, base_y, zoom, animation_system)
        else:
            # 多个单位，在六边形内等分排列
            positions = self._calculate_unit_positions_in_hex(
                unit_count, base_x, base_y, zoom
            )
            for i, entity in enumerate(units):
                x, y = positions[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)

    def _render_multi_faction_units(
        self, units_by_faction, base_x, base_y, zoom, animation_system
    ):
        """渲染多个阵营的单位"""
        factions = list(units_by_faction.keys())

        # 计算每个阵营的区域
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8  # 稍微缩小避免溢出

        if len(factions) == 2:
            # 两个阵营：左右分布
            faction1, faction2 = factions

            # 左侧区域中心
            left_x = base_x - hex_radius * 0.3
            left_y = base_y

            # 右侧区域中心
            right_x = base_x + hex_radius * 0.3
            right_y = base_y

            # 渲染第一个阵营（左侧）
            units1 = units_by_faction[faction1]
            positions1 = self._calculate_unit_positions_in_area(
                len(units1), left_x, left_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units1):
                x, y = positions1[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)

            # 渲染第二个阵营（右侧）
            units2 = units_by_faction[faction2]
            positions2 = self._calculate_unit_positions_in_area(
                len(units2), right_x, right_y, hex_radius * 0.6, zoom
            )
            for i, entity in enumerate(units2):
                x, y = positions2[i]
                self._render_single_unit(entity, x, y, zoom, animation_system)
        else:
            # 三个或更多阵营：环形分布
            import math

            for i, faction in enumerate(factions):
                angle = (2 * math.pi * i) / len(factions)
                area_x = base_x + hex_radius * 0.4 * math.cos(angle)
                area_y = base_y + hex_radius * 0.4 * math.sin(angle)

                units = units_by_faction[faction]
                positions = self._calculate_unit_positions_in_area(
                    len(units), area_x, area_y, hex_radius * 0.4, zoom
                )
                for j, entity in enumerate(units):
                    x, y = positions[j]
                    self._render_single_unit(entity, x, y, zoom, animation_system)

    def _calculate_unit_positions_in_hex(self, unit_count, center_x, center_y, zoom):
        """计算六边形内单位的等分位置，确保不重叠"""
        import math

        positions = []
        # 基础单位半径
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8
        # 六边形可用半径（留出边界）
        hex_radius = GameConfig.HEX_SIZE * zoom * 0.8

        if unit_count == 1:
            # 单个单位：位于中心
            positions.append((center_x, center_y))
        elif unit_count == 2:
            # 两个单位：上下排列，确保不重叠
            offset = max(unit_radius * 1.2, hex_radius * 0.3)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            # 三个单位：三角形排列
            offset = max(unit_radius * 1.2, hex_radius * 0.4)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        elif unit_count == 4:
            # 四个单位：正方形排列
            offset = max(unit_radius * 1.1, hex_radius * 0.35)
            positions.append((center_x - offset, center_y - offset))
            positions.append((center_x + offset, center_y - offset))
            positions.append((center_x - offset, center_y + offset))
            positions.append((center_x + offset, center_y + offset))
        elif unit_count == 5:
            # 五个单位：中心+四周
            center_pos = (center_x, center_y)
            positions.append(center_pos)

            offset = max(unit_radius * 1.3, hex_radius * 0.4)
            for i in range(4):
                angle = (math.pi / 2) * i  # 90度间隔
                x = center_x + offset * math.cos(angle)
                y = center_y + offset * math.sin(angle)
                positions.append((x, y))
        elif unit_count == 6:
            # 六个单位：六边形排列
            radius = max(unit_radius * 1.2, hex_radius * 0.45)
            for i in range(6):
                angle = (2 * math.pi * i) / 6
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions.append((x, y))
        else:
            # 更多单位：双层环形排列
            if unit_count <= 12:
                # 单层环形
                radius = max(unit_radius * 1.1, hex_radius * 0.5)
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # 双层环形：内层6个，外层其余
                # 内层
                inner_radius = max(unit_radius * 1.0, hex_radius * 0.3)
                for i in range(6):
                    angle = (2 * math.pi * i) / 6
                    x = center_x + inner_radius * math.cos(angle)
                    y = center_y + inner_radius * math.sin(angle)
                    positions.append((x, y))

                # 外层
                outer_count = unit_count - 6
                outer_radius = max(unit_radius * 1.2, hex_radius * 0.6)
                for i in range(outer_count):
                    angle = (2 * math.pi * i) / outer_count
                    x = center_x + outer_radius * math.cos(angle)
                    y = center_y + outer_radius * math.sin(angle)
                    positions.append((x, y))

        return positions

    def _calculate_unit_positions_in_area(
        self, unit_count, center_x, center_y, area_radius, zoom
    ):
        """计算指定区域内单位的等分位置，确保不重叠"""
        import math

        positions = []
        # 基础单位半径
        unit_radius = GameConfig.HEX_SIZE // 3 * zoom * 0.8

        if unit_count == 1:
            positions.append((center_x, center_y))
        elif unit_count == 2:
            # 两个单位：上下排列
            offset = max(unit_radius * 1.2, area_radius * 0.6)
            positions.append((center_x, center_y - offset))
            positions.append((center_x, center_y + offset))
        elif unit_count == 3:
            # 三个单位：三角形排列
            offset = max(unit_radius * 1.1, area_radius * 0.7)
            positions.append((center_x, center_y - offset))
            positions.append((center_x - offset * 0.866, center_y + offset * 0.5))
            positions.append((center_x + offset * 0.866, center_y + offset * 0.5))
        else:
            # 多个单位：环形排列，根据区域大小调整半径
            radius = max(unit_radius * 1.0, area_radius * 0.8)
            # 确保单位之间不重叠
            min_distance = unit_radius * 2.2
            circle_circumference = 2 * math.pi * radius
            max_units_on_circle = int(circle_circumference / min_distance)

            if unit_count <= max_units_on_circle:
                # 单层环形
                for i in range(unit_count):
                    angle = (2 * math.pi * i) / unit_count
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    positions.append((x, y))
            else:
                # 多层环形或紧凑排列
                # 简化为紧凑的网格排列
                cols = int(math.ceil(math.sqrt(unit_count)))
                rows = int(math.ceil(unit_count / cols))

                # 计算网格间距
                grid_spacing = max(unit_radius * 2.2, area_radius * 2 / max(cols, rows))

                # 计算起始位置（居中）
                start_x = center_x - (cols - 1) * grid_spacing / 2
                start_y = center_y - (rows - 1) * grid_spacing / 2

                for i in range(unit_count):
                    row = i // cols
                    col = i % cols
                    x = start_x + col * grid_spacing
                    y = start_y + row * grid_spacing
                    positions.append((x, y))

        return positions

    def _render_single_unit(self, entity, screen_x, screen_y, zoom, animation_system):
        """渲染单个单位"""
        position = self.world.get_component(entity, HexPosition)
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)

        if not position or not unit or not unit_count:
            return

        # 只有在单位正在移动动画时才使用动画位置，否则使用分组布局位置
        use_animation_pos = False
        if animation_system:
            render_pos = animation_system.get_unit_render_position(entity)
            if render_pos:
                # 检查单位是否正在移动（有动画位置且不在目标位置）
                world_x, world_y = render_pos
                target_world_x, target_world_y = self.hex_converter.hex_to_pixel(
                    position.col, position.row
                )

                # 如果动画位置与目标位置差距较大，说明正在移动，使用动画位置
                distance = (
                    (world_x - target_world_x) ** 2 + (world_y - target_world_y) ** 2
                ) ** 0.5
                if distance > 5:  # 距离阈值，可以调整
                    screen_x = (world_x * zoom) + self.world.get_singleton_component(
                        Camera
                    ).offset_x
                    screen_y = (world_y * zoom) + self.world.get_singleton_component(
                        Camera
                    ).offset_y
                    use_animation_pos = True

        # 动态调整单位大小：根据是否使用动画位置和单位密度
        base_radius = GameConfig.HEX_SIZE // 3
        if use_animation_pos:
            # 移动动画中保持正常大小
            scale_factor = 1.0
        else:
            # 静态状态下根据同格单位数量调整大小
            units_in_same_hex = self._get_units_in_same_hex(entity)
            unit_count_in_hex = len(units_in_same_hex)

            if unit_count_in_hex == 1:
                scale_factor = 1.0
            elif unit_count_in_hex <= 3:
                scale_factor = 0.8
            elif unit_count_in_hex <= 6:
                scale_factor = 0.7
            else:
                scale_factor = 0.6

        # 尝试使用贴图渲染，如果没有贴图则回退到圆形
        texture = self._get_unit_texture(unit.faction, unit.unit_type)
        
        if texture and self.textures_loaded:
            # 使用贴图渲染
            self._render_unit_texture(texture, screen_x, screen_y, zoom, scale_factor)
        else:
            # 回退到原来的圆形渲染
            print("回退到原来的圆形渲染")
            unit_radius = int(base_radius * zoom * scale_factor)
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)

        # 绘制人数条（使用相同的缩放）
        unit_radius = int(base_radius * zoom * scale_factor)
        self._render_unit_count_bar(
            screen_x, screen_y, unit_count, unit_radius, zoom, scale=scale_factor
        )

        # 绘制单位类型图标（使用相同的缩放）
        self._render_unit_icon(screen_x, screen_y, unit, zoom, scale=scale_factor)

        # 绘制单位状态指示器
        status = self.world.get_component(entity, UnitStatus)
        if status:
            self._render_unit_status(screen_x, screen_y, status, unit_radius, zoom)

    def _render_unit_count_bar(
        self, screen_x, screen_y, unit_count, unit_radius, zoom, scale=1.0
    ):
        """渲染单位人数条"""
        if unit_count.current_count <= 1:
            return

        # 计算血条尺寸（应用缩放）
        bar_width = int(unit_radius * 2 * zoom * scale)
        bar_height = int(5 * zoom * scale)
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - unit_radius - int(10 * zoom * scale)

        # 计算满员比例
        fill_ratio = unit_count.current_count / unit_count.max_count
        fill_width = int(bar_width * fill_ratio)

        # 绘制背景条
        RMS.rect(
            (100, 100, 100),
            (bar_x, bar_y, bar_width, bar_height),
        )

        # 绘制填充条
        if fill_ratio > 0.7:
            fill_color = (0, 255, 0)  # 绿色
        elif fill_ratio > 0.3:
            fill_color = (255, 255, 0)  # 黄色
        else:
            fill_color = (255, 0, 0)  # 红色

        if fill_width > 0:
            RMS.rect(
                fill_color,
                (bar_x, bar_y, fill_width, bar_height),
            )

        # 绘制边框
        RMS.rect(
            (255, 255, 255),
            (bar_x, bar_y, bar_width, bar_height),
            1,
        )

    def _render_unit_icon(self, screen_x, screen_y, unit, zoom, scale=1.0):
        """渲染单位类型图标"""
        # 根据单位类型选择符号
        unit_symbols = {
            UnitType.INFANTRY: "兵",
            UnitType.CAVALRY: "骑",
            UnitType.ARCHER: "弓",
            # UnitType.SIEGE: "攻",
        }

        symbol = unit_symbols.get(unit.unit_type, "？")

        # 计算字体大小（应用缩放）
        font_size = int(14 * zoom * scale)

        if font_size < 8:  # 避免字体过小
            return

        try:
            font = pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), font_size)
            text_surface = font.render(symbol, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(int(screen_x), int(screen_y)))
            RMS.draw(text_surface, text_rect)
        except:
            # 如果字体渲染失败，跳过
            pass

    def _render_unit_texture(self, texture: pygame.Surface, screen_x: float, screen_y: float, zoom: float, scale_factor: float):
        """渲染单位贴图"""
        # 计算贴图大小
        texture_size = int(GameConfig.HEX_SIZE * zoom * scale_factor)
        
        # 如果需要缩放贴图
        if texture_size != texture.get_width():
            scaled_texture = pygame.transform.scale(texture, (texture_size, texture_size))
        else:
            scaled_texture = texture
        
        # 计算贴图位置（中心对齐）
        texture_x = screen_x - texture_size // 2
        texture_y = screen_y - texture_size // 2
        
        # 渲染贴图
        RMS.draw(scaled_texture, (int(texture_x), int(texture_y)))

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
        ui_state = self.world.get_singleton_component(UIState)
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not game_state or not fog_of_war or not position or not unit or not ui_state:
            return True

        # 上帝视角模式：所有单位都可见
        if ui_state.god_mode:
            return True

        # 确定当前查看的阵营
        view_faction = (
            ui_state.view_faction
            if ui_state.view_faction
            else game_state.current_player
        )

        # 自己阵营的单位总是可见
        if unit.faction == view_faction:
            return True

        # 检查是否在查看阵营的视野内
        current_vision = fog_of_war.faction_vision.get(view_faction, set())
        return (position.col, position.row) in current_vision

    def _get_units_in_same_hex(self, target_entity):
        """获取与目标单位在同一六边形格子内的所有单位"""
        target_position = self.world.get_component(target_entity, HexPosition)
        if not target_position:
            return [target_entity]

        units_in_hex = []
        for entity in (
            self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        ):
            if not self._is_unit_visible(entity):
                continue

            position = self.world.get_component(entity, HexPosition)
            if (
                position
                and position.col == target_position.col
                and position.row == target_position.row
            ):
                units_in_hex.append(entity)

        return units_in_hex

    def _get_animation_system(self):
        """获取动画系统"""
        # 这里可以从world中获取动画系统
        # 暂时返回None，如果需要可以实现
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None
