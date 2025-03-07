import math
import random

from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    UnitStatsComponent,
    UnitPositionComponent,
    UnitMovementComponent,
    UnitSupplyComponent,
    UnitStateComponent,
    UnitRenderComponent,
    FactionComponent,
    UnitType,
    UnitCategory,
    TerrainType,
    TerrainAdaptability,
    UnitState,
    MapComponent,
)


class UnitManager:
    """管理单位的生命周期和属性更新，符合ECS架构"""

    def __init__(
        self,
        world: World,
        event_manager: EventManager,
        # map_manager,
        unit_configs=None,
    ):
        self.world = world
        self.event_manager = event_manager
        # self.map_manager = map_manager
        self.unit_configs = unit_configs if unit_configs else {}
        self.level_thresholds = [0, 100, 300, 600, 1000, 1500]
        if not unit_configs:
            self._create_default_unit_configs()

    def _create_default_unit_configs(self):
        """创建默认单位配置"""
        # 刀盾兵配置
        self.unit_configs[UnitType.SHIELD_INFANTRY] = {
            "name": "刀盾兵",
            "category": UnitCategory.INFANTRY,
            "health": 120,
            "attack": 15,
            "defense": 12,
            "base_speed": 4.5,
            "max_speed": 6.0,
            "attack_range": 1.0,
            "food_consumption": 0.6,
            "symbol": "盾",
            "size": 24,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.GOOD,
                TerrainType.FOREST: TerrainAdaptability.AVERAGE,
                TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
                TerrainType.HILL: TerrainAdaptability.AVERAGE,
                TerrainType.RIVER: TerrainAdaptability.POOR,
                TerrainType.SWAMP: TerrainAdaptability.POOR,
            },
        }
        # 长戟兵配置
        self.unit_configs[UnitType.SPEAR_INFANTRY] = {
            "name": "长戟兵",
            "category": UnitCategory.INFANTRY,
            "health": 100,
            "attack": 18,
            "defense": 8,
            "base_speed": 4.0,
            "max_speed": 5.5,
            "attack_range": 1.5,
            "food_consumption": 0.6,
            "symbol": "戟",
            "size": 24,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.GOOD,
                TerrainType.FOREST: TerrainAdaptability.POOR,
                TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
                TerrainType.HILL: TerrainAdaptability.AVERAGE,
                TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
                TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
            },
        }
        # 斥候骑兵配置
        self.unit_configs[UnitType.SCOUT_CAVALRY] = {
            "name": "斥候骑兵",
            "category": UnitCategory.CAVALRY,
            "health": 90,
            "attack": 12,
            "defense": 6,
            "base_speed": 8.0,
            "max_speed": 12.0,
            "attack_range": 1.0,
            "food_consumption": 0.8,
            "symbol": "侦",
            "size": 22,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.EXCELLENT,
                TerrainType.FOREST: TerrainAdaptability.POOR,
                TerrainType.MOUNTAIN: TerrainAdaptability.VERY_POOR,
                TerrainType.HILL: TerrainAdaptability.AVERAGE,
                TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
                TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
            },
        }
        # 骑射手配置
        self.unit_configs[UnitType.MOUNTED_ARCHER] = {
            "name": "骑射手",
            "category": UnitCategory.CAVALRY,
            "health": 80,
            "attack": 14,
            "defense": 5,
            "base_speed": 7.5,
            "max_speed": 11.0,
            "attack_range": 4.0,
            "food_consumption": 0.7,
            "ammo_consumption": 1.0,
            "symbol": "骑",
            "size": 22,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.EXCELLENT,
                TerrainType.FOREST: TerrainAdaptability.POOR,
                TerrainType.MOUNTAIN: TerrainAdaptability.VERY_POOR,
                TerrainType.HILL: TerrainAdaptability.AVERAGE,
                TerrainType.RIVER: TerrainAdaptability.VERY_POOR,
                TerrainType.SWAMP: TerrainAdaptability.VERY_POOR,
            },
        }
        # 弓箭手配置
        self.unit_configs[UnitType.ARCHER] = {
            "name": "弓箭手",
            "category": UnitCategory.RANGED,
            "health": 80,
            "attack": 18,
            "defense": 5,
            "base_speed": 4.0,
            "max_speed": 5.0,
            "attack_range": 5.0,
            "food_consumption": 0.5,
            "ammo_consumption": 1.0,
            "symbol": "弓",
            "size": 20,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.GOOD,
                TerrainType.FOREST: TerrainAdaptability.AVERAGE,
                TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
                TerrainType.HILL: TerrainAdaptability.AVERAGE,
                TerrainType.RIVER: TerrainAdaptability.POOR,
                TerrainType.SWAMP: TerrainAdaptability.POOR,
            },
        }
        # 弩手配置
        self.unit_configs[UnitType.CROSSBOWMAN] = {
            "name": "弩手",
            "category": UnitCategory.RANGED,
            "health": 75,
            "attack": 22,
            "defense": 4,
            "base_speed": 3.5,
            "max_speed": 4.5,
            "attack_range": 4.0,
            "food_consumption": 0.5,
            "ammo_consumption": 0.8,
            "symbol": "弩",
            "size": 20,
            "terrain_adaptability": {
                TerrainType.PLAINS: TerrainAdaptability.GOOD,
                TerrainType.FOREST: TerrainAdaptability.POOR,
                TerrainType.MOUNTAIN: TerrainAdaptability.POOR,
                TerrainType.HILL: TerrainAdaptability.POOR,
                TerrainType.RIVER: TerrainAdaptability.POOR,
                TerrainType.SWAMP: TerrainAdaptability.POOR,
            },
        }

    def create_unit(self, unit_type: UnitType, faction_id: int, x: int, y: int) -> int:
        """创建指定类型、阵营的单位"""
        if unit_type not in self.unit_configs:
            print(f"未找到单位类型 {unit_type} 的配置")
            return None
        config = self.unit_configs[unit_type]
        faction_color = (200, 200, 200)  # 默认颜色
        factions = self.world.get_entities_with_components(FactionComponent)
        for faction in factions:
            faction_comp = self.world.get_component(faction, FactionComponent)
            if faction_comp:
                faction_color = faction_comp.color
            else:
                faction_color = (200, 200, 200)
        unit_entity = self.world.create_entity()
        self.world.add_component(
            unit_entity,
            UnitStatsComponent(
                name=config["name"],
                unit_type=unit_type,
                category=config["category"],
                faction_id=faction_id,
                health=config["health"],
                max_health=config["health"],
                attack=config["attack"],
                defense=config["defense"],
            ),
        )
        self.world.add_component(
            unit_entity,
            UnitPositionComponent(
                x=x,
                y=x,
            ),
        )
        move_comp = UnitMovementComponent(
            base_speed=config.get("base_speed", 5.0),
            current_speed=config.get("base_speed", 5.0),
            max_speed=config.get("max_speed", 8.0),
        )
        if "terrain_adaptability" in config:
            move_comp.terrain_adaptability = config["terrain_adaptability"]
        self.world.add_component(unit_entity, move_comp)
        self.world.add_component(
            unit_entity,
            UnitSupplyComponent(
                food_consumption_rate=config.get("food_consumption", 0.5),
                ammo_consumption_rate=config.get("ammo_consumption", 0.0),
            ),
        )
        self.world.add_component(unit_entity, UnitStateComponent())
        self.world.add_component(
            unit_entity,
            UnitRenderComponent(
                main_color=faction_color,
                accent_color=config.get("accent_color", (255, 255, 255)),
                symbol=config.get("symbol", "?"),
                size=config.get("size", 20),
            ),
        )
        # map_comp = self.world.get_component(self.map_manager.map_entity, MapComponent)
        # if map_comp:
        #     map_comp.entities_positions[unit_entity] = (grid_x, grid_y)
        # else:
        #     print("警告: 地图组件不存在，无法更新单位位置映射")
        # if self.faction_system and faction_id in self.faction_system.factions:
        #     faction_entity = self.faction_system.factions.get(faction_id, {}).get(
        #         "entity"
        #     )
        #     if faction_entity:
        #         faction_comp = self.world.get_component(
        #             faction_entity, FactionComponent
        #         )
        #         if faction_comp:
        #             faction_comp.unit_count += 1
        return unit_entity

        # def find_unit_placement_position(
        #     self,
        #     faction_id: int,
        #     near_x: int = None,
        #     near_y: int = None,
        #     max_distance: int = 5,
        # ) -> tuple:
        #     """为新单位寻找合适的放置位置"""
        #     map_comp = self.world.get_component(self.map_manager.map_entity, "MapComponent")
        #     if not map_comp:
        #         return (0, 0)
        #     width, height = map_comp.width, map_comp.height
        #     if near_x is not None and near_y is not None:
        #         for d in range(1, max_distance + 1):
        #             candidates = []
        #             for dy in range(-d, d + 1):
        #                 for dx in range(-d, d + 1):
        #                     if abs(dx) == d or abs(dy) == d:
        #                         x, y = near_x + dx, near_y + dy
        #                         if 0 <= x < width and 0 <= y < height:
        #                             if self._is_valid_placement(x, y):
        #                                 candidates.append((x, y))
        #             if candidates:
        #                 return random.choice(candidates)
        #     return self.map_manager.find_walkable_position(self.world)

        # def _is_valid_placement(self, x: int, y: int) -> bool:
        """检查位置是否可以放置单位"""

        # if not self.map_manager.is_position_valid(self.world, x, y):
        #     return False
        map_entity = self.world.get_entities_with_components(MapComponent)
        map_comp = self.world.get_component(map_entity[0], MapComponent)
        if map_comp and (x, y) in map_comp.entities_positions.values():
            return False
        return True

    def create_unit_formation(
        self,
        unit_type: UnitType,
        faction_id: int,
        center_x: float,  # 中心点X坐标（格子，支持小数）
        center_y: float,  # 中心点Y坐标（格子，支持小数）
        count: int,
        spacing_meters: float = 20.0,  # 单位间距（米）
        formation_type: str = "square",
    ) -> list:
        """创建单位编队

        Args:
            unit_type: 单位类型
            faction_id: 阵营ID
            center_x: 中心点X坐标（格子，支持小数）
            center_y: 中心点Y坐标（格子，支持小数）
            count: 单位数量
            spacing_meters: 单位间距（米）
            formation_type: 编队类型('square', 'line', 'wedge', 'circle')

        Returns:
            list: 创建的单位实体ID列表
        """
        from rotk.utils.unit_conversion import UnitConversion

        units = []
        positions = []  # 存储格子坐标

        # 将单位间距从米转换为格子单位
        spacing_cells = UnitConversion.meters_to_cells(spacing_meters)

        if formation_type == "square":
            # 方阵
            size = math.ceil(math.sqrt(count))
            for i in range(count):
                row = i // size
                col = i % size
                # 计算精确位置，使编队居中
                x_pos = center_x + (col - (size - 1) / 2) * spacing_cells
                y_pos = center_y + (row - (size - 1) / 2) * spacing_cells
                positions.append((x_pos, y_pos))

        elif formation_type == "line":
            # 横线
            for i in range(count):
                x_pos = center_x + (i - (count - 1) / 2) * spacing_cells
                positions.append((x_pos, center_y))

        elif formation_type == "wedge":
            # V字形
            depth_spacing = spacing_cells * 0.866  # sqrt(3)/2，保持合理的垂直间距
            for i in range(count):
                depth = i // 2
                offset = i % 2
                if offset == 0:
                    positions.append(
                        (
                            center_x - depth * spacing_cells,
                            center_y + depth * depth_spacing,
                        )
                    )
                else:
                    positions.append(
                        (
                            center_x + depth * spacing_cells,
                            center_y + depth * depth_spacing,
                        )
                    )

        elif formation_type == "circle":
            # 圆形阵列
            if count <= 1:
                positions.append((center_x, center_y))
            else:
                radius_cells = (
                    spacing_cells * count / (2 * math.pi) * 0.8
                )  # 估算合理半径，乘以0.8使阵型更紧凑
                for i in range(count):
                    angle = 2 * math.pi * i / count
                    x_pos = center_x + radius_cells * math.cos(angle)
                    y_pos = center_y + radius_cells * math.sin(angle)
                    positions.append((x_pos, y_pos))

        # 创建单位
        for pos_x, pos_y in positions:
            unit_entity = self.create_unit(unit_type, faction_id, pos_x, pos_y)
            if unit_entity:
                units.append(unit_entity)

        return units

    def destroy_unit(self, unit_entity: int) -> None:
        """销毁单位"""
        # unit_stats = self.world.get_component(unit_entity, UnitStatsComponent)
        # pos = self.world.get_component(unit_entity, PrecisePositionComponent)
        # if not unit_stats or not pos:
        #     return
        # map_comp = self.world.get_component(self.map_manager.map_entity, "MapComponent")
        # if map_comp and unit_entity in map_comp.entities_positions:
        #     del map_comp.entities_positions[unit_entity]
        # faction_entity = self.faction_system.factions.get(
        #     unit_stats.faction_id, {}
        # ).get("entity")
        # if faction_entity:
        #     faction_comp = self.world.get_component(faction_entity, FactionComponent)
        #     if faction_comp:
        #         faction_comp.unit_count = max(0, faction_comp.unit_count - 1)
        self.world.remove_entity(unit_entity)

    def apply_damage(self, unit_entity: int, damage: float) -> None:
        """对单位应用伤害"""
        stats = self.world.get_component(unit_entity, UnitStatsComponent)
        if not stats:
            return
        stats.health = max(0, stats.health - damage)
        if stats.health <= 0:
            state = self.world.get_component(unit_entity, UnitStateComponent)
            if state:
                state.state = UnitState.DEAD
            self.event_manager.publish(
                "UNIT_KILLED",
                Message(
                    topic="UNIT_KILLED",
                    data_type="combat_event",
                    data={
                        "unit_entity": unit_entity,
                        "unit_name": stats.name,
                        "faction_id": stats.faction_id,
                    },
                ),
            )
            self.destroy_unit(unit_entity)

    def add_experience(self, unit_entity: int, exp: float) -> None:
        """增加单位经验值，可能触发升级"""
        stats = self.world.get_component(unit_entity, UnitStatsComponent)
        if not stats:
            return
        old_exp = stats.experience
        stats.experience += exp
        old_level = stats.level
        while (
            stats.level < len(self.level_thresholds) - 1
            and stats.experience >= self.level_thresholds[stats.level + 1]
        ):
            stats.level += 1
            bonus_factor = 1.1
            stats.max_health *= bonus_factor
            stats.health = stats.max_health
            stats.attack *= bonus_factor
            stats.defense *= bonus_factor
            if stats.level > old_level:
                self.event_manager.publish(
                    "UNIT_LEVELED_UP",
                    Message(
                        topic="UNIT_LEVELED_UP",
                        data_type="unit_event",
                        data={
                            "unit_entity": unit_entity,
                            "unit_name": stats.name,
                            "old_level": old_level,
                            "new_level": stats.level,
                        },
                    ),
                )
