import random
import math
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.components import (
    UnitStatsComponent,
    UnitPositionComponent,
    UnitStateComponent,
    UnitMovementComponent,
    UnitState,
)


class AIControlSystem(System):
    """人工智能控制系统，为NPC阵营提供基本AI控制"""

    def __init__(self):
        super().__init__([], priority=20)  # 优先级在战斗系统之前
        self.player_faction_id = 2  # 默认玩家为蜀国
        self.ai_factions = []  # AI控制的阵营列表
        self.target_update_interval = 3.0  # 目标更新间隔（秒）
        self.time_since_last_update = 0.0  # 上次更新后经过的时间
        self.active = True  # AI是否激活

    def initialize(self, world: World, event_manager: EventManager) -> None:
        """初始化AI控制系统"""
        self.event_manager = event_manager

        # 订阅相关事件
        self.event_manager.subscribe(
            "FACTION_SWITCHED", lambda message: self._handle_faction_switched(message)
        )

        # 默认设置：所有非玩家阵营都由AI控制
        self.ai_factions = [1, 3, 4]  # 魏国、吴国、黄巾军

    def _handle_faction_switched(self, message):
        """处理阵营切换事件"""
        new_faction_id = message.data.get("faction_id")
        if new_faction_id != self.player_faction_id:
            # 玩家切换阵营，更新AI阵营列表
            self.player_faction_id = new_faction_id
            self.ai_factions = [i for i in range(1, 5) if i != self.player_faction_id]

    def update(self, world: World, delta_time: float) -> None:
        """更新AI行为"""
        if not self.active:
            return

        # 定期更新AI决策
        self.time_since_last_update += delta_time
        if self.time_since_last_update >= self.target_update_interval:
            self.time_since_last_update = 0
            self._make_ai_decisions(world)

    def _make_ai_decisions(self, world: World) -> None:
        """为所有AI控制的单位制定决策"""
        # 获取所有单位
        units = world.get_entities_with_components(
            UnitStatsComponent, UnitPositionComponent, UnitStateComponent
        )

        # 按阵营分组单位
        faction_units = {}
        for unit in units:
            stats = world.get_component(unit, UnitStatsComponent)
            if stats:
                faction_id = stats.faction_id
                if faction_id not in faction_units:
                    faction_units[faction_id] = []
                faction_units[faction_id].append(unit)

        # 为每个AI阵营制定策略
        for faction_id in self.ai_factions:
            if faction_id in faction_units:
                ai_units = faction_units[faction_id]
                self._process_faction_units(world, ai_units, faction_units)

    def _process_faction_units(
        self, world: World, ai_units: list, faction_units: dict
    ) -> None:
        """处理一个阵营的所有单位行为"""
        # 如果没有单位，直接返回
        if not ai_units:
            return

        # 确定敌对阵营的单位
        enemy_units = []
        for faction_id, units in faction_units.items():
            if faction_id not in self.ai_factions:  # 不是AI控制的阵营就是敌人
                enemy_units.extend(units)

        # 如果没有敌人，直接返回
        if not enemy_units:
            return

        # 处理每个AI单位的行为
        for unit in ai_units:
            # 获取单位状态
            state = world.get_component(unit, UnitStateComponent)
            if not state or state.state == UnitState.DEAD:
                continue

            # 如果单位已经在攻击或移动，不做处理
            if (
                state.state in [UnitState.ATTACKING, UnitState.ROUTED]
                or state.is_engaged
            ):
                continue

            # 决定这个单位应该做什么 - 简单AI只有两种行为：攻击或移动
            action = self._decide_unit_action(world, unit, enemy_units)

            # 执行决定的行动
            if action == "attack":
                target = self._find_best_target(world, unit, enemy_units)
                if target:
                    # 发送攻击命令
                    self.event_manager.publish(
                        "ATTACK_COMMAND",
                        Message(
                            topic="ATTACK_COMMAND",
                            data_type="command",
                            data={"attacker": unit, "target": target},
                        ),
                    )
            elif action == "move":
                # 选择一个移动目标
                target_pos = self._choose_move_target(world, unit, enemy_units)
                if target_pos:
                    # 发送移动命令
                    self.event_manager.publish(
                        "MOVE_COMMAND",
                        Message(
                            topic="MOVE_COMMAND",
                            data_type="command",
                            data={
                                "unit": unit,
                                "target_x": target_pos[0],
                                "target_y": target_pos[1],
                            },
                        ),
                    )

    def _decide_unit_action(self, world: World, unit, enemy_units) -> str:
        """决定单位应该执行什么行动（攻击或移动）"""
        # 获取单位位置和属性
        unit_pos = world.get_component(unit, UnitPositionComponent)
        unit_stats = world.get_component(unit, UnitStatsComponent)

        if not unit_pos or not unit_stats:
            return "move"  # 默认移动

        # 检查是否有敌人在攻击范围内
        closest_enemy = None
        closest_dist = float("inf")

        for enemy in enemy_units:
            enemy_pos = world.get_component(enemy, UnitPositionComponent)
            if not enemy_pos:
                continue

            # 计算距离
            dx = unit_pos.x - enemy_pos.x
            dy = unit_pos.y - enemy_pos.y
            dist = math.sqrt(dx * dx + dy * dy)

            # 更新最近的敌人
            if dist < closest_dist:
                closest_dist = dist
                closest_enemy = enemy

        # 如果有敌人在攻击范围内，则攻击
        if closest_dist <= unit_stats.attack_range:
            return "attack"
        else:
            # 如果敌人很近但不在攻击范围，有75%概率移动接近，25%概率直接攻击
            if closest_dist <= unit_stats.attack_range * 2:
                return random.choice(["move", "move", "move", "attack"])
            # 否则移动
            return "move"

    def _find_best_target(self, world: World, unit, enemy_units) -> int:
        """为单位找到最佳攻击目标"""
        unit_pos = world.get_component(unit, UnitPositionComponent)
        unit_stats = world.get_component(unit, UnitStatsComponent)

        if not unit_pos or not unit_stats:
            return None

        # 初始化评分系统
        best_target = None
        best_score = -1

        for enemy in enemy_units:
            enemy_pos = world.get_component(enemy, UnitPositionComponent)
            enemy_stats = world.get_component(enemy, UnitStatsComponent)

            if not enemy_pos or not enemy_stats:
                continue

            # 计算距离
            dx = unit_pos.x - enemy_pos.x
            dy = unit_pos.y - enemy_pos.y
            dist = math.sqrt(dx * dx + dy * dy)

            # 如果敌人在攻击范围外，跳过
            if dist > unit_stats.attack_range:
                continue

            # 根据多种因素评分
            score = 0

            # 1. 距离越近越好
            score += (unit_stats.attack_range - dist) * 5

            # 2. 敌人生命值越低越好
            score += (1.0 - enemy_stats.health / enemy_stats.max_health) * 20

            # 3. 考虑单位类型的相克关系（简化版）
            if unit_stats.category == "RANGED" and enemy_stats.category == "INFANTRY":
                score += 15  # 远程攻击步兵有优势
            elif unit_stats.category == "CAVALRY" and enemy_stats.category == "RANGED":
                score += 15  # 骑兵攻击远程有优势
            elif (
                unit_stats.category == "INFANTRY" and enemy_stats.category == "CAVALRY"
            ):
                score += 15  # 步兵攻击骑兵有优势

            # 更新最佳目标
            if score > best_score:
                best_score = score
                best_target = enemy

        return best_target

    def _choose_move_target(self, world: World, unit, enemy_units) -> tuple:
        """为单位选择移动目标位置"""
        unit_pos = world.get_component(unit, UnitPositionComponent)
        unit_stats = world.get_component(unit, UnitStatsComponent)

        if not unit_pos or not unit_stats:
            return None

        # 如果没有敌人，随机移动
        if not enemy_units:
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(3, 6)
            return (
                unit_pos.x + distance * math.cos(angle),
                unit_pos.y + distance * math.sin(angle),
            )

        # 找到最近的敌人
        closest_enemy = None
        closest_dist = float("inf")

        for enemy in enemy_units:
            enemy_pos = world.get_component(enemy, UnitPositionComponent)
            if not enemy_pos:
                continue

            # 计算距离
            dx = unit_pos.x - enemy_pos.x
            dy = unit_pos.y - enemy_pos.y
            dist = math.sqrt(dx * dx + dy * dy)

            # 更新最近的敌人
            if dist < closest_dist:
                closest_dist = dist
                closest_enemy = enemy

        # 如果找到敌人，向它移动
        if closest_enemy:
            enemy_pos = world.get_component(closest_enemy, UnitPositionComponent)

            # 计算期望的距离（根据单位类型调整）
            desired_distance = 0
            if unit_stats.attack_range > 1.5:  # 远程单位
                # 远程单位希望保持在攻击范围的80%左右
                desired_distance = unit_stats.attack_range * 0.8
            else:
                # 近战单位希望直接接触
                desired_distance = 0.5

            # 计算向量从单位到敌人
            dx = enemy_pos.x - unit_pos.x
            dy = enemy_pos.y - unit_pos.y
            dist = math.sqrt(dx * dx + dy * dy)

            # 标准化向量
            if dist > 0:
                dx /= dist
                dy /= dist

            # 根据期望距离调整目标位置
            if dist > desired_distance:
                # 向敌人靠近，但保持期望距离
                move_dist = dist - desired_distance
                return (unit_pos.x + dx * move_dist, unit_pos.y + dy * move_dist)
            elif dist < desired_distance * 0.7:
                # 如果太近，稍微后退
                return (
                    unit_pos.x - dx * (desired_distance * 0.5),
                    unit_pos.y - dy * (desired_distance * 0.5),
                )

        # 没找到合适的移动目标，就随机移动
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(2, 4)
        return (
            unit_pos.x + distance * math.cos(angle),
            unit_pos.y + distance * math.sin(angle),
        )
