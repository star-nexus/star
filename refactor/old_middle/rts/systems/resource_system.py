from framework.ecs.system import System
from rts.components import (
    ResourceComponent,
    UnitComponent,
    BuildingComponent,
    FactionComponent,
)


class ResourceSystem(System):
    """
    资源系统：管理资源收集、消耗和分配
    """

    def __init__(self):
        super().__init__([ResourceComponent])
        # 资源节点列表（矿点、油井等资源生成点）
        self.resource_nodes = []

        # 资源消耗配置
        self.consumption_rates = {
            "unit_food": {
                UnitComponent.TYPE_SUPPLY: 0.5,  # 辎重单位食物消耗
                UnitComponent.TYPE_PLAINS: 1.0,  # 平原单位食物消耗
                UnitComponent.TYPE_MOUNTAIN: 1.2,  # 山地单位食物消耗
                UnitComponent.TYPE_WATER: 1.0,  # 水面单位食物消耗
                UnitComponent.TYPE_RANGED: 1.0,  # 远程单位食物消耗
                UnitComponent.TYPE_AIR: 1.5,  # 空中单位食物消耗
            }
        }

        # 资源生产配置
        self.production_rates = {
            "headquarters": {
                "gold": 5.0,  # 主基地每秒产出5金币
                "weapons": 1.0,  # 主基地每秒产出1武器
                "food": 2.0,  # 主基地每秒产出2食物
                "supplies": 1.0,  # 主基地每秒产出1辎重
            },
            "supply_depot": {"food": 5.0},  # 补给站每秒产出5食物
        }

    def update(self, delta_time):
        """更新所有资源组件"""
        # 更新资源生产
        self._update_resource_production(delta_time)

        # 更新资源消耗
        self._update_resource_consumption(delta_time)

        # 更新资源节点
        self._update_resource_nodes(delta_time)

        # 处理资源组件自身的更新逻辑
        for entity in self.entities:
            resource_comp = entity.get_component(ResourceComponent)
            resource_comp.update_resources(delta_time)

    def _update_resource_production(self, delta_time):
        """更新所有实体的资源生产"""
        # 查找所有建筑并根据类型增加资源
        for entity_id, entity in self.world.entities.items():
            if entity.has_component(BuildingComponent) and entity.has_component(
                FactionComponent
            ):
                building_comp = entity.get_component(BuildingComponent)
                faction_comp = entity.get_component(FactionComponent)

                # 获取该建筑所属阵营
                faction_entity = None
                for faction_ent in self.world.entities.values():
                    if faction_ent.has_component(FactionComponent):
                        f_comp = faction_ent.get_component(FactionComponent)
                        if f_comp.faction_id == faction_comp.faction_id:
                            faction_entity = faction_ent
                            break

                if faction_entity and faction_entity.has_component(ResourceComponent):
                    faction_res_comp = faction_entity.get_component(ResourceComponent)

                    # 根据建筑类型生产资源
                    if (
                        building_comp.building_type
                        == BuildingComponent.TYPE_HEADQUARTERS
                    ):
                        # 主基地生产各种资源
                        rates = self.production_rates.get("headquarters", {})
                        for res_type, rate in rates.items():
                            self._add_resource_to_faction(
                                faction_entity, res_type, rate * delta_time
                            )

                    elif (
                        building_comp.building_type
                        == BuildingComponent.TYPE_SUPPLY_DEPOT
                    ):
                        # 补给站主要生产食物
                        rates = self.production_rates.get("supply_depot", {})
                        for res_type, rate in rates.items():
                            self._add_resource_to_faction(
                                faction_entity, res_type, rate * delta_time
                            )

    def _update_resource_consumption(self, delta_time):
        """更新所有实体的资源消耗"""
        # 处理单位消耗
        for entity_id, entity in self.world.entities.items():
            if entity.has_component(UnitComponent) and entity.has_component(
                FactionComponent
            ):
                unit_comp = entity.get_component(UnitComponent)
                faction_comp = entity.get_component(FactionComponent)

                # 获取该单位所属阵营
                faction_entity = None
                for faction_ent in self.world.entities.values():
                    if faction_ent.has_component(FactionComponent):
                        f_comp = faction_ent.get_component(FactionComponent)
                        if f_comp.faction_id == faction_comp.faction_id:
                            faction_entity = faction_ent
                            break

                if faction_entity and faction_entity.has_component(ResourceComponent):
                    faction_res_comp = faction_entity.get_component(ResourceComponent)

                    # 计算该类型单位的食物消耗
                    food_rate = self.consumption_rates["unit_food"].get(
                        unit_comp.unit_type, 1.0
                    )
                    total_food_consumption = (
                        unit_comp.food_consumption * food_rate * delta_time
                    )

                    # 消耗食物
                    if not faction_res_comp.consume_resource(
                        "food", total_food_consumption
                    ):
                        # 资源不足，单位受到负面影响
                        # TODO: 实现饥饿机制
                        pass

    def _update_resource_nodes(self, delta_time):
        """更新资源节点"""
        # TODO: 实现资源节点更新逻辑
        pass

    def _add_resource_to_faction(self, faction_entity, resource_type, amount):
        """向阵营添加资源"""
        if faction_entity and faction_entity.has_component(ResourceComponent):
            res_comp = faction_entity.get_component(ResourceComponent)
            res_comp.add_resource(resource_type, amount)

    def transfer_resources(self, source_entity, target_entity, resource_type, amount):
        """
        转移资源从一个实体到另一个实体
        :return: 是否成功转移
        """
        if not source_entity.has_component(
            ResourceComponent
        ) or not target_entity.has_component(ResourceComponent):
            return False

        source_res = source_entity.get_component(ResourceComponent)
        target_res = target_entity.get_component(ResourceComponent)

        # 检查源实体是否有足够资源
        if not source_res.consume_resource(resource_type, amount):
            return False

        # 转移到目标实体
        target_res.add_resource(resource_type, amount)
        return True

    def register_resource_node(self, resource_node):
        """注册一个资源节点到系统"""
        self.resource_nodes.append(resource_node)
