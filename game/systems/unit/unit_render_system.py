import pygame
import numpy as np
from typing import Dict, Tuple, List, Optional
from framework.ecs.system import System
from framework.utils.logging import get_logger
from game.components import (
    UnitComponent,
    CameraComponent,
)
from framework.engine.events import EventMessage, EventType
from game.utils.game_types import UnitState, UnitType, RenderLayer


class UnitRenderSystem(System):
    """单位渲染系统，负责渲染单位"""

    def __init__(self, priority: int = 40):
        """初始化单位渲染系统"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("UnitRenderSystem")
        self.unit_colors = {
            UnitType.INFANTRY: (0, 0, 255),  # 蓝色
            UnitType.CAVALRY: (0, 255, 0),  # 绿色
            UnitType.ARCHER: (255, 255, 0),  # 黄色
            UnitType.SIEGE: (128, 0, 128),  # 紫色
            UnitType.HERO: (255, 215, 0),  # 金色
        }
        self.state_indicators = {
            UnitState.IDLE: None,
            UnitState.MOVING: (0, 255, 255),  # 青色
            UnitState.ATTACKING: (255, 0, 0),  # 红色
            UnitState.DEFENDING: (0, 128, 255),  # 浅蓝色
            UnitState.DEAD: (128, 128, 128),  # 灰色
        }
        self.owner_colors = {
            0: (0, 0, 255),  # 玩家0 - 蓝色
            1: (255, 0, 0),  # 玩家1 - 红色
            2: (0, 255, 0),  # 玩家2 - 绿色
            3: (255, 255, 0),  # 玩家3 - 黄色
        }
        self.font = None
        self.tile_size = 32  # 默认格子大小
        self.unit_cache = {}  # 缓存渲染过的单位，提高性能

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("单位渲染系统初始化")

        # 初始化字体
        pygame.font.init()
        self.font = pygame.font.SysFont(None, 14)  # 使用默认字体，大小为14

        # 初始化选择框相关属性
        self.selection_box = None  # 当前选择框，格式为 (start_x, start_y, end_x, end_y)

        # 订阅选择框更新事件
        self.subscribe_events()

        self.logger.info("单位渲染系统初始化完成")

    def subscribe_events(self):
        """订阅事件"""
        if self.context and self.context.event_manager:
            self.context.event_manager.subscribe(
                [
                    EventType.SELECTION_BOX_RENDERING,
                    EventType.SELECTION_BOX_COMPLETED,
                    EventType.SELECTION_BOX_CANCELED,
                ],
                self._handle_selection_box_event,
            )
            self.logger.debug("已订阅自定义事件")

    def _handle_selection_box_event(self, event: EventMessage):
        """处理自定义事件"""
        # 直接使用event.type而不是event.data.get("type")

        # 处理选择框更新事件
        if event.type == EventType.SELECTION_BOX_RENDERING:
            start = event.data.get("start")
            end = event.data.get("end")
            if start and end:
                self.selection_box = (start[0], start[1], end[0], end[1])
                self.logger.debug(f"选择框更新: 从 {start} 到 {end}")
            else:
                self.selection_box = None
        # 处理选择框完成或取消事件
        elif (
            event.type == EventType.SELECTION_BOX_COMPLETED
            or event.type == EventType.SELECTION_BOX_CANCELED
        ):
            self.clear_selection_box()
            self.logger.debug(f"选择框已{event.type.name}")

    def clear_selection_box(self):
        """清除选择框"""
        self.selection_box = None

    # def _on_component_changed(self, event: EventMessage):
    #     """处理组件改变事件，例如相机移动或者缩放"""
    #     # 当相机变化时，清空单位缓存以确保正确渲染
    #     component_data = event.data.get("component")
    #     if component_data and isinstance(component_data, CameraComponent):
    #         self.unit_cache.clear()
    #         self.logger.debug("相机变化，清空单位缓存")

    def _get_camera_component(self) -> Optional[CameraComponent]:
        """获取相机组件，不直接引用相机系统"""
        camera_entity = self.context.with_all(CameraComponent).first()
        if not camera_entity:
            return None
        self.logger.debug(f"找到相机实体: {camera_entity}")
        # 从实体中获取相机组件
        camera_component = self.context.get_component(camera_entity, CameraComponent)
        return camera_component

    def _get_visible_area(
        self, camera_comp: CameraComponent
    ) -> Tuple[float, float, float, float]:
        """获取当前相机可见区域的世界坐标"""
        half_width = camera_comp.width / (2 * camera_comp.zoom)
        half_height = camera_comp.height / (2 * camera_comp.zoom)

        left = camera_comp.x - half_width
        top = camera_comp.y - half_height
        right = camera_comp.x + half_width
        bottom = camera_comp.y + half_height

        return left, top, right, bottom

    def update(self, delta_time: float):
        """更新单位渲染系统"""
        if not self.is_enabled():
            return

        # 获取相机组件
        camera_component = self._get_camera_component()
        if not camera_component:
            self.logger.warning("未找到相机组件，无法准备单位渲染数据")
            return
        self.render_unit(camera_component)

    def render_unit(self, camera_comp: CameraComponent):
        """渲染所有单位"""
        # 获取可见区域
        visible_area = self._get_visible_area(camera_comp)
        left, top, right, bottom = visible_area
        self.context.render_manager.set_layer(RenderLayer.UNIT)
        # 获取所有单位组件
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            # 准备单位渲染数据
            self._prepare_unit_render_data(unit, camera_comp)

        # 渲染选择框（如果存在）
        self._render_selection_box()

    def _render_unit_surface(self, unit: UnitComponent, size: int) -> pygame.Surface:
        """渲染单个单位的表面，用于缓存"""
        # 创建单位表面
        unit_surface = pygame.Surface((size, size), pygame.SRCALPHA)

        # 确定单位颜色（基于所有者）
        unit_color = self.owner_colors.get(unit.owner_id, (200, 200, 200))  # 默认为灰色

        # 如果单位已死亡，使用灰色
        if unit.state == UnitState.DEAD:
            unit_color = (128, 128, 128)  # 灰色

        # 绘制单位主体
        unit_rect = pygame.Rect(0, 0, size, size)
        pygame.draw.rect(unit_surface, unit_color, unit_rect)

        # 绘制单位类型标识
        type_indicator = self._get_unit_type_indicator(unit.unit_type)
        if type_indicator:
            pygame.draw.rect(
                unit_surface,
                type_indicator,
                (
                    size // 4,
                    size // 4,
                    size // 2,
                    size // 2,
                ),
            )

        # 绘制单位状态指示器
        state_color = self.state_indicators.get(unit.state)
        if state_color:
            pygame.draw.circle(
                unit_surface,
                state_color,
                (size * 2 // 3, size // 3),
                max(2, size // 6),
            )

        # 绘制生命值条
        health_ratio = unit.current_health / unit.max_health
        health_width = int(size * health_ratio)
        health_rect = pygame.Rect(0, size - 4, size, 4)
        health_fill_rect = pygame.Rect(0, size - 4, health_width, 4)
        pygame.draw.rect(unit_surface, (64, 64, 64), health_rect)  # 背景
        health_color = self._get_health_color(health_ratio)
        pygame.draw.rect(unit_surface, health_color, health_fill_rect)  # 血条

        # 绘制单位名称或等级
        text = f"{unit.name[:1]}{unit.level}"  # 名称首字母+等级
        text_surface = self.font.render(text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(size // 2, size // 2))
        unit_surface.blit(text_surface, text_rect)

        return unit_surface

    def _prepare_unit_render_data(
        self, unit: UnitComponent, camera_comp: CameraComponent
    ):
        """准备单个单位的渲染数据"""
        # 计算单位在屏幕上的位置和尺寸（支持浮点坐标和实际尺寸）
        # 单位实际尺寸（米）根据相机缩放和tile_size换算为像素
        unit_pixel_size = max(20, int(unit.unit_size * camera_comp.zoom))

        # 创建缓存键
        cache_key = (
            unit.unit_type,
            unit.state,
            unit.owner_id,
            unit_pixel_size,
            int(
                unit.current_health / unit.max_health * 10
            ),  # 将血量比例离散化为10个等级
            unit.level,
            unit.name[:1],  # 名称首字母
        )

        # 检查缓存
        if cache_key not in self.unit_cache:
            self.unit_cache[cache_key] = self._render_unit_surface(
                unit, unit_pixel_size
            )

        # 获取单位表面
        unit_surface = self.unit_cache[cache_key]

        # 将单位的世界坐标转换为屏幕坐标
        screen_x, screen_y = self._world_to_screen(
            unit.position_x, unit.position_y, camera_comp
        )

        # 计算绘制位置（居中）
        draw_pos = (screen_x - unit_pixel_size // 2, screen_y - unit_pixel_size // 2)

        # 添加单位渲染数据到相机渲染系统
        # 使用单位的y坐标作为z_index，使靠下的单位显示在上层（模拟透视效果）
        self.context.render_manager.draw_surface(
            unit_surface,
            draw_pos,
            RenderLayer.UNIT.value,
        )

        # 如果单位被选中，添加选中指示器
        if unit.is_selected:
            # 创建选中指示器表面
            select_surface = pygame.Surface(
                (unit_pixel_size + 4, unit_pixel_size + 4), pygame.SRCALPHA
            )
            select_rect = pygame.Rect(0, 0, unit_pixel_size + 4, unit_pixel_size + 4)
            pygame.draw.rect(
                select_surface, (255, 255, 255), select_rect, 2
            )  # 白色边框

            # 添加选中指示器渲染数据
            self.context.render_manager.draw_surface(
                select_surface,
                (draw_pos[0] - 2, draw_pos[1] - 2),
                RenderLayer.UNIT_EFFECT.value,
            )

    # def _render_unit(
    #     self,
    #     screen: Optional[pygame.Surface],
    #     unit: UnitComponent,
    #     camera_comp: CameraComponent,
    # ):
    #     """渲染单个单位（保留用于兼容旧代码）"""
    #     # 计算单位在屏幕上的位置和尺寸（支持浮点坐标和实际尺寸）
    #     screen_x, screen_y = self._world_to_screen(
    #         unit.position_x, unit.position_y, camera_comp
    #     )
    #     # 单位实际尺寸（米）根据相机缩放和tile_size换算为像素
    #     unit_pixel_size = max(2, int(unit.unit_size * camera_comp.zoom))

    #     # 创建缓存键
    #     cache_key = (
    #         unit.unit_type,
    #         unit.state,
    #         unit.owner_id,
    #         unit_pixel_size,
    #         int(
    #             unit.current_health / unit.max_health * 10
    #         ),  # 将血量比例离散化为10个等级
    #         unit.level,
    #         unit.name[:1],  # 名称首字母
    #     )

    #     # 检查缓存
    #     if cache_key not in self.unit_cache:
    #         self.unit_cache[cache_key] = self._render_unit_surface(
    #             unit, unit_pixel_size
    #         )

    #     # 获取单位表面
    #     unit_surface = self.unit_cache[cache_key]

    #     # 计算绘制位置（居中）
    #     draw_pos = (screen_x - unit_pixel_size // 2, screen_y - unit_pixel_size // 2)

    #     # 使用渲染管理器绘制单位
    #     if self.context.render_manager:
    #         # 创建目标矩形
    #         dest_rect = pygame.Rect(
    #             draw_pos[0], draw_pos[1], unit_pixel_size, unit_pixel_size
    #         )
    #         # 通过渲染管理器绘制
    #         self.context.render_manager.draw(unit_surface, dest_rect)

    #         # 如果单位被选中，绘制选中指示器（这个不缓存，因为选中状态经常变化）
    #         if unit.is_selected:
    #             # 创建选中指示器表面
    #             select_surface = pygame.Surface(
    #                 (unit_pixel_size + 4, unit_pixel_size + 4), pygame.SRCALPHA
    #             )
    #             select_rect = pygame.Rect(
    #                 0, 0, unit_pixel_size + 4, unit_pixel_size + 4
    #             )
    #             pygame.draw.rect(
    #                 select_surface, (255, 255, 255), select_rect, 2
    #             )  # 白色边框

    #             # 通过渲染管理器绘制选中指示器
    #             select_dest = pygame.Rect(
    #                 screen_x - unit_pixel_size // 2 - 2,
    #                 screen_y - unit_pixel_size // 2 - 2,
    #                 unit_pixel_size + 4,
    #                 unit_pixel_size + 4,
    #             )
    #             self.context.render_manager.draw(select_surface, select_dest)
    #     else:
    #         # 如果没有渲染管理器，则直接在屏幕上绘制（兼容旧代码）
    #         screen.blit(unit_surface, draw_pos)

    #         # 如果单位被选中，绘制选中指示器
    #         if unit.is_selected:
    #             select_rect = pygame.Rect(
    #                 screen_x - unit_pixel_size // 2 - 2,
    #                 screen_y - unit_pixel_size // 2 - 2,
    #                 unit_pixel_size + 4,
    #                 unit_pixel_size + 4,
    #             )
    #             pygame.draw.rect(screen, (255, 255, 255), select_rect, 2)  # 白色边框

    def _world_to_screen(
        self, world_x: float, world_y: float, camera_comp: CameraComponent
    ) -> Tuple[int, int]:
        """将世界坐标（米）转换为屏幕坐标"""
        if not camera_comp:
            return (0, 0)
        # 计算相对于相机的偏移
        screen_x = int(
            (world_x - camera_comp.x) * camera_comp.zoom + camera_comp.width / 2
        )
        screen_y = int(
            (world_y - camera_comp.y) * camera_comp.zoom + camera_comp.height / 2
        )
        return (screen_x, screen_y)

    def _get_unit_type_indicator(self, unit_type: UnitType) -> Tuple[int, int, int]:
        """获取单位类型的颜色指示器"""
        return self.unit_colors.get(unit_type)

    def _get_health_color(self, health_ratio: float) -> Tuple[int, int, int]:
        """根据生命值比例获取血条颜色"""
        if health_ratio > 0.7:
            return (0, 255, 0)  # 绿色
        elif health_ratio > 0.3:
            return (255, 255, 0)  # 黄色
        else:
            return (255, 0, 0)  # 红色

    def _render_selection_box(
        self,
    ):
        """渲染选择框"""
        if not self.selection_box:
            return

        # 获取选择框坐标
        start_x, start_y, end_x, end_y = self.selection_box

        # 确保start是左上角，end是右下角
        left = min(start_x, end_x)
        top = min(start_y, end_y)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)

        # 如果选择框太小，不渲染
        if width < 5 or height < 5:
            return

        # 创建选择框表面
        selection_surface = pygame.Surface((width, height), pygame.SRCALPHA)

        # 绘制半透明填充
        pygame.draw.rect(selection_surface, (100, 100, 255, 50), (0, 0, width, height))

        # 绘制边框
        pygame.draw.rect(
            selection_surface, (100, 100, 255, 200), (0, 0, width, height), 2
        )

        # 设置渲染层为UI层，确保选择框显示在单位上方
        # self.context.render_manager.set_layer(RenderLayer.UI)

        # 渲染选择框
        self.context.render_manager.draw_surface(
            selection_surface, (left, top), RenderLayer.UI.value
        )

        self.logger.debug(f"渲染选择框: 位置=({left}, {top}), 尺寸=({width}, {height})")

    # def set_tile_size(self, tile_size: int):
    #     """设置格子大小"""
    #     self.tile_size = tile_size
