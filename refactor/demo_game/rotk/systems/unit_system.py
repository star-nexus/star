import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
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
        map_manager,
        faction_system,
        unit_manager,
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
        self.world = world
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.faction_system = faction_system
        self.unit_manager = unit_manager

        # 如果提供了配置，加载它
        # if unit_configs:
        #     self.unit_configs = unit_configs
        # else:
        #     # 否则使用默认配置
        #     self._create_default_unit_configs()

        # 订阅单位命令事件
        self.event_manager.subscribe("MOVE_COMMAND", self._handle_move_command)
        self.event_manager.subscribe("ATTACK_COMMAND", self._handle_attack_command)

    # def _create_default_unit_configs(self):
    #     """创建默认单位配置"""
    #     # 刀盾兵配置
    #     self.unit_configs[UnitType.SHIELD_INFANTRY] = {
    #         "name": "刀盾兵",
    #         "category": UnitCategory.INFANTRY,
    #         "health": 120,
    #         "attack": 15,
    #         "defense": 12,
    #         "base_speed": 4.5,
    #         "max_speed": 6.0,
    #         "attack_range": 1.0,
    #         "food_consumption": 0.6,
    #         "symbol": "盾",
    #         "size": 24,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.GOOD,
    #             TerrainType.FOREST: TerrainAdaptability.AVERAGE,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
    #             TerrainType.HILL: TerrainAdaptability.AVERAGE,
    #             TerrainType.RIVER: TerrainAdaptability.POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.POOR,
    #         },
    #     }

    #     # 长戟兵配置
    #     self.unit_configs[UnitType.SPEAR_INFANTRY] = {
    #         "name": "长戟兵",
    #         "category": UnitCategory.INFANTRY,
    #         "health": 100,
    #         "attack": 18,
    #         "defense": 8,
    #         "base_speed": 4.0,
    #         "max_speed": 5.5,
    #         "attack_range": 1.5,
    #         "food_consumption": 0.6,
    #         "symbol": "戟",
    #         "size": 24,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.GOOD,
    #             TerrainType.FOREST: TerrainAdaptability.POOR,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
    #             TerrainType.HILL: TerrainAdaptability.AVERAGE,
    #             TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
    #         },
    #     }

    #     # 斥候骑兵配置
    #     self.unit_configs[UnitType.SCOUT_CAVALRY] = {
    #         "name": "斥候骑兵",
    #         "category": UnitCategory.CAVALRY,
    #         "health": 90,
    #         "attack": 12,
    #         "defense": 6,
    #         "base_speed": 8.0,
    #         "max_speed": 12.0,
    #         "attack_range": 1.0,
    #         "food_consumption": 0.8,
    #         "symbol": "侦",
    #         "size": 22,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.EXCELLENT,
    #             TerrainType.FOREST: TerrainAdaptability.POOR,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.VERY_POOR,
    #             TerrainType.HILL: TerrainAdaptability.AVERAGE,
    #             TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
    #         },
    #     }

    #     # 骑射手配置
    #     self.unit_configs[UnitType.MOUNTED_ARCHER] = {
    #         "name": "骑射手",
    #         "category": UnitCategory.CAVALRY,
    #         "health": 80,
    #         "attack": 14,
    #         "defense": 5,
    #         "base_speed": 7.5,
    #         "max_speed": 11.0,
    #         "attack_range": 4.0,
    #         "food_consumption": 0.7,
    #         "ammo_consumption": 1.0,
    #         "symbol": "骑",
    #         "size": 22,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.EXCELLENT,
    #             TerrainType.FOREST: TerrainAdaptability.POOR,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.VERY_POOR,
    #             TerrainType.HILL: TerrainAdaptability.AVERAGE,
    #             TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
    #         },
    #     }

    #     # 弓箭手配置
    #     self.unit_configs[UnitType.ARCHER] = {
    #         "name": "弓箭手",
    #         "category": UnitCategory.RANGED,
    #         "health": 80,
    #         "attack": 18,
    #         "defense": 5,
    #         "base_speed": 4.0,
    #         "max_speed": 5.0,
    #         "attack_range": 5.0,
    #         "food_consumption": 0.5,
    #         "ammo_consumption": 1.0,
    #         "symbol": "弓",
    #         "size": 20,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.GOOD,
    #             TerrainType.FOREST: TerrainAdaptability.AVERAGE,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
    #             TerrainType.HILL: TerrainAdaptability.AVERAGE,
    #             TerrainType.RIVER: TerrainAdaptability.POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.POOR,
    #         },
    #     }

    #     # 弩手配置
    #     self.unit_configs[UnitType.CROSSBOWMAN] = {
    #         "name": "弩手",
    #         "category": UnitCategory.RANGED,
    #         "health": 75,
    #         "attack": 22,
    #         "defense": 4,
    #         "base_speed": 3.5,
    #         "max_speed": 4.5,
    #         "attack_range": 4.0,
    #         "food_consumption": 0.5,
    #         "ammo_consumption": 0.8,
    #         "symbol": "弩",
    #         "size": 20,
    #         "terrain_adaptability": {
    #             TerrainType.PLAINS: TerrainAdaptability.GOOD,
    #             TerrainType.FOREST: TerrainAdaptability.POOR,
    #             TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
    #             TerrainType.HILL: TerrainAdaptability.POOR,
    #             TerrainType.RIVER: TerrainAdaptability.POOR,
    #             TerrainType.SWAMP: TerrainAdaptability.POOR,
    #         },
    #     }

    # def create_unit(
    #     self, unit_type: UnitType, faction_id: int, grid_x: int, grid_y: int
    # ) -> int:
    #     """创建指定类型、阵营的单位

    #     Args:
    #         unit_type: 单位类型
    #         faction_id: 阵营ID
    #         grid_x: 格子X坐标
    #         grid_y: 格子Y坐标

    #     Returns:
    #         int: 创建的单位实体ID
    #     """
    #     # 检查单位类型是否存在配置
    #     if unit_type not in self.unit_configs:
    #         print(f"未找到单位类型 {unit_type} 的配置")
    #         return None

    #     # 获取单位配置
    #     config = self.unit_configs[unit_type]

    #     # 获取阵营信息
    #     faction_color = (200, 200, 200)  # 默认颜色
    #     if faction_id in self.faction_system.factions:
    #         faction_color = self.faction_system.factions[faction_id]["color"]

    #     # 创建单位实体
    #     unit_entity = self.world.create_entity()

    #     # 添加基本单位组件
    #     self.world.add_component(
    #         unit_entity,
    #         UnitStatsComponent(
    #             name=config["name"],
    #             unit_type=unit_type,
    #             category=config["category"],
    #             faction_id=faction_id,
    #             health=config["health"],
    #             max_health=config["health"],
    #             attack=config["attack"],
    #             defense=config["defense"],
    #         ),
    #     )

    #     # 添加精确位置组件
    #     self.world.add_component(
    #         unit_entity,
    #         PrecisePositionComponent(
    #             grid_x=grid_x,
    #             grid_y=grid_y,
    #             offset_x=0.5,  # 居中
    #             offset_y=0.5,  # 居中
    #             prev_grid_x=grid_x,
    #             prev_grid_y=grid_y,
    #         ),
    #     )

    #     # 添加移动组件
    #     movement_component = UnitMovementComponent(
    #         base_speed=config.get("base_speed", 5.0),
    #         current_speed=config.get("base_speed", 5.0),
    #         max_speed=config.get("max_speed", 8.0),
    #         attack_range=config.get("attack_range", 1.0),
    #     )

    #     # 设置地形适应性
    #     if "terrain_adaptability" in config:
    #         movement_component.terrain_adaptability = config["terrain_adaptability"]

    #     self.world.add_component(unit_entity, movement_component)

    #     # 添加补给组件
    #     self.world.add_component(
    #         unit_entity,
    #         UnitSupplyComponent(
    #             food_consumption_rate=config.get("food_consumption", 0.5),
    #             ammo_consumption_rate=config.get("ammo_consumption", 0.0),
    #         ),
    #     )

    #     # 添加状态组件
    #     self.world.add_component(unit_entity, UnitStateComponent())

    #     # 添加渲染组件
    #     self.world.add_component(
    #         unit_entity,
    #         UnitRenderComponent(
    #             main_color=faction_color,
    #             accent_color=config.get("accent_color", (255, 255, 255)),
    #             symbol=config.get("symbol", "?"),
    #             size=config.get("size", 20),
    #         ),
    #     )

    #     # 更新地图实体位置记录 - 确保地图实体存在且有效
    #     map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
    #     if map_comp:
    #         # 使用格子坐标作为位置映射
    #         map_comp.entities_positions[unit_entity] = (grid_x, grid_y)
    #     else:
    #         print(f"警告: 地图组件不存在，无法更新单位位置映射")

    #     # 更新阵营单位计数 - 确保阵营存在且有效
    #     if self.faction_system and faction_id in self.faction_system.factions:
    #         faction_entity = self.faction_system.factions.get(faction_id, {}).get(
    #             "entity"
    #         )
    #         if faction_entity:
    #             faction_comp = self.world.get_component(
    #                 faction_entity, FactionComponent
    #             )
    #             if faction_comp:
    #                 faction_comp.unit_count += 1

    #     return unit_entity

    # def find_unit_placement_position(
    #     self,
    #     faction_id: int,
    #     near_x: int = None,
    #     near_y: int = None,
    #     max_distance: int = 5,
    # ) -> tuple:
    #     """为新单位寻找合适的放置位置

    #     Args:
    #         faction_id: 阵营ID
    #         near_x: 参考X坐标（可选）
    #         near_y: 参考Y坐标（可选）
    #         max_distance: 最大距离（可选）

    #     Returns:
    #         tuple: (x, y) 放置位置
    #     """
    #     map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
    #     if not map_comp:
    #         return (0, 0)

    #     width, height = map_comp.width, map_comp.height

    #     # 如果提供了参考点，在其附近寻找
    #     if near_x is not None and near_y is not None:
    #         # 从近到远搜索
    #         for d in range(1, max_distance + 1):
    #             candidates = []
    #             # 遍历以参考点为中心的范围
    #             for dy in range(-d, d + 1):
    #                 for dx in range(-d, d + 1):
    #                     # 只考虑边界上的点
    #                     if abs(dx) == d or abs(dy) == d:
    #                         x, y = near_x + dx, near_y + dy
    #                         if 0 <= x < width and 0 <= y < height:
    #                             # 检查是否可以放置
    #                             if self._is_valid_placement(x, y):
    #                                 candidates.append((x, y))

    #             if candidates:
    #                 return random.choice(candidates)

    #     # 如果没找到，或没提供参考点，随机寻找
    #     return self.map_manager.find_walkable_position(self.world)

    # def _is_valid_placement(self, x: int, y: int) -> bool:
    #     """检查位置是否可以放置单位

    #     Args:
    #         x: 格子X坐标
    #         y: 格子Y坐标

    #     Returns:
    #         bool: 是否可以放置
    #     """
    #     # 检查地形是否可通行
    #     if not self.map_manager.is_position_valid(self.world, x, y):
    #         return False

    #     # 检查是否已有单位
    #     map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
    #     if map_comp and (x, y) in map_comp.entities_positions.values():
    #         return False

    #     return True

    # def destroy_unit(self, unit_entity: int) -> None:
    #     """销毁单位

    #     Args:
    #         unit_entity: 单位实体ID
    #     """
    #     # 获取单位信息
    #     unit_stats = self.world.get_component(unit_entity, UnitStatsComponent)
    #     position = self.world.get_component(unit_entity, PrecisePositionComponent)

    #     if not unit_stats or not position:
    #         return

    #     # 从地图位置映射中移除
    #     map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
    #     if map_comp and unit_entity in map_comp.entities_positions:
    #         del map_comp.entities_positions[unit_entity]

    #     # 更新阵营单位计数
    #     faction_entity = self.faction_system.factions.get(
    #         unit_stats.faction_id, {}
    #     ).get("entity")
    #     if faction_entity:
    #         faction_comp = self.world.get_component(faction_entity, FactionComponent)
    #         if faction_comp:
    #             faction_comp.unit_count = max(0, faction_comp.unit_count - 1)

    #     # 销毁实体
    #     self.world.remove_entity(unit_entity)

    # def create_unit_formation(
    #     self,
    #     unit_type: UnitType,
    #     faction_id: int,
    #     center_x: int,
    #     center_y: int,
    #     count: int,
    #     formation_type: str = "square",
    # ) -> list:
    #     """创建单位编队

    #     Args:
    #         unit_type: 单位类型
    #         faction_id: 阵营ID
    #         center_x: 中心X坐标
    #         center_y: 中心Y坐标
    #         count: 单位数量
    #         formation_type: 编队类型('square', 'line', 'wedge')

    #     Returns:
    #         list: 创建的单位实体ID列表
    #     """
    #     units = []

    #     # 根据formation_type确定位置
    #     positions = []
    #     if formation_type == "square":
    #         # 方阵
    #         size = math.ceil(math.sqrt(count))
    #         for i in range(count):
    #             row = i // size
    #             col = i % size
    #             positions.append(
    #                 (center_x - size // 2 + col, center_y - size // 2 + row)
    #             )

    #     elif formation_type == "line":
    #         # 横线
    #         for i in range(count):
    #             positions.append((center_x - count // 2 + i, center_y))

    #     elif formation_type == "wedge":
    #         # V字形
    #         for i in range(count):
    #             depth = i // 2
    #             offset = i % 2
    #             if offset == 0:
    #                 positions.append((center_x - depth, center_y + depth))
    #             else:
    #                 positions.append((center_x + depth, center_y + depth))

    #     # 创建单位
    #     for x, y in positions:
    #         if self._is_valid_placement(x, y):
    #             unit_entity = self.create_unit(unit_type, faction_id, x, y)
    #             if unit_entity:
    #                 units.append(unit_entity)

    #     return units

    # def apply_damage(self, unit_entity: int, damage: float) -> None:
    #     """对单位应用伤害

    #     Args:
    #         unit_entity: 单位实体ID
    #         damage: 伤害值
    #     """
    #     stats = self.world.get_component(unit_entity, UnitStatsComponent)
    #     if not stats:
    #         return

    #     # 扣除生命值
    #     stats.health = max(0, stats.health - damage)

    #     # 如果单位死亡，处理死亡逻辑
    #     if stats.health <= 0:
    #         state = self.world.get_component(unit_entity, UnitStateComponent)
    #         if state:
    #             state.state = UnitState.DEAD

    #         # 发布单位死亡事件
    #         self.event_manager.publish(
    #             "UNIT_KILLED",
    #             Message(
    #                 topic="UNIT_KILLED",
    #                 data_type="combat_event",
    #                 data={
    #                     "unit_entity": unit_entity,
    #                     "unit_name": stats.name,
    #                     "faction_id": stats.faction_id,
    #                 },
    #             ),
    #         )

    #         # 销毁单位
    #         self.destroy_unit(unit_entity)

    # def add_experience(self, unit_entity: int, exp: float) -> None:
    #     """增加单位经验值，可能触发升级

    #     Args:
    #         unit_entity: 单位实体ID
    #         exp: 经验值
    #     """
    #     stats = self.world.get_component(unit_entity, UnitStatsComponent)
    #     if not stats:
    #         return

    #     # 增加经验
    #     old_exp = stats.experience
    #     stats.experience += exp

    #     # 检查是否可以升级
    #     old_level = stats.level
    #     while (
    #         stats.level < len(self.level_thresholds) - 1
    #         and stats.experience >= self.level_thresholds[stats.level + 1]
    #     ):
    #         stats.level += 1

    #         # 单位升级，提升属性
    #         bonus_factor = 1.1  # 每级提升10%
    #         stats.max_health *= bonus_factor
    #         stats.health = stats.max_health  # 升级时恢复满血
    #         stats.attack *= bonus_factor
    #         stats.defense *= bonus_factor

    #         # 发布单位升级事件
    #         if stats.level > old_level:
    #             self.event_manager.publish(
    #                 "UNIT_LEVELED_UP",
    #                 Message(
    #                     topic="UNIT_LEVELED_UP",
    #                     data_type="unit_event",
    #                     data={
    #                         "unit_entity": unit_entity,
    #                         "unit_name": stats.name,
    #                         "old_level": old_level,
    #                         "new_level": stats.level,
    #                     },
    #                 ),
    #             )

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
                self.destroy_unit(entity)
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
        for entity in moving_units:
            state_comp = world.get_component(entity, UnitStateComponent)
            pos_comp = world.get_component(entity, UnitPositionComponent)
            move_comp = world.get_component(entity, UnitMovementComponent)

            if state_comp.state == UnitState.MOVING and state_comp.target_position:
                target_x, target_y = state_comp.target_position

                # 检查是否已到达目标
                dx = target_x - pos_comp.grid_x
                dy = target_y - pos_comp.grid_y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < 0.1:  # 足够接近目标
                    # 到达目标，停止移动
                    pos_comp.grid_x = target_x
                    pos_comp.grid_y = target_y
                    pos_comp.offset_x = 0.5  # 居中
                    pos_comp.offset_y = 0.5
                    state_comp.state = UnitState.IDLE
                    state_comp.target_position = None
                else:
                    # 继续移动 - 使用米/秒速度和实际时间计算
                    # 计算在当前时间步内应移动的距离（米）
                    move_distance_meters = UnitConversion.calculate_movement_distance(
                        move_comp.current_speed, delta_time
                    )

                    # 将距离转换为格子单位（因为我们是在格子坐标系中移动）
                    move_distance_cells = UnitConversion.meters_to_cells(
                        move_distance_meters
                    )

                    # 计算移动方向
                    move_dir_x = dx / distance if distance > 0 else 0
                    move_dir_y = dy / distance if distance > 0 else 0

                    # 更新位置（现在使用格子单位的距离）
                    new_grid_x = pos_comp.grid_x + move_dir_x * move_distance_cells
                    new_grid_y = pos_comp.grid_y + move_dir_y * move_distance_cells

                    # 更新格子坐标和偏移
                    int_grid_x = int(new_grid_x)
                    int_grid_y = int(new_grid_y)

                    pos_comp.offset_x = new_grid_x - int_grid_x
                    pos_comp.offset_y = new_grid_y - int_grid_y
                    pos_comp.grid_x = int_grid_x
                    pos_comp.grid_y = int_grid_y

    def _handle_move_command(self, message: Message) -> None:
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
        pos_comp = self.world.get_component(unit_entity, UnitPositionComponent)
        state_comp = self.world.get_component(unit_entity, UnitStateComponent)

        if pos_comp and state_comp:
            # 设置目标位置
            state_comp.target_position = (target_x, target_y)
            state_comp.state = UnitState.MOVING

            # 清除之前的目标
            state_comp.target_entity = None
            state_comp.is_engaged = False

            # 更新地图位置
            map_comp = self.world.get_component(
                self.map_manager.map_entity, MapComponent
            )
            if map_comp and unit_entity in map_comp.entities_positions:
                # 立即更新记录的格子位置为目标位置
                map_comp.entities_positions[unit_entity] = (target_x, target_y)

    def _handle_attack_command(self, message: Message) -> None:
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
            state_comp = self.world.get_component(attacker, UnitStateComponent)
            if state_comp:
                # 清除移动目标
                state_comp.target_position = None
