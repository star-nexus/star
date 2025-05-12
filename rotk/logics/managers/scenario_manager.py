import random
import math
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message
from rotk.logics.components import (
    MapComponent,
    UnitPositionComponent,
    UnitType,
    TerrainType,
    HumanControlComponent,
)
from rotk.logics.managers import UnitManager, FactionManager, MapManager


class ScenarioManager:
    """负责处理场景布局、单位部署和游戏初始化"""

    def __init__(
        self,
        world: World,
        event_manager: EventManager,
        unit_manager: UnitManager,
        map_manager: MapManager,
        faction_manager: FactionManager,
    ):
        self.world = world
        self.event_manager = event_manager
        self.unit_manager = unit_manager
        self.map_manager = map_manager
        self.faction_manager = faction_manager
        self.player_units = []

        # 部队数量配置
        self.unit_count_config = {
            1: {"infantry": 9, "ranged": 5, "cavalry": 3},  # 魏国
            2: {"infantry": 9, "ranged": 5, "cavalry": 0},  # 蜀国
            3: {"infantry": 0, "ranged": 7, "cavalry": 3},  # 吴国
            4: {"infantry": 3, "ranged": 0, "cavalry": 0},  # 黄巾军
        }

        # 单位间距配置
        self.unit_spacing = 40.0  # 默认间距（米）

    def create_test_units(self, camera_manager=None):
        """创建测试用的阵营单位，在随机但战略合理的位置"""
        # 获取地图尺寸
        map_entity = self.world.get_unique_entity(MapComponent)
        map_comp = self.world.get_component(map_entity, MapComponent)
        if not map_comp:
            return []

        map_width, map_height = map_comp.width, map_comp.height

        # 清空当前玩家单位列表
        self.player_units = []

        # 为每个阵营定义生成区域 - 确保各阵营初始位置有所区分但又有随机性
        regions = {
            # 魏国在地图西部(随机选择西北或西南)
            1: {
                "x_range": (map_width // 8, map_width // 3),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
            # 蜀国在地图东部(随机选择东北或东南)
            2: {
                "x_range": (map_width * 2 // 3, map_width * 7 // 8),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
            # 吴国在地图南部(随机选择东南或西南的南部区域)
            3: {
                "x_range": (map_width // 8, map_width * 7 // 8),
                "y_range": (map_height * 2 // 3, map_height * 7 // 8),
            },
            # 黄巾军可以在整个地图上随机分布
            4: {
                "x_range": (map_width // 8, map_width * 7 // 8),
                "y_range": (map_height // 8, map_height * 7 // 8),
            },
        }

        # 查找可行走的位置作为各阵营中心点
        faction_centers = {}
        for faction_id, region in regions.items():
            # 尝试多次找到合适的区域中心
            for attempt in range(10):
                center_x = random.randint(region["x_range"][0], region["x_range"][1])
                center_y = random.randint(region["y_range"][0], region["y_range"][1])

                # 确保区域中心点地形适合生成单位
                if self.map_manager.is_valid_spawn_position(
                    self.world, center_x, center_y
                ):
                    # 为该阵营设置中心点
                    faction_centers[faction_id] = (center_x, center_y)
                    break
                # 如果多次尝试后仍找不到合适位置，使用区域中心点
                if attempt == 9:
                    center_x = (region["x_range"][0] + region["x_range"][1]) // 2
                    center_y = (region["y_range"][0] + region["y_range"][1]) // 2
                    faction_centers[faction_id] = (center_x, center_y)

        # 为三个主要阵营创建单位
        # 生成各阵营单位 - 这里只显示魏国部分作为示例，其他阵营类似
        wei_center_x, wei_center_y = faction_centers[1]
        wei_config = self.unit_count_config[1]

        self._create_faction_units(1, wei_center_x, wei_center_y, wei_config)

        # 蜀国单位 (阵营ID: 2，玩家阵营)
        shu_center_x, shu_center_y = faction_centers[2]
        shu_config = self.unit_count_config[2]
        shu_units = self._create_faction_units(
            2, shu_center_x, shu_center_y, shu_config
        )
        self.player_units.extend(shu_units)

        # 吴国单位 (阵营ID: 3)
        wu_center_x, wu_center_y = faction_centers[3]
        wu_config = self.unit_count_config[3]
        self._create_faction_units(3, wu_center_x, wu_center_y, wu_config)

        # 黄巾军单位 (阵营ID: 4) - 随机放置
        self._create_rebel_units(4, faction_centers[4], self.unit_count_config[4])

        # 设置相机位置到玩家单位
        if self.player_units and camera_manager:
            self._focus_camera_on_player_units(camera_manager, map_comp)

        return self.player_units

    def _create_faction_units(self, faction_id, center_x, center_y, faction_config):
        """为指定阵营创建单位"""
        units = []

        # 根据阵营配置创建不同类型单位
        if faction_id == 1:  # 魏国
            # 创建盾兵方阵
            shield_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            shield_units = self.unit_manager.create_unit_formation(
                UnitType.SHIELD_INFANTRY,
                faction_id,
                shield_pos[0],
                shield_pos[1],
                faction_config["infantry"],
                self.unit_spacing,
                random.choice(["square", "staggered"]),
            )
            units.extend(shield_units)

            # 创建弓箭手
            archer_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            archer_units = self.unit_manager.create_unit_formation(
                UnitType.ARCHER,
                faction_id,
                archer_pos[0],
                archer_pos[1],
                faction_config["ranged"],
                self.unit_spacing,
                random.choice(["line", "staggered"]),
            )
            units.extend(archer_units)

            # 创建骑兵
            cavalry_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            cavalry_units = self.unit_manager.create_unit_formation(
                UnitType.HEAVY_CAVALRY,
                faction_id,
                cavalry_pos[0],
                cavalry_pos[1],
                faction_config["cavalry"],
                self.unit_spacing,
                random.choice(["wedge", "line"]),
            )
            units.extend(cavalry_units)

        elif faction_id == 2:  # 蜀国
            # 蜀国创建长戟兵
            spear_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            spear_units = self.unit_manager.create_unit_formation(
                UnitType.SPEAR_INFANTRY,
                faction_id,
                spear_pos[0],
                spear_pos[1],
                faction_config["infantry"],
                self.unit_spacing,
                random.choice(["staggered", "square"]),
            )
            units.extend(spear_units)

            # 蜀国创建弩手
            crossbow_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            crossbow_units = self.unit_manager.create_unit_formation(
                UnitType.CROSSBOWMAN,
                faction_id,
                crossbow_pos[0],
                crossbow_pos[1],
                faction_config["ranged"],
                self.unit_spacing,
                random.choice(["line", "staggered"]),
            )
            units.extend(crossbow_units)

        elif faction_id == 3:  # 吴国
            # 吴国创建骑射手
            mounted_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            mounted_units = self.unit_manager.create_unit_formation(
                UnitType.MOUNTED_ARCHER,
                faction_id,
                mounted_pos[0],
                mounted_pos[1],
                faction_config["ranged"],
                self.unit_spacing,
                random.choice(["line", "circle"]),
            )
            units.extend(mounted_units)

            # 吴国创建斥候骑兵
            scout_pos = self._get_random_offset_position(center_x, center_y, 2, 4)
            scout_units = self.unit_manager.create_unit_formation(
                UnitType.SCOUT_CAVALRY,
                faction_id,
                scout_pos[0],
                scout_pos[1],
                faction_config["cavalry"],
                self.unit_spacing,
                random.choice(["wedge", "circle"]),
            )
            units.extend(scout_units)

        return units

    def _create_rebel_units(self, faction_id, center_pos, faction_config):
        """创建黄巾军单位"""
        rebel_count = faction_config["infantry"]
        rebel_center_x, rebel_center_y = center_pos
        units = []

        # 随机分布几个小队黄巾军
        for i in range(min(3, max(1, rebel_count // 3))):  # 至少1个小队，最多3个
            # 在黄巾中心点附近随机生成位置
            offset_angle = random.uniform(0, 2 * math.pi)
            offset_distance = random.randint(3, 8)  # 距离可以稍远些，更分散
            rebel_x = rebel_center_x + math.cos(offset_angle) * offset_distance
            rebel_y = rebel_center_y + math.sin(offset_angle) * offset_distance

            # 确保位置有效
            if not self.map_manager.is_valid_spawn_position(
                self.world, rebel_x, rebel_y
            ):
                rebel_x = rebel_center_x
                rebel_y = rebel_center_y

            unit_type = random.choice(
                [UnitType.SHIELD_INFANTRY, UnitType.ARCHER, UnitType.SPEAR_INFANTRY]
            )

            # 创建小群黄巾军
            count = max(1, rebel_count // (4 - i))  # 分配单位到各小队
            rebel_count -= count

            rebel_units = self.unit_manager.create_unit_formation(
                unit_type,
                faction_id,
                rebel_x,
                rebel_y,
                count,
                self.unit_spacing,
                random.choice(["square", "circle", "staggered"]),
            )
            units.extend(rebel_units)

        return units

    def _get_random_offset_position(self, center_x, center_y, min_dist, max_dist):
        """获取中心点附近的随机偏移位置"""
        angle = random.uniform(0, 2 * math.pi)
        distance = random.randint(min_dist, max_dist)
        offset_x = center_x + math.cos(angle) * distance
        offset_y = center_y + math.sin(angle) * distance
        return (offset_x, offset_y)

    def _focus_camera_on_player_units(self, camera_manager, map_comp):
        """将相机聚焦在玩家单位上"""
        if not self.player_units:
            return

        # 获取第一个玩家单位的位置
        first_unit = self.player_units[0]
        pos = self.world.get_component(first_unit, UnitPositionComponent)
        if pos:
            # 设置相机中心位置
            world_x = pos.x * map_comp.cell_size
            world_y = pos.y * map_comp.cell_size

            # 将相机中心点设置为玩家位置
            center_x = world_x - camera_manager.screen_width / (2 * camera_manager.zoom)
            center_y = world_y - camera_manager.screen_height / (
                2 * camera_manager.zoom
            )

            camera_manager.set_position(center_x, center_y)
            camera_manager.constrain(
                map_comp.width * map_comp.cell_size,
                map_comp.height * map_comp.cell_size,
                map_comp.cell_size,
            )

    def regenerate_battle_scene(self, camera_manager=None):
        """重新生成战场场景"""
        # 清空所有单位
        for entity in self.world.get_entities_with_components(UnitPositionComponent):
            self.world.remove_entity(entity)

        self.player_units = []

        # 清除人类控制器的选择状态
        hc_entity = self.world.get_unique_entity(HumanControlComponent)
        if hc_entity:
            hc_comp = self.world.get_component(hc_entity, HumanControlComponent)
            # 重置控制组件状态
            hc_comp.selected_unit = None
            hc_comp.target_unit = None
            hc_comp.move_target = None
            hc_comp.selected_position = None

        # 重新生成地图
        self.map_manager.regenerate_map(self.world)

        # 创建新的测试单位
        self.create_test_units(camera_manager)

        print("战场已重新生成!")
