import math
from framework.ecs.system import System
from rts.components import (
    UnitComponent,
    PositionComponent,
    MovementComponent,
    AttackComponent,
    DefenseComponent,
    FactionComponent,
)


class UnitSystem(System):
    """
    单位系统：处理单位移动、寻路和行动逻辑
    管理游戏中所有单位实体的行为，控制它们的移动、地形交互和状态更新
    """

    def __init__(self):
        """
        初始化单位系统
        定义系统关心的组件类型，只有同时具有这些组件的实体才会被处理
        """
        super().__init__([UnitComponent, PositionComponent, MovementComponent])
        self.map_data = None  # 地图数据引用，用于地形检查和寻路

    def set_map_data(self, map_data):
        """
        设置地图数据引用

        参数:
            map_data: 游戏地图数据对象，包含地形信息和寻路网格
        """
        self.map_data = map_data

    def update(self, delta_time):
        """
        更新所有单位的状态和行为

        参数:
            delta_time: 帧间时间差（秒），用于基于时间的更新
        """
        # 遍历系统中的所有单位实体
        for entity in self.entities:
            # 获取必要的组件引用
            unit_comp = entity.get_component(UnitComponent)
            pos_comp = entity.get_component(PositionComponent)
            move_comp = entity.get_component(MovementComponent)

            # 跳过不在移动状态或没有目标位置的单位
            if not unit_comp.is_moving or not unit_comp.target_position:
                continue

            # 处理单位移动逻辑
            self._process_unit_movement(entity, delta_time)

            # 更新攻击冷却时间
            if unit_comp.attack_cooldown > 0:
                unit_comp.attack_cooldown -= delta_time

    def _process_unit_movement(self, entity, delta_time):
        """
        处理单位向目标位置的移动
        实现基于物理的简单移动逻辑

        参数:
            entity: 要处理的单位实体
            delta_time: 帧间时间差（秒）
        """
        # 获取必要的组件引用
        unit_comp = entity.get_component(UnitComponent)
        pos_comp = entity.get_component(PositionComponent)
        move_comp = entity.get_component(MovementComponent)

        # 获取目标位置
        target_x, target_y = unit_comp.target_position

        # 计算移动方向和距离
        dx = target_x - pos_comp.x  # X方向距离
        dy = target_y - pos_comp.y  # Y方向距离
        distance = math.sqrt(dx * dx + dy * dy)  # 欧几里得距离

        # 如果已经非常接近目标（小于5像素），停止移动
        if distance < 5:
            unit_comp.is_moving = False
            move_comp.is_moving = False
            return

        # 标准化方向向量（转为单位向量）
        if distance > 0:
            dx /= distance
            dy /= distance

        # 获取考虑地形影响后的实际移动速度
        speed = self._get_terrain_adjusted_speed(entity)

        # 计算这一帧的位移量
        move_x = dx * speed * delta_time
        move_y = dy * speed * delta_time

        # 应用移动，更新单位位置
        pos_comp.x += move_x
        pos_comp.y += move_y

        # 设置移动组件的移动状态标志
        move_comp.is_moving = True

    def _get_terrain_adjusted_speed(self, entity):
        """
        获取考虑地形影响后的单位移动速度
        不同单位在不同地形上的移动速度会有变化

        参数:
            entity: 单位实体

        返回:
            float: 调整后的移动速度值
        """
        # 如果没有地图数据，返回默认速度
        if not self.map_data:
            return 100  # 默认速度

        # 获取必要的组件引用
        unit_comp = entity.get_component(UnitComponent)
        pos_comp = entity.get_component(PositionComponent)
        move_comp = entity.get_component(MovementComponent)

        # 获取单位所在的瓦片坐标（从像素坐标转换）
        tile_x = int(pos_comp.x / 32)  # 假设每个瓦片为32x32像素
        tile_y = int(pos_comp.y / 32)

        # 检查位置是否有效（是否在地图范围内）
        if not self.map_data.is_valid_position(tile_x, tile_y):
            return unit_comp.speed  # 如果超出地图，使用默认速度

        # 获取当前位置的地形类型
        tile = self.map_data.get_tile(tile_x, tile_y)
        terrain_type = tile.type

        # 获取该地形类型对应的速度，如果没有特定设置则使用默认速度
        terrain_speed = move_comp.speed.get(terrain_type, unit_comp.speed)

        # 飞行单位忽略地形惩罚
        if move_comp.is_flying:
            return unit_comp.speed

        # 特殊能力：穿越困难地形
        # 水面穿越能力
        if terrain_type == "water" and move_comp.can_traverse_water:
            # 可以穿越水面的单位，使用至少为平原速度80%的速度
            terrain_speed = max(
                terrain_speed, move_comp.speed.get("plains", unit_comp.speed) * 0.8
            )

        # 山地穿越能力
        if terrain_type == "mountain" and move_comp.can_traverse_mountain:
            # 可以穿越山地的单位，使用至少为平原速度70%的速度
            terrain_speed = max(
                terrain_speed, move_comp.speed.get("plains", unit_comp.speed) * 0.7
            )

        return terrain_speed
