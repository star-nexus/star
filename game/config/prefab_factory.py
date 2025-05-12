from typing import Dict, Any, Tuple, Optional
from framework.ecs.entity import Entity
from framework.ecs.world import World

from game.components import (
    MapComponent,
    TileComponent,
    UnitComponent,
    CameraComponent,
    FogOfWarComponent,
    BattleStatsComponent,
    TerrainType,
    UnitState,
    UnitType,
)
from game.config.prefab.map_config import (
    get_map_config,
    get_terrain_properties,
    get_map_generation_config,
)
from game.config.prefab.unit_config import (
    get_unit_config,
    get_faction_config,
    create_unit_config,
)

from game.config.prefab.camera_config import get_camera_config
from game.config.prefab.fog_of_war_config import get_fog_of_war_config
from game.utils.map_generator import MapGenerator
from game.utils.game_types import ViewMode


class PrefabFactory:
    """组件工厂类，负责根据配置创建和初始化各种组件"""

    def __init__(self, world: World):
        self.world = world

    def create_map(
        self, config_name: str = "default", seed: int = None
    ) -> Tuple[Entity, MapComponent]:
        """创建地图实体和组件

        Args:
            config_name: 地图配置名称
            seed: 可选的随机种子，如果提供则使用此种子生成地图，否则使用配置中的种子
        """
        # 获取地图配置
        map_config = get_map_config(config_name)
        map_gen_config = get_map_generation_config(config_name)

        # 如果提供了种子，则使用提供的种子
        if seed is not None:
            map_gen_config["seed"] = seed

        # 创建地图实体
        map_entity = self.world.create_entity()

        # 创建地图组件
        map_component = MapComponent(
            width=map_config["width"],
            height=map_config["height"],
            tile_size=map_config["tile_size"],
        )

        # 添加组件到实体
        self.world.add_component(map_entity, map_component)

        # 使用地图生成器生成地形
        map_generator = MapGenerator(
            map_config["width"], map_config["height"], map_gen_config["seed"]
        )
        elevation, terrain, moisture = map_generator.generate_map()

        # 存储地图数据
        map_component.elevation_map = elevation
        map_component.terrain_map = terrain
        map_component.moisture_map = moisture

        # 生成地图格子实体
        self._generate_tile_entities(map_entity, map_component, terrain)

        return map_entity, map_component

    def _generate_tile_entities(
        self, map_entity: Entity, map_component: MapComponent, terrain_map
    ):
        """为每个地图格子生成实体"""
        for y in range(map_component.height):
            for x in range(map_component.width):
                # 创建格子实体
                tile_entity = self.world.create_entity()

                # 获取地形类型和属性
                terrain_type = TerrainType(terrain_map[y, x])
                terrain_props = get_terrain_properties(terrain_type.value)

                # 创建格子组件
                tile_component = TileComponent(
                    terrain_type=terrain_type,
                    elevation=map_component.elevation_map[y, x],  # 添加海拔数据
                    moisture=map_component.moisture_map[y, x],
                    movement_cost=terrain_props["movement_cost"],
                    defense_bonus=terrain_props["defense_bonus"],
                    x=x,
                    y=y,
                    visible=True,
                    explored=False,
                )

                # 添加组件到实体
                self.world.add_component(tile_entity, tile_component)

                # 记录格子实体
                map_component.tile_entities[(x, y)] = tile_entity

    def create_unit(
        self,
        unit_type: UnitType,
        faction: int,
        x: int,
        y: int,
        level: int = 1,
        **kwargs,
    ) -> Tuple[Entity, UnitComponent]:
        """创建单位实体和组件"""
        # 获取单位配置
        unit_config = create_unit_config(unit_type, faction, level, **kwargs)

        # 创建单位实体
        unit_entity = self.world.create_entity()

        # 设置位置
        unit_config["position_x"] = float(x)
        unit_config["position_y"] = float(y)

        # 创建单位组件
        unit_component = UnitComponent(**unit_config)

        # 添加组件到实体
        self.world.add_component(unit_entity, unit_component)

        return unit_entity, unit_component

    def create_predefined_unit(
        self, unit_id: str, x: int, y: int
    ) -> Optional[Tuple[Entity, UnitComponent]]:
        """创建预定义的单位"""
        from game.config.prefab.unit_config import get_predefined_unit

        # 获取预定义单位配置
        unit_config = get_predefined_unit(unit_id)
        if not unit_config:
            return None

        # 创建单位
        return self.create_unit(
            unit_config["unit_type"], unit_config["faction"], x, y, unit_config["level"]
        )

    def create_camera(
        self, config_name: str = "default"
    ) -> Tuple[Entity, CameraComponent]:
        """创建相机实体和组件"""
        # 获取相机配置
        camera_config = get_camera_config(config_name)

        # 创建相机实体
        camera_entity = self.world.create_entity()

        # 创建相机组件
        camera_component = CameraComponent(
            x=camera_config["position_x"],
            y=camera_config["position_y"],
            zoom=camera_config["zoom"],
            move_speed=camera_config["speed"],
            zoom_speed=camera_config["zoom_speed"],
            min_zoom=camera_config["min_zoom"],
            max_zoom=camera_config["max_zoom"],
        )

        # 添加组件到实体
        self.world.add_component(camera_entity, camera_component)

        return camera_entity, camera_component

    def create_fog_of_war(
        self, config_name: str = "default", map_width: int = 0, map_height: int = 0
    ) -> Tuple[Entity, FogOfWarComponent]:
        """创建战争迷雾实体和组件

        Args:
            config_name: 配置名称
            map_width: 地图宽度，用于初始化可见性地图
            map_height: 地图高度，用于初始化可见性地图

        Returns:
            战争迷雾实体和组件
        """
        # 获取战争迷雾配置
        fog_config = get_fog_of_war_config(config_name)

        # 创建战争迷雾实体
        fog_entity = self.world.create_entity()

        # 创建战争迷雾组件
        fog_component = FogOfWarComponent(
            # fog_of_war_enabled=fog_config["fog_of_war_enabled"],
            view_mode=ViewMode[fog_config["view_mode"]],
            current_player_id=fog_config["current_player_id"],
            unit_vision_range=fog_config["unit_vision_range"],
        )

        # 添加组件到实体
        self.world.add_component(fog_entity, fog_component)

        # 初始化可见性地图和已探索地图（如果提供了地图尺寸）
        if map_width > 0 and map_height > 0:
            self._init_visibility_maps(fog_component, map_width, map_height)

        return fog_entity, fog_component

    def create_battle_stats(self, faction):
        """创建战斗统计数据"""
        stats_entity = self.world.create_entity()

        # 创建战斗统计数据组件
        battle_stats_component = BattleStatsComponent(
            faction=faction,
            enemy_status_info={},
            enemy_transfer_situation={},
            # 作战任务 - 任务ID: 任务信息, 包括任务目标、任务进度等
            my_transfer_situation={},
            terrain_environment={},  # 地理环境信息
            contact_and_fire={},
            death_status={},
        )

        self.world.add_component(stats_entity, battle_stats_component)

    def _init_visibility_maps(self, fog: FogOfWarComponent, width: int, height: int):
        """初始化可见性地图和已探索地图

        Args:
            fog: 战争迷雾组件
            width: 地图宽度
            height: 地图高度
        """
        import numpy as np

        # 为4个玩家创建可见性地图和已探索地图
        for player_id in range(4):
            # 可见性地图：0表示不可见，1表示可见
            fog.visibility_map[player_id] = np.zeros((height, width), dtype=np.uint8)
            # 已探索地图：0表示未探索，1表示已探索
            fog.explored_map[player_id] = np.zeros((height, width), dtype=np.uint8)
