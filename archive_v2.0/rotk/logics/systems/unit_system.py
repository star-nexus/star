import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    MapComponent,
    UnitStatsComponent,
    UnitMovementComponent,
    UnitSupplyComponent,
    UnitStateComponent,
    UnitPositionComponent,
    UnitRenderComponent,
    FactionComponent,
    UnitType,
    UnitCategory,
    UnitState,
    TerrainType,
    TerrainAdaptability,
)
from rotk.utils.unit_conversion import UnitConversion  # 导入新的单位转换工具类


class UnitSystem(System):
    """单位系统，负责管理游戏中的单位"""

    def __init__(self):
        super().__init__(
            [UnitStatsComponent, UnitPositionComponent, UnitRenderComponent],
            priority=15,
        )
        # self.map_manager = None
        # self.faction_system = None
        # 存储各单位类型的配置信息
        # self.unit_configs = {}
        # 单位经验值升级阈值
        self.level_thresholds = [0, 100, 300, 600, 1000, 1500]

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        unit_configs=None,
    ) -> None:
        """初始化单位系统

        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            faction_system: 阵营系统
            unit_manager: 单位管理器
            unit_configs: 单位配置（可选）
        """
        # self.world = world
        self.event_manager = event_manager
        # self.map_manager = map_manager
        # self.faction_system = faction_system
        # self.unit_manager = unit_manager

        # 如果提供了配置，加载它
        # if unit_configs:
        #     self.unit_configs = unit_configs
        # else:
        #     # 否则使用默认配置
        #     self._create_default_unit_configs()

        # 订阅单位命令事件
        self.event_manager.subscribe(
            "MOVE_COMMAND", lambda message: self._handle_move_command(world, message)
        )
        self.event_manager.subscribe(
            "ATTACK_COMMAND",
            lambda message: self._handle_attack_command(world, message),
        )

    def update(self, world: World, delta_time: float) -> None:
        """更新单位系统

        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 处理死亡单位
        entities = world.get_entities_with_components(
            UnitStatsComponent, UnitStateComponent
        )
        for entity in entities:
            state = world.get_component(entity, UnitStateComponent)
            stats = world.get_component(entity, UnitStatsComponent)

            # 处理死亡单位
            if state.state == UnitState.DEAD:
                # 已经在apply_damage中处理过销毁逻辑，这里不需要重复处理
                continue

            # 处理濒死单位
            if stats.health <= 0 and state.state != UnitState.DEAD:
                state.state = UnitState.DEAD
                world.remove_entity(entity)
                continue

            # 处理溃逃单位
            if state.is_routed and state.state != UnitState.ROUTED:
                state.state = UnitState.ROUTED
                # TODO: 处理溃逃行为
                continue

        # 处理单位移动
        moving_units = world.get_entities_with_components(
            UnitPositionComponent, UnitStateComponent, UnitMovementComponent
        )

        # 获取地图信息以确定格子大小和地形
        map_entities = world.get_entities_with_components(MapComponent)
        cell_size = 32  # 默认值
        map_comp = None
        if map_entities:
            map_comp = world.get_component(map_entities[0], MapComponent)
            if map_comp:
                cell_size = map_comp.cell_size

        for entity in moving_units:
            state_comp = world.get_component(entity, UnitStateComponent)
            pos_comp = world.get_component(entity, UnitPositionComponent)
            move_comp = world.get_component(entity, UnitMovementComponent)
            supply_comp = world.get_component(entity, UnitSupplyComponent)

            if state_comp.state == UnitState.MOVING and state_comp.target_position:
                target_x, target_y = state_comp.target_position

                # 检查是否已到达目标
                dx = target_x - pos_comp.x
                dy = target_y - pos_comp.y
                distance = math.sqrt(dx * dx + dy * dy)

                # 更精确的目标到达判定 - 距离很小时精确设置到目标位置
                if distance < 0.05:  # 减小判定阈值，更精确地到达目标
                    # 到达目标，停止移动并精确设置位置
                    pos_comp.x = target_x
                    pos_comp.y = target_y
                    state_comp.state = UnitState.IDLE
                    state_comp.target_position = None

                    # 发布到达目标事件
                    self.event_manager.publish(
                        "UNIT_REACHED_DESTINATION",
                        Message(
                            topic="UNIT_REACHED_DESTINATION",
                            data_type="unit_event",
                            data={"unit": entity, "position": (target_x, target_y)},
                        ),
                    )
                else:
                    # 更新单位实际移动速度 - 考虑地形、疲劳、补给等因素
                    actual_speed = self._calculate_actual_speed(
                        world, entity, move_comp, supply_comp, map_comp, pos_comp
                    )

                    # 记录当前位置用于平滑移动
                    prev_x, prev_y = pos_comp.x, pos_comp.y

                    # 计算在当前时间步内应移动的距离（米）
                    move_distance_meters = UnitConversion.calculate_movement_distance(
                        actual_speed, delta_time
                    )

                    # 将距离转换为格子单位
                    move_distance_cells = UnitConversion.meters_to_cells(
                        move_distance_meters
                    )

                    # 计算移动方向 - 确保规范化为单位向量
                    move_dir_x = dx / distance if distance > 0 else 0
                    move_dir_y = dy / distance if distance > 0 else 0

                    # 确保不会超过目标位置
                    if move_distance_cells >= distance:
                        # 直接设置到目标位置
                        pos_comp.x = target_x
                        pos_comp.y = target_y
                        state_comp.state = UnitState.IDLE
                        state_comp.target_position = None

                        # 发布到达目标事件
                        self.event_manager.publish(
                            "UNIT_REACHED_DESTINATION",
                            Message(
                                topic="UNIT_REACHED_DESTINATION",
                                data_type="unit_event",
                                data={"unit": entity, "position": (target_x, target_y)},
                            ),
                        )
                    else:
                        # 平滑更新位置 - 线性插值
                        pos_comp.x += move_dir_x * move_distance_cells
                        pos_comp.y += move_dir_y * move_distance_cells

                        # 保存移动轨迹数据用于渲染效果
                        move_comp.prev_x = prev_x
                        move_comp.prev_y = prev_y
                        move_comp.current_speed = actual_speed  # 更新当前速度

                        # 计算移动进度百分比，用于显示平滑效果
                        initial_distance = math.sqrt(
                            (target_x - prev_x) ** 2 + (target_y - prev_y) ** 2
                        )
                        if initial_distance > 0:
                            move_comp.movement_progress = 1 - (
                                distance / initial_distance
                            )

                        # 增加疲劳值
                        move_comp.fatigue = min(
                            100, move_comp.fatigue + 0.05 * delta_time
                        )

                        # 消耗补给
                        if supply_comp:
                            food_consumption = (
                                supply_comp.food_consumption_rate * delta_time / 60
                            )
                            supply_comp.food_supply = max(
                                0, supply_comp.food_supply - food_consumption
                            )

    def _calculate_actual_speed(
        self, world, entity, move_comp, supply_comp, map_comp, pos_comp
    ):
        """计算单位的实际移动速度，考虑各种影响因素

        Args:
            world: 游戏世界
            entity: 单位实体ID
            move_comp: 移动组件
            supply_comp: 补给组件
            map_comp: 地图组件
            pos_comp: 位置组件

        Returns:
            float: 实际移动速度 (米/秒)
        """
        # 基础速度
        base_speed = move_comp.base_speed

        # 地形修正
        terrain_factor = 1.0
        if (
            map_comp
            and 0 <= int(pos_comp.x) < map_comp.width
            and 0 <= int(pos_comp.y) < map_comp.height
        ):
            current_terrain = map_comp.grid[int(pos_comp.y)][int(pos_comp.x)]

            # 根据单位对地形的适应性修正速度
            if current_terrain in move_comp.terrain_adaptability:
                terrain_adaptability = move_comp.terrain_adaptability[current_terrain]
                if terrain_adaptability == TerrainAdaptability.EXCELLENT:
                    terrain_factor = 1.2  # 极佳适应性提升速度
                elif terrain_adaptability == TerrainAdaptability.GOOD:
                    terrain_factor = 1.0  # 良好适应性正常速度
                elif terrain_adaptability == TerrainAdaptability.AVERAGE:
                    terrain_factor = 0.8  # 一般适应性略微减速
                elif terrain_adaptability == TerrainAdaptability.POOR:
                    terrain_factor = 0.6  # 较差适应性明显减速
                elif terrain_adaptability == TerrainAdaptability.VERY_POOR:
                    terrain_factor = 0.4  # 极差适应性大幅减速

        # 补给修正 - 粮食不足会降低速度
        supply_factor = 1.0
        if supply_comp:
            if supply_comp.food_supply < 10:
                supply_factor = 0.5  # 粮食严重不足
            elif supply_comp.food_supply < 30:
                supply_factor = 0.7  # 粮食不足

        # 疲劳修正 - 疲劳度越高，速度越慢
        fatigue_factor = 1.0
        if move_comp.fatigue > 80:
            fatigue_factor = 0.6  # 极度疲劳
        elif move_comp.fatigue > 60:
            fatigue_factor = 0.8  # 疲劳
        elif move_comp.fatigue > 40:
            fatigue_factor = 0.9  # 轻微疲劳

        # 计算最终速度，但不超过最大速度
        actual_speed = base_speed * terrain_factor * supply_factor * fatigue_factor
        actual_speed = min(actual_speed, move_comp.max_speed)

        return max(0.5, actual_speed)  # 确保速度不会过低

    def _handle_move_command(self, world, message: Message) -> None:
        """处理移动命令

        Args:
            message: 包含移动命令的消息
        """
        data = message.data
        unit_entity = data.get("unit")
        target_x = data.get("target_x")
        target_y = data.get("target_y")

        if unit_entity is None or target_x is None or target_y is None:
            return

        # 获取单位组件
        pos_comp = world.get_component(unit_entity, UnitPositionComponent)
        state_comp = world.get_component(unit_entity, UnitStateComponent)
        move_comp = world.get_component(unit_entity, UnitMovementComponent)

        if pos_comp and state_comp and move_comp:
            # 保存起始位置，用于计算移动进度
            move_comp.start_x = pos_comp.x
            move_comp.start_y = pos_comp.y

            # 设置目标位置 - 使用精确的浮点值
            state_comp.target_position = (float(target_x), float(target_y))
            state_comp.state = UnitState.MOVING

            # 初始化移动进度为0
            move_comp.movement_progress = 0.0

            # 清除之前的目标
            state_comp.target_entity = None
            state_comp.is_engaged = False

            # 更新地图位置
            # map_comp = world.get_component(map_entity[0], MapComponent)
            # if map_comp and unit_entity in map_comp.entities_positions:
            #     # 立即更新记录的格子位置为目标位置
            #     map_comp.entities_positions[unit_entity] = (target_x, target_y)

    def _handle_attack_command(self, world, message: Message) -> None:
        """处理攻击命令

        Args:
            message: 包含攻击命令的消息
        """
        # 不做具体实现，交由CombatSystem处理
        # 只用于处理移除当前的移动目标等状态
        data = message.data
        attacker = data.get("attacker")

        if attacker:
            # 获取单位组件
            state_comp = world.get_component(attacker, UnitStateComponent)
            if state_comp:
                # 清除移动目标
                state_comp.target_position = None
