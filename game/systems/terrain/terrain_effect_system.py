from typing import Dict, List, Tuple, Any
import numpy as np

from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger

from game.components import (
    MapComponent,
    TileComponent,
    UnitComponent,
    TerrainType,
)
from game.components.unit.unit_effect_component import UnitEffectComponent
from game.utils.game_types import UnitState
from game.utils.hex_utils import HexCoordinate, pixel_to_hex, hex_neighbors


class TerrainEffectSystem(System):
    """地形效果系统，支持六边形和方形地图"""

    def __init__(self, priority: int = 15):
        super().__init__(
            required_components=[],
            priority=priority,
        )
        self.logger = get_logger("TerrainEffectSystem")
        self.terrain_effects = {
            TerrainType.RIVER: self._apply_water_effect,
            TerrainType.MOUNTAIN: self._apply_mountain_effect,
            TerrainType.FOREST: self._apply_forest_effect,
            TerrainType.PLAIN: self._apply_plain_effect,
        }
        # 用于跟踪单位上一次所在的地形
        self.unit_last_terrain = {}

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("地形效果系统初始化")

    def update(self, delta_time):
        """更新地形效果"""
        # 获取地图
        map_component = self._get_map()
        if not map_component:
            return

        # 获取所有有单位效果组件的实体
        for unit_entity, (unit_component,) in self.context.with_all(
            UnitComponent  # , UnitEffectComponent]
        ).iter_components(
            UnitComponent
        ):  # , UnitEffectComponent):
            # unit_component = self.context.get_component(unit_entity, UnitComponent)
            # unit_effect = self.context.get_component(unit_entity, UnitEffectComponent)

            # 获取单位当前位置的地形
            tile_entity, tile_component = self._get_tile_at_position(
                map_component, unit_component.position_x, unit_component.position_y
            )

            if not self.context.get_component(unit_entity, UnitEffectComponent):
                # 如果没有单位效果组件，则添加一个
                self.context.add_component(unit_entity, UnitEffectComponent())

            unit_effect = self.context.get_component(unit_entity, UnitEffectComponent)

            if tile_component:
                # 检查地形效果变化
                current_terrain_type = tile_component.terrain_type
                current_near_water = self._is_near_water(
                    map_component, unit_component.position_x, unit_component.position_y
                )
                current_in_city = self._is_in_city(tile_component)

                # 获取上一次的地形信息
                last_terrain_info = self.unit_last_terrain.get(unit_entity, {})
                last_terrain_type = last_terrain_info.get("terrain_type")
                last_near_water = last_terrain_info.get("near_water", False)
                last_in_city = last_terrain_info.get("in_city", False)

                # 检查地形是否发生变化，移除旧地形效果
                self._remove_terrain_effects(
                    unit_entity,
                    unit_effect,
                    last_terrain_type,
                    last_near_water,
                    last_in_city,
                    current_terrain_type,
                    current_near_water,
                    current_in_city,
                )

                # 应用当前地形效果
                if current_terrain_type in self.terrain_effects:
                    self.terrain_effects[current_terrain_type](
                        unit_entity,
                        unit_component,
                        unit_effect,
                        tile_entity,
                        tile_component,
                    )

                # 检查是否在水边
                if current_near_water:
                    self._apply_waterside_effect(
                        unit_entity,
                        unit_component,
                        unit_effect,
                        tile_entity,
                        tile_component,
                    )

                # 检查是否在城市
                if current_in_city:
                    self._apply_city_effect(
                        unit_entity,
                        unit_component,
                        unit_effect,
                        tile_entity,
                        tile_component,
                    )

                # 更新单位的地形信息
                self.unit_last_terrain[unit_entity] = {
                    "terrain_type": current_terrain_type,
                    "near_water": current_near_water,
                    "in_city": current_in_city,
                }

    def _get_map(self):
        """获取地图组件"""
        map_entity = self.context.with_all(MapComponent).first()
        return (
            self.context.get_component(map_entity, MapComponent) if map_entity else None
        )

    def _get_tile_at_position(
        self, map_component: MapComponent, x: float, y: float
    ) -> Tuple[Entity, TileComponent]:
        """获取指定位置的地形格子"""
        if map_component.map_type == "hexagonal":
            # 六边形地图
            hex_coord = pixel_to_hex(
                x, y, map_component.hex_size, map_component.orientation
            )
            hex_tuple = hex_coord.to_tuple()
            tile_entity = map_component.hex_entities.get(hex_tuple)
        else:
            # 方形地图
            grid_x = int(x // map_component.tile_size)
            grid_y = int(y // map_component.tile_size)
            tile_entity = map_component.tile_entities.get((grid_x, grid_y))

        if tile_entity:
            tile_component = self.context.get_component(tile_entity, TileComponent)
            return tile_entity, tile_component
        return None, None

    def _is_near_water(self, map_component: MapComponent, x: float, y: float) -> bool:
        """检查是否靠近水域"""
        if map_component.map_type == "hexagonal":
            # 六边形地图：检查邻近的六边形
            center_hex = pixel_to_hex(
                x, y, map_component.hex_size, map_component.orientation
            )
            neighbors = hex_neighbors(center_hex)

            for neighbor in neighbors:
                neighbor_tuple = neighbor.to_tuple()
                if neighbor_tuple in map_component.hex_entities:
                    tile_entity = map_component.hex_entities[neighbor_tuple]
                    tile_component = self.context.get_component(
                        tile_entity, TileComponent
                    )
                    if tile_component and tile_component.terrain_type in [
                        TerrainType.RIVER,
                        TerrainType.LAKE,
                        TerrainType.OCEAN,
                    ]:
                        return True
        else:
            # 方形地图：检查周围8个格子
            grid_x = int(x // map_component.tile_size)
            grid_y = int(y // map_component.tile_size)

            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    check_pos = (grid_x + dx, grid_y + dy)
                    if check_pos in map_component.tile_entities:
                        tile_entity = map_component.tile_entities[check_pos]
                        tile_component = self.context.get_component(
                            tile_entity, TileComponent
                        )
                        if tile_component and tile_component.terrain_type in [
                            TerrainType.RIVER,
                            TerrainType.LAKE,
                            TerrainType.OCEAN,
                        ]:
                            return True
        return False

    def _is_in_city(self, tile_component: TileComponent) -> bool:
        """检查是否在城市

        Args:
            tile_component: 地形组件

        Returns:
            是否在城市
        """
        # 目前没有城市地形类型，暂时返回False
        # 后续可以在TileComponent中添加is_city属性
        return False

    def _remove_terrain_effects(
        self,
        unit_entity: Entity,
        unit_effect: UnitEffectComponent,
        last_terrain_type,
        last_near_water: bool,
        last_in_city: bool,
        current_terrain_type,
        current_near_water: bool,
        current_in_city: bool,
    ):
        """移除不再适用的地形效果

        当单位从一个地形移动到另一个地形时，需要移除旧地形的效果

        Args:
            unit_entity: 单位实体
            unit_effect: 单位效果组件
            last_terrain_type: 上一次的地形类型
            last_near_water: 上一次是否在水边
            last_in_city: 上一次是否在城市
            current_terrain_type: 当前地形类型
            current_near_water: 当前是否在水边
            current_in_city: 当前是否在城市
        """
        # 如果是第一次更新，没有上一次的地形信息，则不需要移除效果
        if last_terrain_type is None:
            return

        # 检查地形类型是否变化
        if last_terrain_type != current_terrain_type:
            # 移除旧地形效果
            if last_terrain_type == TerrainType.RIVER:
                unit_effect.remove_effect("terrain_water")
            elif last_terrain_type == TerrainType.MOUNTAIN:
                unit_effect.remove_effect("terrain_mountain")
            elif last_terrain_type == TerrainType.FOREST:
                unit_effect.remove_effect("terrain_forest")
            elif last_terrain_type == TerrainType.PLAIN:
                unit_effect.remove_effect("terrain_plain")

        # 检查水边状态是否变化
        if last_near_water and not current_near_water:
            unit_effect.remove_effect("terrain_waterside")

        # 检查城市状态是否变化
        if last_in_city and not current_in_city:
            unit_effect.remove_effect("terrain_city")

        self.logger.debug(f"单位 {unit_entity} 地形变化，移除旧地形效果")

    def _apply_water_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用水域效果：减少生命值，移速降低"""
        effect_id = "terrain_water"
        effect_data = {
            "health_reduction": -1,  # 每回合减少1点生命值
            "movement_speed_modifier": 0.5,  # 移动速度降低50%
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开水域
            description="水域：减少生命值，移速降低",
        )

    def _apply_waterside_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用水边效果：静止恢复体力"""
        effect_id = "terrain_waterside"

        # 只有单位静止时才应用效果
        if unit_component.state is not UnitState.IDLE:
            if unit_effect.has_effect(effect_id):
                unit_effect.remove_effect(effect_id)
            return

        effect_data = {
            "stamina_recovery": 2,  # 每回合恢复2点体力
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开水边或开始移动
            description="水边：静止恢复体力",
        )

    def _apply_mountain_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用山地效果：骑兵移速速度降为最低，静止时隐蔽，对非山地地形攻击加成"""
        effect_id = "terrain_mountain"

        effect_data = {
            "cavalry_speed_reduced": True,  # 骑兵移速降低
            "is_concealed": unit_component.state is UnitState.IDLE,  # 静止时隐蔽
            "attack_bonus_to_non_mountain": 1.2,  # 对非山地地形攻击加成20%
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开山地
            description="山地：骑兵移速降低，静止时隐蔽，对非山地地形攻击加成",
        )

    def _apply_forest_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用森林效果：静止时可以隐蔽"""
        effect_id = "terrain_forest"

        # 只有单位静止时才应用隐蔽效果
        effect_data = {
            "is_concealed": unit_component.state is UnitState.IDLE,  # 静止时隐蔽
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开森林
            description="森林：静止时可以隐蔽",
        )

    def _apply_plain_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用平原效果：骑兵加速"""
        effect_id = "terrain_plain"

        # 只对骑兵单位应用效果
        if unit_component.unit_type.name == "CAVALRY":
            effect_data = {
                "movement_speed_modifier": 1.3,  # 移动速度提高30%
            }

            # 添加或更新效果
            unit_effect.add_effect(
                effect_id=effect_id,
                source=tile_entity,
                data=effect_data,
                duration=-1,  # 永久效果，直到离开平原
                description="平原：骑兵移动速度提高",
            )
        elif unit_effect.has_effect(effect_id):
            # 如果不是骑兵但有平原效果，则移除
            unit_effect.remove_effect(effect_id)

    def _apply_city_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用城市效果：占领后范围内攻击力增加，同时只能由一个阵营占领生效"""
        effect_id = "terrain_city"

        # 检查是否已被占领
        # 这里需要一个机制来跟踪城市的占领状态
        # 暂时简化处理，假设单位停留在城市上一段时间后自动占领

        # 只有单位静止时才应用占领效果
        if unit_component.is_moving:
            if unit_effect.has_effect(effect_id):
                unit_effect.remove_effect(effect_id)
            return

        # 假设单位已占领城市
        effect_data = {
            "attack_bonus": 1.2,  # 攻击力提高20%
            "occupied_by_faction": unit_component.faction,  # 记录占领阵营
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开城市或被其他阵营占领
            description="城市：占领后攻击力提高",
        )

    def _apply_city_effect(
        self,
        unit_entity: Entity,
        unit_component: UnitComponent,
        unit_effect: UnitEffectComponent,
        tile_entity: Entity,
        tile_component: TileComponent,
    ):
        """应用城市效果：占领后范围内攻击力增加，同时只能由一个阵营占领生效"""
        effect_id = "terrain_city"

        # 检查是否已被占领
        # 这里需要一个机制来跟踪城市的占领状态
        # 暂时简化处理，假设单位停留在城市上一段时间后自动占领

        # 只有单位静止时才应用占领效果
        if unit_component.is_moving:
            if unit_effect.has_effect(effect_id):
                unit_effect.remove_effect(effect_id)
            return

        # 假设单位已占领城市
        effect_data = {
            "attack_bonus": 1.2,  # 攻击力提高20%
            "occupied_by_faction": unit_component.faction,  # 记录占领阵营
        }

        # 添加或更新效果
        unit_effect.add_effect(
            effect_id=effect_id,
            source=tile_entity,
            data=effect_data,
            duration=-1,  # 永久效果，直到离开城市或被其他阵营占领
            description="城市：占领后攻击力提高",
        )
