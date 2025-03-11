from framework.ecs.system import System
from rts.components import (
    BuildingComponent,
    PositionComponent,
    FactionComponent,
    ResourceComponent,
    SpriteComponent,
)


class BuildingSystem(System):
    """
    建筑系统：管理所有建筑的建造、生产和功能
    """

    def __init__(self):
        super().__init__([BuildingComponent, PositionComponent])
        self.selected_building = None  # 当前选中的建筑

    def update(self, delta_time):
        """更新所有建筑"""
        for entity in self.entities:
            building = entity.get_component(BuildingComponent)
            position = entity.get_component(PositionComponent)

            # 处理建造过程
            if not building.is_completed:
                self._update_construction(entity, delta_time)

            # 处理生产过程
            elif building.is_producing:
                self._update_production(entity, delta_time)

            # 处理资源生成和存储
            if building.is_completed:
                self._update_resource_generation(entity, delta_time)

    def _update_construction(self, entity, delta_time):
        """更新建筑建造进度"""
        building = entity.get_component(BuildingComponent)

        # 更新建造进度
        if building.construction_time > 0:
            progress_increment = 100.0 * delta_time / building.construction_time
            building.construction_progress += progress_increment

            # 检查建造是否完成
            if building.construction_progress >= 100:
                building.construction_progress = 100
                building.is_completed = True

                # 更新建筑外观
                if entity.has_component(SpriteComponent):
                    sprite = entity.get_component(SpriteComponent)
                    # 移除 "_construction" 后缀
                    if sprite.image_name.endswith("_construction"):
                        sprite.image_name = sprite.image_name[:-13]

    def _update_production(self, entity, delta_time):
        """更新建筑生产进度"""
        building = entity.get_component(BuildingComponent)

        if building.is_producing and building.production_target:
            # 更新生产进度
            building.production_progress += delta_time

            # 检查是否完成生产
            target_info = building.production_target
            if target_info and building.production_progress >= target_info.get(
                "time", 0
            ):
                # 生产完成，创建产品
                self._complete_production(entity)

    def _complete_production(self, entity):
        """完成生产过程"""
        building = entity.get_component(BuildingComponent)
        target_info = building.production_target

        # 重置生产状态
        building.is_producing = False
        building.production_progress = 0
        building.production_target = None

        # 实现生产逻辑 (将在后续与单位工厂集成)
        # 例如: 如果目标是单位，调用单位工厂创建单位
        # 如果目标是升级，应用升级效果

    def _update_resource_generation(self, entity, delta_time):
        """处理建筑的资源生成"""
        building = entity.get_component(BuildingComponent)

        # 如果有资源生成配置
        if building.resource_generation:
            # 寻找所属阵营
            if entity.has_component(FactionComponent):
                faction_comp = entity.get_component(FactionComponent)
                faction_id = faction_comp.faction_id

                # 寻找阵营实体
                faction_entity = None
                for potential_faction in self.world.entities.values():
                    if potential_faction.has_component(FactionComponent):
                        potential_faction_comp = potential_faction.get_component(
                            FactionComponent
                        )
                        if (
                            potential_faction_comp.faction_id == faction_id
                            and potential_faction != entity
                        ):
                            faction_entity = potential_faction
                            break

                # 生成资源并添加到阵营
                if faction_entity and faction_entity.has_component(ResourceComponent):
                    resource_comp = faction_entity.get_component(ResourceComponent)
                    for resource_type, rate in building.resource_generation.items():
                        amount = rate * delta_time
                        resource_comp.add_resource(resource_type, amount)

    def start_production(self, entity, product_type, product_data):
        """开始生产流程"""
        if not entity.has_component(BuildingComponent):
            return False

        building = entity.get_component(BuildingComponent)

        # 确保建筑已完成建造且未在生产中
        if not building.is_completed or building.is_producing:
            return False

        # 设置生产目标
        building.is_producing = True
        building.production_progress = 0
        building.production_target = {
            "type": product_type,
            "data": product_data,
            "time": product_data.get("production_time", 10.0),  # 默认10秒
        }

        return True

    def can_place_building(self, map_data, building_type, x, y, faction_id=None):
        """
        检查建筑是否可以放置在指定位置
        :param map_data: 地图数据
        :param building_type: 建筑类型
        :param x, y: 地图坐标 (格子坐标)
        :param faction_id: 阵营ID
        :return: 是否可放置, 原因描述
        """
        # 获取建筑尺寸
        from rts.factories.building_factory import BuildingFactory

        size = BuildingFactory(None).building_sizes.get(building_type, (1, 1))
        width, height = size

        # 检查边界
        if x < 0 or y < 0 or x + width > map_data.width or y + height > map_data.height:
            return False, "超出地图边界"

        # 检查所有格子是否可通行
        for check_y in range(y, y + height):
            for check_x in range(x, x + width):
                tile = map_data.get_tile(check_x, check_y)
                if not tile or not tile.passable:
                    return False, "地形不可建造"

                # 检查是否有其他建筑占用
                if tile.entity:
                    return False, "位置已被占用"

        # 检查与主基地的距离要求
        if building_type != BuildingComponent.TYPE_HEADQUARTERS:
            # 检查是否有相同阵营的主基地
            has_headquarters_nearby = False

            # 遍历所有建筑寻找主基地
            for entity in self.entities:
                if not entity.has_component(
                    BuildingComponent
                ) or not entity.has_component(FactionComponent):
                    continue

                building_comp = entity.get_component(BuildingComponent)
                faction_comp = entity.get_component(FactionComponent)

                # 只考虑相同阵营的已完成主基地
                if (
                    building_comp.building_type == BuildingComponent.TYPE_HEADQUARTERS
                    and building_comp.is_completed
                    and faction_comp.faction_id == faction_id
                ):

                    # 获取主基地位置
                    if entity.has_component(PositionComponent):
                        pos = entity.get_component(PositionComponent)
                        hq_x = int(pos.x / 32)  # 假设一格32像素
                        hq_y = int(pos.y / 32)

                        # 计算距离
                        distance = ((x - hq_x) ** 2 + (y - hq_y) ** 2) ** 0.5

                        # 如果在一定范围内，允许建造
                        if distance <= 20:  # 允许在主基地20格范围内建造
                            has_headquarters_nearby = True
                            break

            if not has_headquarters_nearby:
                return False, "必须在主基地附近建造"

        return True, "可以建造"

    def select_building(self, building):
        """选择建筑"""
        if self.selected_building:
            # 清除之前选择的建筑
            building_comp = self.selected_building.get_component(BuildingComponent)
            if building_comp:
                building_comp.is_selected = False

        self.selected_building = building

        if building and building.has_component(BuildingComponent):
            building_comp = building.get_component(BuildingComponent)
            building_comp.is_selected = True
