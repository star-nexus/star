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
from game.components.unit.unit_effect_component import UnitEffectComponent
from game.components.terrain_effect_component import TerrainEffectComponent

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
from game.utils.game_types import TerrainTypeMapping, ViewMode
from game.utils.hex_utils import HexCoordinate, create_hex_map_coordinates, hex_to_pixel

import random
import time
import numpy as np

# 使用当前时间作为随机种子，确保每次运行生成不同的随机序列
random.seed(int(time.time()))


class PrefabFactory:
    """组件工厂类，负责根据配置创建和初始化各种组件"""

    _instance = None

    @classmethod
    def instance(cls, world: World):
        if cls._instance is None:
            cls._instance = cls(world)
        return cls._instance

    def __init__(self, world: World):
        self.world = world

    def create_map(
        self, config_name: str = "default", seed: int = None, symmetric: bool = True
    ) -> Tuple[Entity, MapComponent]:
        """创建地图实体和组件

        Args:
            config_name: 地图配置名称
            seed: 可选的随机种子，如果提供则使用此种子生成地图，否则使用配置中的种子
            symmetric: 是否创建对称地图
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
            map_type=map_config.get("map_type", "hexagonal"),
            width=map_config["width"],
            height=map_config["height"],
            radius=map_config.get("radius", 3),
            hex_size=map_config.get("hex_size", 20.0),
            tile_size=map_config["tile_size"],
        )

        # 添加组件到实体
        self.world.add_component(map_entity, map_component)

        # 根据地图类型生成地形
        if map_component.map_type == "hexagonal":
            if symmetric:
                terrain_dict = self.create_symmetric_hex_terrain(map_component.radius)
                self._generate_hex_tile_entities(
                    map_entity, map_component, terrain_dict
                )
            else:
                map_generator = MapGenerator(
                    map_config["width"],
                    map_config["height"],
                    map_gen_config["seed"],
                    map_type="hexagonal",
                    radius=map_component.radius,
                )
                elevation, terrain, moisture = map_generator.generate_map()
                map_component.terrain_map = terrain
                # 从terrain数组生成六边形地图格子实体
                self._generate_hex_tile_entities_from_terrain(
                    map_entity, map_component, terrain
                )
        else:
            # 原有的方形地图逻辑
            if symmetric:
                terrain = self.create_symmetric_terrain(5, 5)
                elevation = np.zeros((5, 5), dtype=np.int32)
                moisture = np.zeros((5, 5), dtype=np.float32)
            else:
                map_generator = MapGenerator(
                    map_config["width"], map_config["height"], map_gen_config["seed"]
                )
                elevation, terrain, moisture = map_generator.generate_map()

            map_component.terrain_map = terrain
            # 生成方形地图格子实体
            self._generate_tile_entities(map_entity, map_component, terrain)

        print("terrain_map", map_component.terrain_map)
        print("map_entity", map_entity)

        return map_entity, map_component

    def create_symmetric_hex_terrain(
        self, radius: int
    ) -> Dict[Tuple[int, int, int], int]:
        """创建对称的六边形地形图"""
        hex_coords = create_hex_map_coordinates(radius)
        terrain_dict = {}

        # 初始化为平原
        for coord in hex_coords:
            terrain_dict[coord.to_tuple()] = TerrainType.PLAIN.value

        # 中心为湖泊
        center = HexCoordinate(0, 0, 0)
        terrain_dict[center.to_tuple()] = TerrainType.LAKE.value

        # 在特定位置放置山脉（对称）
        if radius >= 2:
            mountains = [
                HexCoordinate(2, -1, -1),  # 右上
                HexCoordinate(-1, 2, -1),  # 左下
                HexCoordinate(-1, -1, 2),  # 左上
            ]
            for mountain in mountains:
                if mountain.to_tuple() in terrain_dict:
                    terrain_dict[mountain.to_tuple()] = TerrainType.MOUNTAIN.value

        # 在特定位置放置森林
        if radius >= 2:
            forests = [
                HexCoordinate(1, 0, -1),  # 右
                HexCoordinate(-1, 0, 1),  # 左
                HexCoordinate(0, 1, -1),  # 右下
                HexCoordinate(0, -1, 1),  # 左上
            ]
            for forest in forests:
                if forest.to_tuple() in terrain_dict:
                    terrain_dict[forest.to_tuple()] = TerrainType.FOREST.value

        # 在边缘放置城市作为出生点
        if radius >= 3:
            cities = [
                HexCoordinate(radius, 0, -radius),  # 右边缘
                HexCoordinate(-radius, 0, radius),  # 左边缘
            ]
            for city in cities:
                if city.to_tuple() in terrain_dict:
                    terrain_dict[city.to_tuple()] = TerrainType.CITY.value

        return terrain_dict

    def _generate_hex_tile_entities(
        self,
        map_entity: Entity,
        map_component: MapComponent,
        terrain_dict: Dict[Tuple[int, int, int], int],
    ):
        """为六边形地图生成格子实体"""
        hex_coords = create_hex_map_coordinates(map_component.radius)

        for hex_coord in hex_coords:
            # 创建格子实体
            tile_entity = self.world.create_entity()

            # 获取地形类型和属性
            terrain_type_value = terrain_dict.get(
                hex_coord.to_tuple(), TerrainType.PLAIN.value
            )
            terrain_type = TerrainType(terrain_type_value)
            terrain_props = get_terrain_properties(terrain_type.value)

            # 将六边形坐标转换为像素坐标
            pixel_x, pixel_y = hex_to_pixel(hex_coord, map_component.hex_size)

            # 创建格子组件
            tile_component = TileComponent(
                terrain_type=terrain_type,
                type_name=TerrainTypeMapping[terrain_type],
                elevation=50,  # 默认海拔
                moisture=0.5,  # 默认湿度
                movement_cost=terrain_props["movement_cost"],
                defense_bonus=terrain_props["defense_bonus"],
                x=int(pixel_x),
                y=int(pixel_y),
                hex_q=hex_coord.q,
                hex_r=hex_coord.r,
                hex_s=hex_coord.s,
                visible=True,
                explored=False,
            )

            # 添加组件到实体
            self.world.add_component(tile_entity, tile_component)

            # 为地形添加效果组件
            self.create_terrain_effect(tile_entity, tile_component)

            # 记录格子实体（使用六边形坐标作为主键）
            map_component.hex_entities[hex_coord.to_tuple()] = tile_entity
            # 不再使用像素坐标作为键，因为会导致重叠问题

    def _generate_hex_tile_entities_from_terrain(
        self,
        map_entity: Entity,
        map_component: MapComponent,
        terrain_array: np.ndarray,
    ):
        """从地形数组为六边形地图生成格子实体"""
        hex_coords = create_hex_map_coordinates(map_component.radius)

        for hex_coord in hex_coords:
            # 创建格子实体
            tile_entity = self.world.create_entity()

            # 将六边形坐标转换为数组索引
            col = hex_coord.q + map_component.radius
            row = hex_coord.r + map_component.radius

            # 获取地形类型和属性
            if 0 <= row < terrain_array.shape[0] and 0 <= col < terrain_array.shape[1]:
                terrain_type_value = terrain_array[row, col]
            else:
                terrain_type_value = TerrainType.PLAIN.value

            terrain_type = TerrainType(terrain_type_value)
            terrain_props = get_terrain_properties(terrain_type.value)

            # 将六边形坐标转换为像素坐标
            pixel_x, pixel_y = hex_to_pixel(hex_coord, map_component.hex_size)

            # 创建格子组件
            tile_component = TileComponent(
                terrain_type=terrain_type,
                type_name=TerrainTypeMapping[terrain_type],
                elevation=50,  # 默认海拔
                moisture=0.5,  # 默认湿度
                movement_cost=terrain_props["movement_cost"],
                defense_bonus=terrain_props["defense_bonus"],
                x=int(pixel_x),
                y=int(pixel_y),
                hex_q=hex_coord.q,
                hex_r=hex_coord.r,
                hex_s=hex_coord.s,
                visible=True,
                explored=False,
            )

            # 添加组件到实体
            self.world.add_component(tile_entity, tile_component)

            # 为地形添加效果组件
            self.create_terrain_effect(tile_entity, tile_component)

            # 记录格子实体（使用六边形坐标作为主键）
            map_component.hex_entities[hex_coord.to_tuple()] = tile_entity

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

    def create_terrain_effect(
        self, tile_entity: Entity, tile_component: TileComponent
    ) -> Optional[TerrainEffectComponent]:
        """为地形实体创建地形效果组件

        根据不同地形类型添加不同的地形效果组件：
        - 水：减少生命值，移速降低
        - 水边：静止恢复体力
        - 城市：占领后范围内攻击力增加，同时只能由一个阵营占领生效，离开和杀死对方后失效
        - 山地：骑兵移速速度降为最低，静止时隐蔽，对非山地地形攻击加成
        - 森林：静止时可以隐蔽
        - 平原：骑兵加速

        Args:
            tile_entity: 地形实体
            tile_component: 地形组件

        Returns:
            地形效果组件
        """
        # 创建地形效果组件
        terrain_effect = TerrainEffectComponent(
            current_terrain=tile_component.terrain_type
        )

        # 根据地形类型设置效果
        terrain_type = tile_component.terrain_type

        # 水域效果：减少生命值，移速降低
        if terrain_type in [TerrainType.RIVER, TerrainType.LAKE, TerrainType.OCEAN]:
            terrain_effect.active_effects.append("water_effect")
            terrain_effect.effect_data["water_effect"] = {
                "health_reduction": -1,  # 每回合减少1点生命值
                "movement_speed_modifier": 0.5,  # 移动速度降低50%
            }

        # 山地效果：骑兵移速速度降为最低，静止时隐蔽，对非山地地形攻击加成
        elif terrain_type == TerrainType.MOUNTAIN:
            terrain_effect.active_effects.append("mountain_effect")
            terrain_effect.effect_data["mountain_effect"] = {
                "cavalry_speed_reduction": True,  # 骑兵移速降低
                "concealment": True,  # 静止时隐蔽
                "attack_bonus": 1.2,  # 对非山地地形攻击加成20%
            }

        # 森林效果：静止时可以隐蔽
        elif terrain_type == TerrainType.FOREST:
            terrain_effect.active_effects.append("forest_effect")
            terrain_effect.effect_data["forest_effect"] = {
                "concealment": True,  # 静止时隐蔽
            }

        # 平原效果：骑兵加速
        elif terrain_type == TerrainType.PLAIN:
            terrain_effect.active_effects.append("plain_effect")
            terrain_effect.effect_data["plain_effect"] = {
                "cavalry_speed_bonus": 1.3,  # 骑兵移动速度提高30%
            }

        # 添加组件到实体
        self.world.add_component(tile_entity, terrain_effect)

        return terrain_effect

    def create_random_unit(self, faction_num: int = 3, unit_num: int = 5):
        import random
        import time

        # 使用当前时间作为随机种子
        random.seed(int(time.time()))

        # 获取所有单位类型
        unit_types = [
            UnitType.INFANTRY,
            UnitType.CAVALRY,
            UnitType.ARCHER,
            UnitType.ARCHER,
            UnitType.ARCHER,
        ]

        # 获取地图
        map_entity = self.world.query_manager.with_all(MapComponent).first()
        map_component = self.world.component_manager.get_component(
            map_entity, MapComponent
        )

        if map_component.map_type == "hexagonal":
            # 六边形地图的单位放置
            self._place_units_on_hex_map(
                map_component, faction_num, unit_num, unit_types
            )
        else:
            # 原有的方形地图逻辑
            map_width = map_component.width * map_component.tile_size
            map_height = map_component.height * map_component.tile_size

            # 边缘缓冲区大小，避免单位生成在地图最边缘
            buffer = int(map_width * 0.05)

            for faction_id in range(faction_num):
                # 跳过faction_id=0（可能是中立阵营）
                if faction_id == 0:
                    continue

                # 为该阵营的每个单位计算均匀分布的Y坐标
                y_positions = []
                if unit_num > 1:
                    # 计算均匀分布的y坐标
                    y_step = (map_height - 2 * buffer) / (unit_num - 1)
                    for i in range(unit_num):
                        y_positions.append(buffer + int(i * y_step))
                else:
                    # 如果只有一个单位，放在中间
                    y_positions.append(map_height // 2)

                # 根据阵营确定x坐标范围
                if faction_id == 1:  # 第一个阵营在左侧
                    x_min = buffer
                    x_max = int(map_width * 0.2)  # 地图宽度的20%
                elif faction_id == 2:  # 第二个阵营在右侧
                    x_min = int(map_width * 0.8)  # 地图宽度的80%
                    x_max = map_width - buffer
                else:  # 其他阵营（如果有）可以在中间或做其他安排
                    x_min = int(map_width * 0.4)
                    x_max = int(map_width * 0.6)

                # 创建该阵营的单位
                for i in range(unit_num):
                    # 在区域范围内添加一些随机性
                    x = random.randint(x_min, x_max)
                    y = y_positions[i] + random.randint(-buffer, buffer)

                    # 确保y坐标不超出地图边界
                    y = max(0, min(y, map_height - 1))

                    unit_type = unit_types[i]
                    # 创建单位
                    self.create_unit(unit_type, faction_id, x, y, owner_id=faction_id)

                # 为阵营创建战场统计组件
                self.create_battle_stats(faction_id)

    def _place_units_on_hex_map(
        self,
        map_component: MapComponent,
        faction_num: int,
        unit_num: int,
        unit_types: list,
    ):
        """在六边形地图上放置单位"""
        # 获取城市位置作为出生点
        city_coords = []
        for hex_coord_tuple, tile_entity in map_component.hex_entities.items():
            tile_component = self.world.component_manager.get_component(
                tile_entity, TileComponent
            )
            if tile_component and tile_component.terrain_type == TerrainType.CITY:
                city_coords.append(HexCoordinate(*hex_coord_tuple))

        # 如果没有城市，使用地图边缘
        if not city_coords:
            radius = map_component.radius
            city_coords = [
                HexCoordinate(radius, 0, -radius),  # 右边缘
                HexCoordinate(-radius, 0, radius),  # 左边缘
            ]

        for faction_id in range(1, faction_num):  # 跳过faction_id=0
            if faction_id - 1 < len(city_coords):
                spawn_hex = city_coords[faction_id - 1]
                spawn_pixel_x, spawn_pixel_y = hex_to_pixel(
                    spawn_hex, map_component.hex_size
                )

                # 在出生点周围放置单位
                for i in range(unit_num):
                    # 在出生点附近随机放置
                    offset_x = random.randint(-50, 50)
                    offset_y = random.randint(-50, 50)
                    x = int(spawn_pixel_x + offset_x)
                    y = int(spawn_pixel_y + offset_y)

                    unit_type = unit_types[i % len(unit_types)]
                    self.create_unit(unit_type, faction_id, x, y, owner_id=faction_id)

                # 为阵营创建战场统计组件
                self.create_battle_stats(faction_id)

    def create_benchmark_unit(
        self, faction_num: int = 3
    ) -> Optional[Tuple[Entity, UnitComponent]]:
        """创建随机单位"""
        import random

        # 获取所有单位类型
        unit_types = [
            UnitType.CAVALRY,
            UnitType.INFANTRY,
            UnitType.INFANTRY,
            UnitType.ARCHER,
            UnitType.ARCHER,
        ]

        # 获取地图
        map_entity = self.world.query_manager.with_all(MapComponent).first()
        map_component = self.world.component_manager.get_component(
            map_entity, MapComponent
        )

        # 获取单位所属阵营
        # faction = get_faction_config(faction_num)
        # 随机选择一个位置
        faction_num = faction_num + 1
        for faction_id in range(1, faction_num):
            # 获取单位所属阵营
            if faction_id == 0:
                continue
            for i in range(5):
                # 随机选择一个位置
                x = random.randint(0, (map_component.width) * map_component.tile_size)
                y = random.randint(0, (map_component.height) * map_component.tile_size)

                unit_type = unit_types[i]
                # 创建单位
                self.create_unit(unit_type, faction_id, x, y, owner_id=faction_id)
            self.create_battle_stats(faction_id)
            self.create_battle_stats(faction_id)
