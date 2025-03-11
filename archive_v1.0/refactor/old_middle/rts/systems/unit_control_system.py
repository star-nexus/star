import pygame
import math
from framework.ecs.system import System
from rts.components import (
    UnitComponent,
    PositionComponent,
    MovementComponent,
    AttackComponent,
    FactionComponent,
)


class UnitControlSystem(System):
    """
    单位控制系统：处理单位的选择、命令和移动逻辑
    """

    def __init__(self):
        super().__init__([UnitComponent, PositionComponent, MovementComponent])
        self.selected_units = []  # 当前选中的单位
        self.unit_groups = {}  # 单位编组 {组号: [单位列表]}

    def select_units(self, units, add_to_selection=False):
        """选择单位"""
        if not add_to_selection:
            # 清除之前的选择
            for unit in self.selected_units:
                if unit.id in self.world.entities:
                    unit_comp = unit.get_component(UnitComponent)
                    if unit_comp:
                        unit_comp.is_selected = False
            self.selected_units.clear()

        # 添加新选择的单位
        for unit in units:
            if unit.has_component(UnitComponent) and unit not in self.selected_units:
                unit_comp = unit.get_component(UnitComponent)
                unit_comp.is_selected = True
                self.selected_units.append(unit)

    def move_selected_units(self, target_position):
        """命令选中的单位移动到指定位置"""
        if not self.selected_units:
            return

        # 根据单位数量决定移动方式
        if len(self.selected_units) == 1:
            # 单个单位直接移动到目标位置
            unit = self.selected_units[0]
            if unit.id in self.world.entities:
                self._command_unit_move(unit, target_position)
        else:
            # 多个单位使用队形移动
            self._move_units_in_formation(target_position)

    def _command_unit_move(self, unit, target_position):
        """命令单个单位移动"""
        if unit.id not in self.world.entities:
            return

        unit_comp = unit.get_component(UnitComponent)
        if unit_comp:
            unit_comp.is_moving = True
            unit_comp.target_position = target_position
            # 停止之前的攻击
            unit_comp.is_attacking = False
            unit_comp.target_entity = None

    def _move_units_in_formation(self, center_position):
        """以队形方式移动多个单位"""
        if not self.selected_units:
            return

        # 计算队形参数
        unit_count = len(self.selected_units)
        formation_radius = 20 + 10 * unit_count  # 根据单位数量动态调整队形大小

        # 计算每个单位的目标位置
        for i, unit in enumerate(self.selected_units):
            if unit.id not in self.world.entities:
                continue

            # 计算单位在队形中的角度
            angle = (2 * math.pi * i) / unit_count

            # 计算目标位置
            offset_x = formation_radius * math.cos(angle)
            offset_y = formation_radius * math.sin(angle)

            unit_target = (center_position[0] + offset_x, center_position[1] + offset_y)

            # 命令单位移动
            self._command_unit_move(unit, unit_target)

    def attack_with_selected_units(self, target_entity):
        """命令选中的单位攻击指定目标"""
        if not target_entity or target_entity.id not in self.world.entities:
            return

        for unit in self.selected_units:
            if unit.id in self.world.entities and unit.has_component(AttackComponent):
                attack_comp = unit.get_component(AttackComponent)
                unit_comp = unit.get_component(UnitComponent)

                if unit_comp and attack_comp:
                    unit_comp.is_attacking = True
                    unit_comp.target_entity = target_entity
                    attack_comp.target = target_entity
                    # 停止之前的移动
                    unit_comp.is_moving = False
                    unit_comp.target_position = None

    def group_selected_units(self, group_number):
        """将选中的单位编组"""
        if group_number >= 0 and group_number <= 9:  # 支持0-9编组
            self.unit_groups[group_number] = list(self.selected_units)

    def select_group(self, group_number):
        """选择指定编组的单位"""
        if group_number in self.unit_groups:
            # 过滤掉已经不存在的单位
            valid_units = [
                unit
                for unit in self.unit_groups[group_number]
                if unit.id in self.world.entities
            ]

            if valid_units:
                self.select_units(valid_units)

                # 更新组以移除无效单位
                self.unit_groups[group_number] = valid_units

    def select_units_in_rect(self, rect, faction_id=None):
        """选择指定矩形区域内的单位"""
        selected = []

        for entity in self.entities:
            # 检查是否是我们想要选择的阵营单位
            if faction_id is not None:
                if not entity.has_component(FactionComponent):
                    continue

                faction_comp = entity.get_component(FactionComponent)
                if faction_comp.faction_id != faction_id:
                    continue

            # 检查单位是否在选框内
            pos = entity.get_component(PositionComponent)
            unit = entity.get_component(UnitComponent)

            if unit and pos:
                # 假设单位有32x32的碰撞盒
                unit_rect = pygame.Rect(pos.x, pos.y, 32, 32)

                if rect.colliderect(unit_rect):
                    selected.append(entity)

        return selected

    def find_path(self, unit, target_position, map_data):
        """为单位查找到目标位置的路径（简单版本）"""
        # 这只是一个简单版本，未来可以使用A*算法实现
        # 直接设置目标，由UnitSystem处理实际移动
        unit_comp = unit.get_component(UnitComponent)
        if unit_comp:
            unit_comp.target_position = target_position
            unit_comp.is_moving = True

    def update(self, delta_time):
        """更新单位控制逻辑"""
        # 检查并更新已选择的单位集合，删除不再存在的单位
        self.selected_units = [
            unit for unit in self.selected_units if unit.id in self.world.entities
        ]

        # 更新单位组中的无效单位
        for group_num, units in self.unit_groups.items():
            self.unit_groups[group_num] = [
                unit for unit in units if unit.id in self.world.entities
            ]

        # 其他更新逻辑...
