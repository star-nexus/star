import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from game.components import (
    Position,
    MapPosition,
    Terrain,
    MapTile,
    Velocity,
)


class TerrainEffectSystem(System):
    """地形效果系统，处理地形对单位的影响"""

    def __init__(self):
        super().__init__([Position, Velocity], priority=2)  # 在移动前应用地形效果
        self.tile_size = 32  # 与MapRenderSystem中相同
        self.map_width = 20  # 默认地图宽度
        self.map_height = 15  # 默认地图高度

    def update(self, world: World, delta_time: float) -> None:
        """更新地形效果"""
        # 获取地图尺寸

        # 获取所有有位置和速度的实体（玩家、敌人等）
        entities = world.get_entities_with_components(Position, Velocity)

        # 获取所有地形格子
        tile_entities = world.get_entities_with_components(MapTile, Terrain)
        tiles = {}
        for entity in tile_entities:
            tile = world.get_component(entity, MapTile)
            terrain = world.get_component(entity, Terrain)
            tiles[(tile.x, tile.y)] = terrain

        for entity in entities:
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)

            # 计算实体所在的格子坐标
            grid_x = int(pos.x // self.tile_size)
            grid_y = int(pos.y // self.tile_size)

            # 确保格子坐标在地图范围内
            grid_x = max(0, min(grid_x, self.map_width - 1))
            grid_y = max(0, min(grid_y, self.map_height - 1))

            # 如果实体在地图范围内，应用地形效果
            if (grid_x, grid_y) in tiles:
                terrain = tiles[(grid_x, grid_y)]

                # 应用地形速度效果
                movement_mod = terrain.effects.get("movement_speed", 1.0)

                # 修改实体速度
                original_speed = math.sqrt(vel.x**2 + vel.y**2)
                if original_speed > 0:
                    # 保持方向，但修改速度大小
                    vel.x = vel.x * movement_mod
                    vel.y = vel.y * movement_mod

                # 如果实体有MapPosition组件，更新它
                if world.has_component(entity, MapPosition):
                    map_pos = world.get_component(entity, MapPosition)
                    map_pos.x = grid_x
                    map_pos.y = grid_y

            # 如果是不可通行地形或地图外，阻止移动
            elif (
                grid_x < 0
                or grid_x >= self.map_width
                or grid_y < 0
                or grid_y >= self.map_height
            ):
                # 实体尝试移动到地图外，停止其移动
                vel.x = 0
                vel.y = 0

                # 将实体推回地图范围内
                map_pixel_width = self.map_width * self.tile_size
                map_pixel_height = self.map_height * self.tile_size
                entity_radius = self.tile_size / 2

                pos.x = max(entity_radius, min(pos.x, map_pixel_width - entity_radius))
                pos.y = max(entity_radius, min(pos.y, map_pixel_height - entity_radius))
