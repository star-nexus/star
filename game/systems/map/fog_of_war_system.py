import pygame
import numpy as np
from typing import Dict, Tuple, List, Optional, Set
from framework.ecs.system import System
from framework.utils.logging import get_logger
from framework.engine.events import EventMessage, EventType
from game.components import UnitComponent, UnitState
from game.components import MapComponent
from game.components import TileComponent
from game.components import CameraComponent
from game.components import FogOfWarComponent
from game.utils.game_types import RenderLayer, ViewMode


class FogOfWarSystem(System):
    """战争迷雾系统，负责计算和渲染战争迷雾

    功能：
    1. 计算每个玩家的可见区域
    2. 根据当前视角模式（全局/玩家）渲染战争迷雾
    3. 响应玩家切换和迷雾开关事件
    """

    def __init__(self, priority: int = 35):  # 在地图渲染之后，单位渲染之前
        """初始化战争迷雾系统"""
        super().__init__(
            required_components=[MapComponent, FogOfWarComponent], priority=priority
        )
        self.logger = get_logger("FogOfWarSystem")

        # 地图和相机引用
        # self.map_entity = None
        # self.map_component = None
        # self.camera_component = None

        # # 战争迷雾组件引用
        # self.fog_of_war_entity = None
        # self.fog_of_war_component = None

        # 渲染相关
        self.fog_surface = None  # 迷雾渲染表面

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("战争迷雾系统初始化")

        # 查找地图实体和组件
        # for entity in self.context.entity_manager.get_all_entity():
        #     if self.context.component_manager.has_component(entity, MapComponent):
        #         self.map_entity = entity
        #         self.map_component = self.context.get_component(entity, MapComponent)
        #         self.logger.debug(f"找到地图实体: {self.map_entity}")
        #         break
        map_entity = self.context.with_all(MapComponent).first()
        map_component = self.context.get_component(map_entity, MapComponent)
        if not map_component:
            self.logger.error("未找到地图实体")
            return

        # 查找或创建战争迷雾组件
        fog_of_war_entity = self.context.with_all(FogOfWarComponent).first()
        if fog_of_war_entity:
            fog_of_war_component = self.context.get_component(
                fog_of_war_entity, FogOfWarComponent
            )
            self.logger.debug(f"找到战争迷雾实体: {fog_of_war_entity}")
        else:
            # 使用组件工厂创建战争迷雾组件
            from game.prefab.prefab_factory import PrefabFactory

            prefab_factory = PrefabFactory(self.context)
            fog_of_war_entity, fog_of_war_component = prefab_factory.create_fog_of_war(
                "default", map_component.width, map_component.height
            )
            self.logger.debug(f"创建战争迷雾实体: {fog_of_war_entity}")

        # 订阅事件
        self.subscribe_events()

        self.logger.info("战争迷雾系统初始化完成")

    # 已移至PrefabFactory中的_init_visibility_maps方法

    def subscribe_events(self):
        """订阅事件"""
        if self.context and self.context.event_manager:
            # 订阅玩家切换事件
            self.context.event_manager.subscribe(
                [EventType.PLAYER_SWITCHED, EventType.FOG_OF_WAR_TOGGLED],
                self._handle_fog_event,
            )
            self.logger.debug("已订阅单位和迷雾相关事件")

    # def _handle_unit_event(self, event: EventMessage):
    #     """处理单位相关事件，更新可见性地图"""
    #     # 更新所有单位的可见性
    #     self.update_visibility_maps()

    def _handle_fog_event(self, event: EventMessage):
        """处理迷雾相关事件"""
        # 强制重新渲染迷雾
        self.fog_surface = None

    def update_visibility_maps(self, fog: FogOfWarComponent):
        """更新所有玩家的可见性地图"""

        # 重置所有玩家的可见性地图（但保留已探索地图）
        for player_id in fog.visibility_map:
            fog.visibility_map[player_id].fill(0)

        # 遍历所有单位，更新其视野范围内的可见性
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            if not unit or unit.state == UnitState.DEAD:
                continue

            # 获取单位所属玩家和位置
            player_id = unit.owner_id
            unit_x, unit_y = int(unit.position_x), int(unit.position_y)

            # 获取单位视野范围
            vision_range = fog.unit_vision_range.get(unit.unit_type.name, 3)

            # 更新可见性和已探索地图
            self.update_unit_visibility(fog, player_id, unit_x, unit_y, vision_range)

    def update_unit_visibility(
        self,
        fog: FogOfWarComponent,
        player_id: int,
        unit_x: int,
        unit_y: int,
        vision_range: int,
    ):
        """更新单个单位的可见性范围

        Args:
            player_id: 玩家ID
            unit_x: 单位X坐标
            unit_y: 单位Y坐标
            vision_range: 视野范围
        """
        if player_id not in fog.visibility_map or player_id not in fog.explored_map:
            return

        height, width = fog.visibility_map[player_id].shape

        # 计算视野范围（简单的圆形视野）
        for y in range(
            max(0, unit_y - vision_range), min(height, unit_y + vision_range + 1)
        ):
            for x in range(
                max(0, unit_x - vision_range), min(width, unit_x + vision_range + 1)
            ):
                # 计算到单位的距离
                distance = ((x - unit_x) ** 2 + (y - unit_y) ** 2) ** 0.5

                # 如果在视野范围内
                if distance <= vision_range:
                    # 设置为可见
                    fog.visibility_map[player_id][y, x] = 1
                    # 标记为已探索
                    fog.explored_map[player_id][y, x] = 1

    def update(self, delta_time: float):
        """更新系统逻辑"""
        if not self.is_enabled():
            return

        fog_entity = self.context.with_all(FogOfWarComponent).first()
        if not fog_entity:
            return
        fog = self.context.get_component(fog_entity, FogOfWarComponent)
        if not fog:
            return
        # 如果战争迷雾被禁用，不进行更新
        # if not fog.fog_of_war_enabled:
        #     return

        # 每隔一段时间更新可见性地图（性能优化）
        if not hasattr(self, "_visibility_update_timer"):
            self._visibility_update_timer = 0

        self._visibility_update_timer += delta_time
        if self._visibility_update_timer >= 0.5:  # 每0.5秒更新一次
            self._visibility_update_timer = 0
            self.update_visibility_maps(fog)
