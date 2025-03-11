from framework.core.ecs.system import System
from framework.core.ecs.world import World
from game.components import Position, Velocity, MapPosition


class MovementSystem(System):
    """移动系统，处理实体的移动"""

    def __init__(self):
        super().__init__([Position, Velocity], priority=1)
        self.map_width = 20  # 默认地图宽度
        self.map_height = 15  # 默认地图高度
        self.tile_size = 32  # 默认格子大小

    def update(self, world: World, delta_time: float) -> None:
        # 更新所有具有位置和速度组件的实体
        entities = world.get_entities_with_components(Position, Velocity)
        for entity in entities:
            pos = world.get_component(entity, Position)
            vel = world.get_component(entity, Velocity)

            # 计算新位置
            new_x = pos.x + vel.x * delta_time
            new_y = pos.y + vel.y * delta_time

            # 限制在地图范围内
            map_pixel_width = self.map_width * self.tile_size
            map_pixel_height = self.map_height * self.tile_size

            # 应用边界限制，考虑实体尺寸（假设为圆形，半径约为tile_size/2）
            entity_radius = self.tile_size / 2

            # 限制X坐标在地图范围内
            pos.x = max(entity_radius, min(new_x, map_pixel_width - entity_radius))

            # 限制Y坐标在地图范围内
            pos.y = max(entity_radius, min(new_y, map_pixel_height - entity_radius))

            # 如果实体撞到边界，将其速度在对应方向设为0
            if pos.x <= entity_radius or pos.x >= map_pixel_width - entity_radius:
                vel.x = 0

            if pos.y <= entity_radius or pos.y >= map_pixel_height - entity_radius:
                vel.y = 0
