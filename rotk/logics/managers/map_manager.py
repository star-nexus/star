import random
from rotk.logics.components import (
    MapComponent,
    TerrainType,
    UniqueComponent,
)
from framework.managers.events import EventManager, Message
from framework.core.ecs.world import World
from rotk.logics.managers.terrain_generator import TerrainGenerator
from rotk.logics.managers.map_feature_generator import MapFeatureGenerator
from rotk.logics.managers.terrain_utility import TerrainUtility


class MapManager:
    """地图管理器，负责地图生成和管理"""

    def __init__(self):
        """初始化地图管理器"""
        self.default_width = 50
        self.default_height = 50

        # 创建各个子模块
        self.terrain_generator = TerrainGenerator()
        self.feature_generator = MapFeatureGenerator()
        self.terrain_utility = TerrainUtility()
        
        # 保存上次创建的地图数据
        self.current_grid = None
        self.current_height_map = None
        self.current_moisture_map = None
        self.current_river_map = None
        self.current_cities = []

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
    ) -> None:
        """初始化地图管理器
        
        Args:
            world: 游戏世界
            event_manager: 事件管理器
        """
        self.event_manager = event_manager
        # 订阅地图生成事件
        self.event_manager.subscribe(
            "MAP_REGENERATED", lambda message: self.generate_map(world)
        )

    def create_map(self, world, width=None, height=None):
        """创建新地图
        
        Args:
            world: 游戏世界
            width: 地图宽度，默认使用default_width
            height: 地图高度，默认使用default_height
        """
        width = width or self.default_width
        height = height or self.default_height

        # 创建地图实体
        map_entity = world.create_entity()
        world.add_component(map_entity, UniqueComponent(unique_id="map"))
        world.add_component(map_entity, MapComponent(width=width, height=height))

        # 生成地图内容
        self.generate_map(world)

    def generate_map(self, world):
        """生成地图内容
        
        使用TerrainGenerator和MapFeatureGenerator生成随机地图
        
        Args:
            world: 游戏世界
        """
        # 获取地图实体和组件
        map_entity = world.get_entities_with_components(MapComponent)
        if not map_entity:
            return

        map_comp = world.get_component(map_entity[0], MapComponent)
        if not map_comp:
            return

        width, height = map_comp.width, map_comp.height

        # 使用地形生成器生成基本地形
        grid, height_map, moisture_map, river_map = self.terrain_generator.generate_terrain(width, height)
        
        # 使用特征生成器添加特殊地形特征
        cities = self.feature_generator.add_all_features(grid, height_map, river_map, width, height)
        
        # 保存当前地图数据
        self.current_grid = grid
        self.current_height_map = height_map
        self.current_moisture_map = moisture_map
        self.current_river_map = river_map
        self.current_cities = cities
        
        # 更新地图组件
        map_comp.grid = grid
        map_comp.cities = cities

        # 发布地图生成完成事件
        self.event_manager.publish("MAP_GENERATED",Message(topic="MAP_GENERATED", data_type="MAP_GENERATED", data={"width": width, "height": height}))

    def regenerate_map(self, world):
        """重新生成地图
        
        Args:
            world: 游戏世界
        """
        # 获取地图实体和组件
        map_entities = world.get_entities_with_components(MapComponent)
        if not map_entities:
            return

        map_comp = world.get_component(map_entities[0], MapComponent)
        if not map_comp:
            return

        # 生成新地图
        self.generate_map(world)

        # 发布地图重新生成事件
        self.event_manager.publish(Message("MAP_REGENERATED", {}))

    def get_movement_cost(self, terrain_type):
        """获取地形的移动消耗
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 移动消耗值
        """
        return self.terrain_utility.get_movement_cost(terrain_type)

    def get_terrain_color(self, terrain_type):
        """获取地形的颜色
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            tuple: RGB颜色值
        """
        return self.terrain_utility.get_terrain_color(terrain_type)

    def find_walkable_position(self, world):
        """在地图上查找可通行位置
        
        Args:
            world: 游戏世界
            
        Returns:
            tuple: (x, y) 位置坐标
        """
        map_entities = world.get_entities_with_components(MapComponent)
        if not map_entities:
            return (0, 0)

        map_comp = world.get_component(map_entities[0], MapComponent)
        if not map_comp:
            return (0, 0)

        width, height = map_comp.width, map_comp.height
        grid = map_comp.grid

        # 优先使用城市作为初始位置
        if self.current_cities:
            # 随机选择一个城市
            city_x, city_y = random.choice(self.current_cities)
            return (city_x, city_y)

        # 如果没有城市，寻找平原或其他可通行地形
        valid_positions = []
        for y in range(height):
            for x in range(width):
                terrain = grid[y][x]
                if self.terrain_utility.can_pass_terrain("land", terrain):
                    valid_positions.append((x, y))

        if valid_positions:
            return random.choice(valid_positions)

        # 如果没有找到有效位置，返回地图中心
        return (width // 2, height // 2)

    def get_terrain_at(self, world, x, y):
        """获取指定位置的地形类型
        
        Args:
            world: 游戏世界
            x: X坐标
            y: Y坐标
            
        Returns:
            TerrainType: 地形类型
        """
        map_entities = world.get_entities_with_components(MapComponent)
        if not map_entities:
            return TerrainType.PLAINS

        map_comp = world.get_component(map_entities[0], MapComponent)
        if not map_comp or not map_comp.grid:
            return TerrainType.PLAINS

        # 检查是否在地图范围内
        if x < 0 or x >= map_comp.width or y < 0 or y >= map_comp.height:
            return TerrainType.OCEAN  # 地图外视为海洋

        return map_comp.grid[int(y)][int(x)]

    def is_valid_spawn_position(self, world, x: float, y: float) -> bool:
        """检查位置是否适合生成单位
        
        Args:
            world: 游戏世界
            x: X坐标
            y: Y坐标
            
        Returns:
            bool: 是否适合生成单位
        """
        terrain = self.get_terrain_at(world, int(x), int(y))
        return self.terrain_utility.can_pass_terrain("land", terrain)
        
    def get_defense_bonus(self, terrain_type):
        """获取地形提供的防御加成
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 防御加成系数
        """
        return self.terrain_utility.get_defense_bonus(terrain_type)
        
    def get_ranged_accuracy_modifier(self, terrain_type):
        """获取地形对远程攻击精度的修正
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            float: 精度修正系数
        """
        return self.terrain_utility.get_ranged_accuracy_modifier(terrain_type)
        
    def is_water(self, terrain_type):
        """检查地形是否为水域
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            bool: 是否为水域
        """
        return self.terrain_utility.is_water(terrain_type)
        
    def is_rough_terrain(self, terrain_type):
        """检查地形是否为崎岖地形
        
        Args:
            terrain_type: 地形类型
            
        Returns:
            bool: 是否为崎岖地形
        """
        return self.terrain_utility.is_rough_terrain(terrain_type)
