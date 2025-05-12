import pygame
from typing import List, Dict, Tuple, Optional, Set
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.engine.events import EventType, EventMessage
from framework.utils.logging import get_logger
from game.components import UnitComponent, UnitState, UnitType
from game.components import MapComponent


class UnitSystem(System):
    """单位系统，负责处理单位的逻辑，如移动、战斗等"""

    def __init__(self, priority: int = 20):
        """初始化单位系统"""
        super().__init__(required_components=[UnitComponent], priority=priority)
        self.logger = get_logger("UnitSystem")
        self.selected_unit_entity = None
        self.unit_entities = set()  # 存储所有单位实体的集合
        self.map_entity = None
        self.map_component = None

    def initialize(self, context):
        """初始化系统"""
        self.context = context
        self.logger.info("单位系统初始化")
        # 查找地图实体和组件
        for entity in self.context.entity_manager.get_all_entity():
            if self.context.component_manager.has_component(entity, MapComponent):
                self.map_entity = entity
                self.map_component = self.context.get_component(entity, MapComponent)
                break
        self.logger.info("单位系统初始化完成")
        # 注意：单位的创建已移至ComponentFactory，此处不再创建测试单位

    def subscribe_events(self):
        """订阅事件"""
        self.context.event_manager.subscribe(
            [EventType.KEY_DOWN, EventType.MOUSEBUTTON_DOWN], self._handle_event
        )

    def _handle_event(self, event: EventMessage):
        """处理单位选择"""
        if event.type == EventType.KEY_DOWN or event.type == EventType.MOUSEBUTTON_DOWN:
            self.handle_key_event(event)
            self.handle_mouse_event(event)

    def handle_mouse_event(self, event: EventMessage):
        if event.type == EventType.MOUSEBUTTON_DOWN and event.data.get("button") == 1:
            mouse_x, mouse_y = event.data.get("pos", (0, 0))
            self.logger.debug(f"鼠标点击位置: ({mouse_x}, {mouse_y})")
            clicked_unit_entity = self._get_unit_at_position(mouse_x, mouse_y)
            if clicked_unit_entity:
                unit_component = self.context.get_component(
                    clicked_unit_entity, UnitComponent
                )
                if unit_component and not unit_component.is_alive:
                    self.logger.debug(f"无法选择已死亡的单位: {unit_component.name}")
                    return  # 不处理死亡单位的选择
            self._handle_unit_selection(mouse_x, mouse_y)

    def handle_key_event(self, event: EventMessage):
        if event.type == EventType.KEY_DOWN:
            if event.data.get("key") == "escape":
                self.logger.info("取消选择单位")
                # 直接更新组件状态，不调用unit_system
                for entity in self.selected_units:
                    unit = self.context.get_component(entity, UnitComponent)
                    if unit:
                        unit.is_selected = False
                self.selected_units = []

    def update(self, delta_time: float):
        """更新单位系统"""
        if not self.is_enabled():
            return

        # 获取所有拥有UnitComponent的实体
        entities = self.context.with_all(UnitComponent).result()
        self.unit_entities = set(entities)

        # 处理单位状态更新
        for entity in entities:
            unit_component = self.context.get_component(entity, UnitComponent)
            self._update_unit_state(entity, unit_component, delta_time)

    def _update_unit_state(
        self, entity: Entity, unit: UnitComponent, delta_time: float
    ):
        """更新单位状态"""
        # 根据单位当前状态执行相应逻辑
        # 注意：移动逻辑已移至MovementSystem处理
        if unit.state == UnitState.ATTACKING:
            # 攻击逻辑在这里实现
            pass
        elif unit.state == UnitState.DEAD and self.is_alive(unit):
            # 如果单位状态是死亡但生命值大于0，恢复为空闲状态
            unit.state = UnitState.IDLE

        # 检查单位生命值
        if unit.current_health <= 0 and unit.is_alive:
            unit.state = UnitState.DEAD
            unit.current_health = 0
            unit.is_alive = False  # 更新存活状态
            self.logger.info(f"单位 {unit.name} 已阵亡")
            # 发布单位死亡事件，如果尚未在AttackSystem中发布，或者需要在此处也发布
            # self.context.event_manager.publish(
            # EventMessage(
            # EventType.UNIT_KILLED,
            # {
            # "entity": entity,
            # "unit_component": unit
            # },
            # )
            # )

    def is_alive(self, unit: UnitComponent) -> bool:
        """检查单位是否存活"""
        return unit.is_alive

    def can_move(self, unit: UnitComponent) -> bool:
        """检查单位是否可以移动"""
        return self.is_alive(unit)

    def can_attack(self, unit: UnitComponent) -> bool:
        """检查单位是否可以攻击"""
        return self.is_alive(unit)

    def reset_turn(self, unit: UnitComponent):
        """重置单位回合状态"""
        unit.movement_left = unit.movement
        unit.has_acted = False
        if unit.state != UnitState.DEAD:
            unit.state = UnitState.IDLE

    def create_test_units(self):
        """创建测试单位"""
        self.logger.info("创建测试单位")

        # 创建不同类型的单位
        # 玩家1的单位（蓝色）
        infantry_entity = self.create_unit(UnitType.INFANTRY, 1, 5, 5, 0)
        cavalry_entity = self.create_unit(UnitType.CAVALRY, 1, 7, 5, 0)
        archer_entity = self.create_unit(UnitType.ARCHER, 1, 9, 5, 0)

        # 玩家2的单位（红色）
        enemy_infantry = self.create_unit(UnitType.INFANTRY, 2, 5, 10, 1)
        enemy_cavalry = self.create_unit(UnitType.CAVALRY, 2, 7, 10, 1)
        enemy_siege = self.create_unit(UnitType.SIEGE, 2, 9, 10, 1)

        # 创建一个英雄单位
        hero_entity = self.create_unit(UnitType.HERO, 1, 7, 7, 0)

        # 将单位添加到场景的单位列表中
        self.units = [
            infantry_entity,
            cavalry_entity,
            archer_entity,
            enemy_infantry,
            enemy_cavalry,
            enemy_siege,
            hero_entity,
        ]

        # 默认选择英雄单位
        self.select_unit(hero_entity)
        self.selected_units = [hero_entity]

        self.logger.info(f"创建了 {len(self.units)} 个测试单位")

    def create_unit(
        self,
        unit_type: UnitType,
        faction: int,
        position_x: float,
        position_y: float,
        owner_id: int = 0,
        unit_size: float = 1.0,
    ) -> Entity:
        """创建一个新单位"""
        # 创建单位实体
        unit_entity = self.context.entity_manager.create_entity()

        # 根据单位类型设置不同的属性
        if unit_type == UnitType.INFANTRY:
            unit = UnitComponent(
                name="步兵",
                unit_type=unit_type,
                position_x=position_x,
                position_y=position_y,
                unit_size=unit_size,
                max_health=100,
                current_health=100,
                attack=10,
                defense=5,
                range=1,
                movement=3,
                movement_left=3,
                owner_id=owner_id,
            )
        elif unit_type == UnitType.CAVALRY:
            unit = UnitComponent(
                name="骑兵",
                unit_type=unit_type,
                position_x=position_x,
                position_y=position_y,
                unit_size=unit_size,
                max_health=80,
                current_health=80,
                attack=15,
                defense=3,
                range=1,
                movement=5,
                movement_left=5,
                owner_id=owner_id,
            )
        elif unit_type == UnitType.ARCHER:
            unit = UnitComponent(
                name="弓箭手",
                unit_type=unit_type,
                position_x=position_x,
                position_y=position_y,
                unit_size=unit_size,
                max_health=70,
                current_health=70,
                attack=12,
                defense=2,
                range=3,
                movement=2,
                movement_left=2,
                owner_id=owner_id,
            )
        elif unit_type == UnitType.SIEGE:
            unit = UnitComponent(
                name="攻城单位",
                unit_type=unit_type,
                position_x=position_x,
                position_y=position_y,
                max_health=120,
                current_health=120,
                attack=20,
                defense=8,
                range=2,
                movement=1,
                movement_left=1,
                owner_id=owner_id,
            )
        elif unit_type == UnitType.HERO:
            unit = UnitComponent(
                name="英雄",
                unit_type=unit_type,
                position_x=position_x,
                position_y=position_y,
                max_health=150,
                current_health=150,
                attack=25,
                defense=10,
                range=2,
                movement=10,
                movement_left=10,
                owner_id=owner_id,
            )
        else:
            # 默认为步兵
            unit = UnitComponent(
                position_x=position_x, position_y=position_y, owner_id=owner_id
            )

        # 添加单位组件到实体
        self.context.component_manager.add_component(unit_entity, unit)
        self.unit_entities.add(unit_entity)
        self.logger.info(
            f"创建了一个新单位: {unit.name} 在位置 ({position_x}, {position_y}) 尺寸{unit_size}米"
        )
        return unit_entity

    # def move_unit(self, unit_entity: Entity, target_x: float, target_y: float) -> bool:
    #     """将单位移动到目标浮点坐标（米）"""
    #     unit = self.context.get_component(unit_entity, UnitComponent)
    #     if not unit or not self.can_move(unit):
    #         return False
    #     # 计算欧氏距离
    #     distance = (
    #         (target_x - unit.position_x) ** 2 + (target_y - unit.position_y) ** 2
    #     ) ** 0.5
    #     # if distance > unit.movement_left:
    #     #     return False
    #     # 检查目标位置是否有其他单位（允许一定重叠可根据unit_size调整）
    #     for other_entity in self.unit_entities:
    #         if other_entity == unit_entity:
    #             continue
    #         other_unit = self.context.get_component(other_entity, UnitComponent)
    #         if other_unit and self.is_alive(other_unit):
    #             dx = other_unit.position_x - target_x
    #             dy = other_unit.position_y - target_y
    #             min_dist = (unit.unit_size + other_unit.unit_size) / 2
    #             if (dx**2 + dy**2) ** 0.5 < min_dist:
    #                 return False

    #     # 减少移动力
    #     old_x, old_y = unit.position_x, unit.position_y
    #     # unit.movement_left -= distance

    #     # 发布移动事件，让MovementSystem处理实际移动
    #     if self.context.event_manager:
    #         self.context.event_manager.publish(
    #             EventMessage(
    #                 EventType.UNIT_MOVED,
    #                 {
    #                     "entity": unit_entity,
    #                     "origin_x": old_x,
    #                     "origin_y": old_y,
    #                     "target_x": target_x,
    #                     "target_y": target_y,
    #                     "unit": unit,
    #                 },
    #             )
    #         )
    #         self.logger.info(
    #             f"单位 {unit.name} 开始从({old_x},{old_y})移动到({target_x},{target_y})，剩余移动力{unit.movement_left}"
    #         )
    #         return True
    #     return False

    # 注意：attack_unit方法已移至UnitAttackSystem

    def select_unit(self, unit_entity: Entity) -> bool:
        """选择一个单位"""
        if not self.context.component_manager.has_component(unit_entity, UnitComponent):
            return False

        unit = self.context.get_component(unit_entity, UnitComponent)
        if not self.is_alive(unit):
            self.logger.info(f"无法选择已阵亡的单位: {unit.name}")
            return False

        # 取消之前选择的单位
        if self.selected_unit_entity and self.selected_unit_entity != unit_entity:
            prev_unit_comp = self.context.get_component(
                self.selected_unit_entity, UnitComponent
            )
            if prev_unit_comp:  # 确保前一个选中的单位组件存在
                prev_unit_comp.is_selected = False

        # 选择新单位
        unit.is_selected = True
        self.selected_unit_entity = unit_entity

        self.logger.info(
            f"选择了单位: {unit.name} 在位置 ({unit.position_x}, {unit.position_y})"
        )
        return True

    def deselect_unit(self) -> bool:
        """取消选择当前单位"""
        if not self.selected_unit_entity:
            return False

        unit = self.context.get_component(self.selected_unit_entity, UnitComponent)
        unit.is_selected = False
        self.selected_unit_entity = None

        self.logger.info("取消选择当前单位")
        return True

    def get_selected_unit(self) -> Optional[Tuple[Entity, UnitComponent]]:
        """获取当前选择的单位"""
        if not self.selected_unit_entity:
            return None

        if not self.context.component_manager.has_component(
            self.selected_unit_entity, UnitComponent
        ):
            self.selected_unit_entity = None
            return None

        unit = self.context.get_component(self.selected_unit_entity, UnitComponent)
        return (self.selected_unit_entity, unit)

    def reset_units_turn(self, owner_id: Optional[int] = None):
        """重置单位的回合状态，可以指定只重置特定玩家的单位"""
        for entity in self.unit_entities:
            unit = self.context.get_component(entity, UnitComponent)
            if owner_id is None or unit.owner_id == owner_id:
                self.reset_turn(unit)

        self.logger.info(
            f"重置了{'所有' if owner_id is None else f'玩家 {owner_id} 的'}单位回合状态"
        )

    def _handle_unit_selection(self, map_x: int, map_y: int):
        # 获取当前选中的单位
        currently_selected = None
        if self.selected_units:
            entity = self.selected_units[0]
            currently_selected = (
                entity,
                self.context.get_component(entity, UnitComponent),
            )

        # 查找点击位置的单位
        clicked_unit = None
        clicked_entity = None
        for entity in self.units:
            unit = self.context.get_component(entity, UnitComponent)
            if unit and unit.position_x == map_x and unit.position_y == map_y:
                clicked_unit = unit
                clicked_entity = entity
                break

        # 处理单位选择
        if clicked_entity:
            # 确保点击的单位是存活的才能进行选择操作
            if not self.is_alive(clicked_unit):
                self.logger.info(f"无法选择已阵亡的单位: {clicked_unit.name}")
                return

            if currently_selected and currently_selected[0] == clicked_entity:
                # 取消选择单位
                clicked_unit.is_selected = False
                self.selected_units = []
                self.logger.info(f"取消选择单位: {clicked_unit.name}")
            else:
                # 选择新单位
                # 先取消之前选中的单位
                if currently_selected:
                    currently_selected[1].is_selected = False

                # 选择新单位
                clicked_unit.is_selected = True
                self.selected_units = [clicked_entity]
                self.logger.info(f"选择单位: {clicked_unit.name}")
        elif currently_selected:
            # 处理移动指令
            selected_entity, selected_unit = currently_selected
            if self.can_move(selected_unit):
                # 计算欧氏距离
                origin_x, origin_y = selected_unit.position_x, selected_unit.position_y
                distance = ((map_x - origin_x) ** 2 + (map_y - origin_y) ** 2) ** 0.5

                # 检查移动距离是否超过剩余移动力
                # if distance > selected_unit.movement_left:
                #     self.logger.info(
                #         f"单位 {selected_unit.name} 移动距离超过剩余移动力"
                #     )
                #     return

                # 检查目标位置是否有其他单位
                for other_entity in self.unit_entities:
                    if other_entity == selected_entity:
                        continue
                    other_unit = self.context.get_component(other_entity, UnitComponent)
                    if other_unit and self.is_alive(other_unit):
                        dx = other_unit.position_x - map_x
                        dy = other_unit.position_y - map_y
                        min_dist = (selected_unit.unit_size + other_unit.unit_size) / 2
                        if (dx**2 + dy**2) ** 0.5 < min_dist:
                            self.logger.info(
                                f"单位 {selected_unit.name} 无法移动到 ({map_x}, {map_y})，目标位置有其他单位"
                            )
                            return

                # 减少移动力
                # selected_unit.movement_left -= distance

                # 发布移动事件，让MovementSystem处理实际移动
                if self.context.event_manager:
                    self.context.event_manager.publish(
                        EventMessage(
                            EventType.UNIT_MOVED,
                            {
                                "entity": selected_entity,
                                "origin_x": float("{:.1f}".format(origin_x)),
                                "origin_y": float("{:.1f}".format(origin_y)),
                                "target_x": float("{:.1f}".format(map_x)),
                                "target_y": float("{:.1f}".format(map_y)),
                                "unit": selected_unit,
                            },
                        )
                    )

                self.logger.info(
                    f"单位 {selected_unit.name} 开始移动到 ({map_x}, {map_y})"
                )
            else:
                self.logger.info(
                    f"单位 {selected_unit.name} 无法移动到 ({map_x}, {map_y})"
                )
