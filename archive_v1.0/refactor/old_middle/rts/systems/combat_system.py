import math
import random
from framework.ecs.system import System
from rts.components import (
    UnitComponent,
    AttackComponent,
    DefenseComponent,
    FactionComponent,
    PositionComponent,
    SpriteComponent,
)
from rts.map.tile import TileType


class CombatSystem(System):
    """
    战斗系统：处理单位间的战斗、伤害计算和战斗结果
    实现游戏中的战斗逻辑，包括攻击检测、伤害计算、战斗事件生成和死亡处理
    """

    def __init__(self, map_data=None):
        """
        初始化战斗系统

        参数:
            map_data: 地图数据引用，用于计算地形防御加成
        """
        # 系统关心的组件：攻击、防御和位置组件
        super().__init__([AttackComponent, DefenseComponent, PositionComponent])
        self.map_data = map_data  # 地图数据，用于地形加成计算
        self.combat_events = []  # 战斗事件队列（用于UI显示、音效和动画）
        self.death_callbacks = []  # 单位死亡回调函数列表，允许其他系统响应死亡事件

    def set_map_data(self, map_data):
        """
        设置地图数据引用

        参数:
            map_data: 游戏地图数据对象
        """
        self.map_data = map_data

    def update(self, delta_time):
        """
        更新战斗状态，处理攻击和伤害计算

        参数:
            delta_time: 帧间时间差（秒）
        """
        # 清除上一帧的战斗事件，准备记录新的事件
        self.combat_events.clear()

        # 处理所有具有攻击和防御组件的实体
        for attacker in self.entities:
            attack_comp = attacker.get_component(AttackComponent)

            # 跳过没有目标或不在攻击状态的实体
            if not attack_comp.is_attacking or attack_comp.target is None:
                continue

            # 降低攻击冷却时间
            if attack_comp.current_cooldown > 0:
                attack_comp.current_cooldown -= delta_time
                continue

            # 获取目标实体
            target = attack_comp.target

            # 检查目标是否还存在（可能已被销毁）
            if target.id not in self.world.entities:
                # 目标已不存在，清除攻击状态
                attack_comp.is_attacking = False
                attack_comp.target = None
                continue

            # 检查目标是否有防御组件（可以受到伤害）
            if not target.has_component(DefenseComponent):
                continue

            # 检查是否在攻击范围内
            if self._is_in_attack_range(attacker, target, attack_comp.range):
                # 执行攻击操作
                self._perform_attack(attacker, target, delta_time)

    def _perform_attack(self, attacker, target, delta_time):
        """
        执行攻击动作，计算伤害并应用效果

        参数:
            attacker: 攻击方实体
            target: 防御方实体
            delta_time: 帧间时间差（秒）
        """
        # 获取必要的组件引用
        attack_comp = attacker.get_component(AttackComponent)
        defense_comp = target.get_component(DefenseComponent)

        # 计算攻击方属性加成（例如单位类型特性）
        attack_bonus = 1.0
        if attacker.has_component(UnitComponent):
            unit_comp = attacker.get_component(UnitComponent)
            # 可以在这里添加特定单位类型的攻击加成

        # 计算地形提供的防御加成
        terrain_defense_bonus = self._calculate_terrain_defense_bonus(target)

        # 计算基础伤害
        raw_damage = attack_comp.damage * attack_bonus

        # 应用防御减伤（护甲值转换为百分比减伤）
        damage_reduction = defense_comp.armor / 100.0

        # 应用攻击类型抗性（如远程攻击抗性）
        resistance = defense_comp.resistance.get(attack_comp.attack_type, 0)

        # 计算最终伤害，考虑所有加成和减免
        final_damage = (
            raw_damage
            * (1 - damage_reduction)  # 护甲减伤
            * (1 - resistance)  # 攻击类型抗性
            * (1 - terrain_defense_bonus)  # 地形防御加成
        )

        # 确保至少造成1点伤害，避免"无伤害"攻击
        final_damage = max(1, round(final_damage))

        # 应用伤害到目标
        defense_comp.health -= final_damage

        # 记录战斗事件（用于UI显示和音效）
        self.combat_events.append(
            {
                "type": "attack",
                "attacker": attacker,
                "target": target,
                "damage": final_damage,
                "position": target.get_component(PositionComponent),
            }
        )

        # 重置攻击冷却，控制攻击频率
        attack_comp.current_cooldown = attack_comp.cooldown

        # 检查目标是否死亡（生命值降至0或以下）
        if defense_comp.health <= 0:
            self._handle_entity_death(target)
            # 清除攻击目标，停止攻击
            attack_comp.is_attacking = False
            attack_comp.target = None

    def _handle_entity_death(self, entity):
        """
        处理实体死亡逻辑

        参数:
            entity: 死亡的实体
        """
        # 记录死亡事件
        self.combat_events.append(
            {
                "type": "death",
                "entity": entity,
                "position": entity.get_component(PositionComponent),
            }
        )

        # 通知所有注册的死亡回调函数
        for callback in self.death_callbacks:
            callback(entity)

        # 添加死亡视觉效果（这里使用发光作为临时效果）
        if entity.has_component(SpriteComponent):
            sprite_comp = entity.get_component(SpriteComponent)
            sprite_comp.is_glowing = True  # 临时使用发光效果表示死亡

        # 注：实际删除实体由外部系统处理，这允许死亡动画播放完成

    def _is_in_attack_range(self, attacker, target, range_tiles):
        """
        检查目标是否在攻击范围内

        参数:
            attacker: 攻击方实体
            target: 防御方实体
            range_tiles: 攻击范围（格子数）

        返回:
            bool: 如果目标在攻击范围内则返回True
        """
        # 获取位置组件
        attacker_pos = attacker.get_component(PositionComponent)
        target_pos = target.get_component(PositionComponent)

        # 计算实体间距离（像素单位）
        dx = attacker_pos.x - target_pos.x
        dy = attacker_pos.y - target_pos.y
        distance = math.sqrt(dx * dx + dy * dy)

        # 转换攻击范围从格子数到像素（假设一个格子是32像素）
        range_pixels = range_tiles * 32

        # 判断距离是否在攻击范围内
        return distance <= range_pixels

    def _calculate_terrain_defense_bonus(self, entity):
        """
        计算地形提供的防御加成
        不同地形可以提供不同程度的防御加成

        参数:
            entity: 要计算的实体

        返回:
            float: 地形提供的防御加成（0-1之间的值）
        """
        # 如果没有地图数据或实体没有位置组件，返回0加成
        if not self.map_data or not entity.has_component(PositionComponent):
            return 0

        # 获取实体位置
        position = entity.get_component(PositionComponent)

        # 将实体像素坐标转换为地图格子坐标
        tile_x = int(position.x / 32)
        tile_y = int(position.y / 32)

        # 获取实体所在的格子
        if self.map_data.is_valid_position(tile_x, tile_y):
            tile = self.map_data.get_tile(tile_x, tile_y)
            # 返回地形防御加成
            return tile.defense_bonus

        return 0  # 默认无加成

    def add_death_callback(self, callback):
        """
        添加实体死亡时的回调函数
        允许其他系统对单位死亡做出反应

        参数:
            callback: 死亡时调用的函数，格式为 function(entity)
        """
        if callback not in self.death_callbacks:
            self.death_callbacks.append(callback)

    def remove_death_callback(self, callback):
        """
        移除实体死亡时的回调函数

        参数:
            callback: 要移除的回调函数
        """
        if callback in self.death_callbacks:
            self.death_callbacks.remove(callback)

    def get_combat_events(self):
        """
        获取战斗事件列表
        用于UI系统显示战斗效果和播放音效

        返回:
            list: 当前帧发生的战斗事件列表
        """
        return self.combat_events
