import random
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from game.components import MapTile, Terrain, TerrainType


class MapGenerationSystem(System):
    """地图生成系统，负责生成地图"""

    def __init__(self):
        super().__init__([], priority=0)  # 最高优先级，确保地图首先生成
        self.map_generated = False
        self.width = 0
        self.height = 0

    def generate_map(self, world: World, width: int, height: int) -> None:
        """生成指定大小的地图"""
        self.width = width
        self.height = height

        # 清理现有的地图格子实体
        entities = world.get_entities_with_components(MapTile)
        for entity in entities:
            world.remove_entity(entity)

        # 使用柏林噪声或其他算法生成随机地形
        # 这里简单实现：随机生成各种类型的地形
        terrain_types = list(TerrainType)

        # 为每个格子创建实体
        for x in range(width):
            for y in range(height):
                tile_entity = world.create_entity()
                # 创建MapTile组件
                map_tile = MapTile(x=x, y=y)

                # 随机决定地形类型，但平原的概率更高
                if random.random() < 0.5:
                    terrain_type = TerrainType.PLAIN
                else:
                    terrain_type = random.choice(terrain_types)

                # 创建Terrain组件
                terrain = Terrain(type=terrain_type)

                # 添加组件到实体
                world.add_component(tile_entity, map_tile)
                world.add_component(tile_entity, terrain)

        self.map_generated = True
        print(f"Map generated: {width}x{height}")

    def update(self, world: World, delta_time: float) -> None:
        """如果地图尚未生成，则生成地图"""
        if not self.map_generated:
            self.generate_map(world, 20, 15)  # 默认生成20x15的地图
