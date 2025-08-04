"""
AI系统 - 处理AI玩家的决策（按规则手册v1.2）
"""

import random
from typing import Set, List, Tuple, Optional
from framework import System, World
from ..components import (
    Player,
    AIControlled,
    Unit,
    HexPosition,
    MovementPoints,
    Combat,
    UnitCount,
    UnitStatus,
    GameState,
    MapData,
    Terrain,
    GameModeComponent,
    ActionPoints,
)
from ..prefabs.config import GameConfig, TerrainType, ActionType
from ..utils.hex_utils import HexMath, PathFinding


class AISystem(System):
    """AI系统 - 处理AI玩家的决策"""

    def __init__(self):
        super().__init__(required_components={Player, AIControlled})
        self.decision_timer = 0.0
        self.decision_interval = 1.0  # AI决策间隔（秒）
        self.debug_timer = 0.0  # 用于调试输出
        self.debug_interval = 5.0  # 每5秒输出一次调试信息
        self.unit_last_action = {}  # 记录每个单位的最后行动时间

    def initialize(self, world: World) -> None:
        """初始化AI系统"""
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新AI系统"""
        game_state = self.world.get_singleton_component(GameState)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not game_state or game_state.game_over or game_state.paused:
            return

        # 检查游戏模式
        is_realtime = game_mode and game_mode.is_real_time()

        self.decision_timer += delta_time
        self.debug_timer += delta_time

        # 在实时模式下，AI更频繁地做决策
        decision_interval = 0.3 if is_realtime else self.decision_interval

        if self.decision_timer >= decision_interval:
            if is_realtime:
                # 实时模式：所有AI玩家同时行动
                self._make_realtime_ai_decisions()
            else:
                # 回合制模式：只有当前玩家行动
                current_player = self._get_current_player()
                if current_player:
                    ai_controlled = self.world.get_component(
                        current_player, AIControlled
                    )
                    if ai_controlled:
                        self._make_ai_decisions(current_player)

            self.decision_timer = 0.0

        # 调试输出
        if is_realtime and self.debug_timer >= self.debug_interval:
            self._debug_ai_status()
            self.debug_timer = 0.0

    def _get_current_player(self) -> Optional[int]:
        """获取当前玩家实体"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return None

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == game_state.current_player:
                return entity

        return None

    def _make_ai_decisions(self, player_entity: int):
        """AI决策逻辑"""
        player = self.world.get_component(player_entity, Player)
        if not player:
            return

        # 获取AI控制的所有单位
        ai_units = []
        for unit_entity in player.units:
            if self.world.has_component(unit_entity, Unit):
                unit_count = self.world.get_component(unit_entity, UnitCount)
                # 只考虑还有人数的单位
                if unit_count and unit_count.current_count > 0:
                    ai_units.append(unit_entity)

        if not ai_units:
            # 没有有效单位了，结束回合
            self._end_ai_turn()
            return

        # 为每个单位制定策略
        actions_taken = 0
        for unit_entity in ai_units:
            if self._execute_unit_strategy(unit_entity):
                actions_taken += 1

        # 如果所有单位都执行了行动，结束回合
        if actions_taken == 0 or self._all_units_exhausted(ai_units):
            self._end_ai_turn()

    def _execute_unit_strategy(self, unit_entity: int) -> bool:
        """执行单位策略"""
        import time

        action_points = self.world.get_component(unit_entity, ActionPoints)
        movement = self.world.get_component(unit_entity, MovementPoints)
        combat = self.world.get_component(unit_entity, Combat)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        # 检查单位是否存活且有足够人数
        if not unit_count or unit_count.current_count <= 0:
            return False

        # 检查是否被残破（人数<=10%）
        if unit_count.is_decimated():
            return False

        # 检查是否有行动力
        if not action_points or action_points.current_ap <= 0:
            return False

        # 在实时模式下添加单位行动冷却
        is_realtime = game_mode and game_mode.is_real_time()
        if is_realtime:
            current_time = time.time()
            last_action_time = self.unit_last_action.get(unit_entity, 0)

            # 每个单位至少间隔1秒才能执行下一个行动
            if current_time - last_action_time < 1.0:
                return False

            can_move = movement and movement.current_mp > 0
            can_attack = combat and not combat.has_attacked
            if not can_move and not can_attack:
                return False
        else:
            # 回合制模式：检查是否已经行动过
            if (movement and movement.has_moved) and (combat and combat.has_attacked):
                return False

        # 记录行动时间
        if is_realtime:
            self.unit_last_action[unit_entity] = time.time()

        # 寻找敌人
        enemy_target = self._find_nearest_enemy(unit_entity)
        if enemy_target:
            # 计算与敌人的距离
            attacker_pos = self.world.get_component(unit_entity, HexPosition)
            target_pos = self.world.get_component(enemy_target, HexPosition)

            if attacker_pos and target_pos:
                distance = HexMath.hex_distance(
                    (attacker_pos.col, attacker_pos.row),
                    (target_pos.col, target_pos.row),
                )

                # 优先级1：如果在攻击范围内，尝试攻击
                if (
                    combat
                    and not combat.has_attacked
                    and action_points.can_perform_action(ActionType.ATTACK)
                    and distance <= combat.attack_range
                ):
                    if self._try_attack(unit_entity, enemy_target):
                        return True

                # 优先级2：如果距离适中(2-3格)，优先执行防御策略(占领、工事等)
                if 2 <= distance <= 3:
                    if self._execute_defensive_strategy(unit_entity):
                        return True

                # 优先级3：如果距离太远，移动接近敌人
                if (
                    movement
                    and action_points.can_perform_action(ActionType.MOVE)
                    and distance > 1
                    and (
                        (is_realtime and movement.current_mp > 0)
                        or (not is_realtime and not movement.has_moved)
                    )
                ):
                    if self._move_towards_enemy(unit_entity, enemy_target):
                        return True

        # 没有找到敌人，执行防御策略
        return self._execute_defensive_strategy(unit_entity)

    def _find_nearest_enemy(self, unit_entity: int) -> Optional[int]:
        """寻找最近的敌人"""
        unit = self.world.get_component(unit_entity, Unit)
        position = self.world.get_component(unit_entity, HexPosition)

        if not unit or not position:
            return None

        nearest_enemy = None
        min_distance = float("inf")

        for entity in (
            self.world.query().with_all(Unit, HexPosition, UnitCount).entities()
        ):
            enemy_unit = self.world.get_component(entity, Unit)
            enemy_pos = self.world.get_component(entity, HexPosition)
            enemy_count = self.world.get_component(entity, UnitCount)

            if (
                enemy_unit
                and enemy_pos
                and enemy_count
                and enemy_unit.faction != unit.faction
                and enemy_count.current_count > 0
            ):

                distance = HexMath.hex_distance(
                    (position.col, position.row), (enemy_pos.col, enemy_pos.row)
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_enemy = entity

        return nearest_enemy

    def _try_attack(self, attacker_entity: int, target_entity: int) -> bool:
        """尝试攻击"""
        # 检查攻击范围
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        combat = self.world.get_component(attacker_entity, Combat)

        if not attacker_pos or not target_pos or not combat:
            return False

        distance = HexMath.hex_distance(
            (attacker_pos.col, attacker_pos.row), (target_pos.col, target_pos.row)
        )

        if distance <= combat.attack_range:
            # 执行攻击（调用战斗系统）
            combat_system = self._get_combat_system()
            if combat_system:
                return combat_system.attack(attacker_entity, target_entity)

        return False

    def _move_towards_enemy(self, unit_entity: int, enemy_entity: int) -> bool:
        """移动接近敌人"""
        position = self.world.get_component(unit_entity, HexPosition)
        enemy_pos = self.world.get_component(enemy_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit_count = self.world.get_component(unit_entity, UnitCount)

        if not all([position, enemy_pos, movement, unit_count]):
            return False

        # 计算有效移动力
        effective_movement = movement.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)
        enemy_target_pos = (enemy_pos.col, enemy_pos.row)

        # 获取考虑地形消耗的可到达位置
        reachable_positions = self._get_reachable_positions_with_terrain_cost(
            current_pos, effective_movement
        )

        if not reachable_positions:
            return False

        # 寻找最佳移动位置（最接近敌人的位置）
        best_pos = None
        best_distance = float("inf")

        for pos, cost in reachable_positions.items():
            if pos == current_pos:
                continue

            distance = HexMath.hex_distance(pos, enemy_target_pos)
            if distance < best_distance:
                best_distance = distance
                best_pos = pos

        if best_pos:
            # 执行移动
            movement_system = self._get_movement_system()
            if movement_system:
                return movement_system.move_unit(unit_entity, best_pos)

        return False

    def _execute_defensive_strategy(self, unit_entity: int) -> bool:
        """执行防御策略"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        action_points = self.world.get_component(unit_entity, ActionPoints)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not all([position, movement, action_points]):
            return False

        is_realtime = game_mode and game_mode.is_real_time()

        # 优先级1：尝试占领重要地块（城市或未占领的地块）
        if action_points.can_perform_action(ActionType.OCCUPY):
            if self._try_occupy_territory(unit_entity):
                return True

        # 优先级2：尝试建设工事（如果已占领且未建设工事）
        if action_points.can_perform_action(ActionType.FORTIFY):
            if self._try_build_fortification(unit_entity):
                return True

        # 优先级3：尝试驻扎（如果在合适地形）
        if action_points.can_perform_action(ActionType.GARRISON):
            action_system = self._get_action_system()
            if action_system and action_system.perform_garrison(unit_entity):
                return True

        # 优先级4：移动到更好的位置（但在实时模式下降低移动频率）
        should_move = False
        if is_realtime:
            # 实时模式：只有当移动力足够多时才移动，避免频繁移动
            should_move = (
                movement.current_mp >= movement.max_mp * 0.8 and not movement.has_moved
            )
        else:
            # 回合制模式：按原逻辑
            should_move = not movement.has_moved

        if should_move and action_points.can_perform_action(ActionType.MOVE):
            best_terrain_pos = self._find_best_defensive_terrain(unit_entity)
            if best_terrain_pos and best_terrain_pos != (position.col, position.row):
                movement_system = self._get_movement_system()
                if movement_system:
                    return movement_system.move_unit(unit_entity, best_terrain_pos)

        # 最后选择待命
        if action_points.can_perform_action(ActionType.REST):
            action_system = self._get_action_system()
            if action_system and action_system.perform_wait(unit_entity):
                return True

        return False

    def _find_best_defensive_terrain(
        self, unit_entity: int
    ) -> Optional[Tuple[int, int]]:
        """寻找最佳防御地形"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        unit = self.world.get_component(unit_entity, Unit)

        if not all([position, movement, unit_count, unit]):
            return None

        effective_movement = movement.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)

        # 获取考虑地形消耗的可到达位置
        reachable_positions = self._get_reachable_positions_with_terrain_cost(
            current_pos, effective_movement
        )

        best_pos = None
        best_score = -1

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        for pos, cost in reachable_positions.items():
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)

                # 导入TerritoryControl组件
                from ..components import TerritoryControl

                territory_control = self.world.get_component(
                    tile_entity, TerritoryControl
                )

                if terrain:
                    # 计算地形防御价值
                    from ..prefabs.config import GameConfig

                    score = 0
                    terrain_effect = GameConfig.TERRAIN_EFFECTS.get(
                        terrain.terrain_type
                    )
                    if terrain_effect:
                        score += terrain_effect.defense_bonus

                    # 城市地形额外加分
                    if terrain.terrain_type == TerrainType.CITY:
                        score += 10  # 城市有很高的战略价值

                    # 己方控制的地块加分
                    if (
                        territory_control
                        and territory_control.controlling_faction == unit.faction
                    ):
                        score += 5
                        # 有工事的地块额外加分
                        score += territory_control.fortification_level * 3

                    # 未被占领的重要地形加分
                    elif not territory_control and terrain.terrain_type in [
                        TerrainType.CITY,
                        TerrainType.HILL,
                    ]:
                        score += 8  # 未占领的重要地形优先占领

                    if score > best_score:
                        best_score = score
                        best_pos = pos

        return best_pos

    def _try_occupy_territory(self, unit_entity: int) -> bool:
        """尝试占领当前位置的地块"""
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not unit:
            return False

        current_pos = (position.col, position.row)

        # 获取当前地块
        map_data = self.world.get_singleton_component(MapData)
        if not map_data or current_pos not in map_data.tiles:
            return False

        tile_entity = map_data.tiles[current_pos]
        terrain = self.world.get_component(tile_entity, Terrain)

        # 检查是否需要占领
        should_capture = False

        # 导入TerritoryControl组件
        from ..components import TerritoryControl

        territory_control = self.world.get_component(tile_entity, TerritoryControl)

        if not territory_control:
            # 未被占领的地块，优先占领
            should_capture = True
        elif territory_control.controlling_faction != unit.faction:
            # 敌方占领的地块，需要夺取
            should_capture = True
        elif (
            terrain
            and terrain.terrain_type == TerrainType.CITY
            and territory_control.controlling_faction != unit.faction
        ):
            # 敌方城市，高优先级目标
            should_capture = True

        if should_capture:
            # 执行占领行动
            territory_system = self._get_territory_system()
            if territory_system:
                return territory_system.start_capture(unit_entity, current_pos)

        return False

    def _try_build_fortification(self, unit_entity: int) -> bool:
        """尝试在当前位置建设工事"""
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not unit:
            return False

        current_pos = (position.col, position.row)

        # 获取当前地块
        map_data = self.world.get_singleton_component(MapData)
        if not map_data or current_pos not in map_data.tiles:
            return False

        tile_entity = map_data.tiles[current_pos]

        # 导入TerritoryControl组件
        from ..components import TerritoryControl

        territory_control = self.world.get_component(tile_entity, TerritoryControl)

        # 只有在己方控制的地块上才能建设工事
        if (
            not territory_control
            or territory_control.controlling_faction != unit.faction
        ):
            return False

        # 检查是否已经有最大等级的工事
        max_fortification_level = 3  # 最大工事等级
        if territory_control.fortification_level >= max_fortification_level:
            return False

        # 检查是否值得建设工事（基于战略价值）
        if self._should_build_fortification(tile_entity, territory_control):
            # 执行工事建设
            territory_system = self._get_territory_system()
            if territory_system:
                return territory_system.build_fortification(unit_entity, current_pos)

        return False

    def _should_build_fortification(self, tile_entity: int, territory_control) -> bool:
        """判断是否应该建设工事"""
        terrain = self.world.get_component(tile_entity, Terrain)

        # 城市地块优先建设工事
        if terrain and terrain.terrain_type == TerrainType.CITY:
            return True

        # 已完全占领的地块值得建设工事
        if territory_control.capture_progress >= 1.0:
            return True

        # 边境地块（有敌人附近）值得建设工事
        position = self.world.get_component(tile_entity, HexPosition)
        if position and self._is_border_position(
            (position.col, position.row), territory_control.controlling_faction
        ):
            return True

        return False

    def _is_border_position(self, pos: Tuple[int, int], current_faction) -> bool:
        """检查位置是否是边境（附近有敌方单位或敌方控制的地块）"""
        # 检查周围是否有敌方单位
        for neighbor_pos in HexMath.hex_neighbors(*pos):
            # 检查是否有敌方单位
            for entity in self.world.query().with_all(Unit, HexPosition).entities():
                unit_pos = self.world.get_component(entity, HexPosition)
                unit = self.world.get_component(entity, Unit)
                if (
                    unit_pos
                    and unit
                    and (unit_pos.col, unit_pos.row) == neighbor_pos
                    and unit.faction != current_faction
                ):
                    return True

        return False

    def _get_territory_system(self):
        """获取领土系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None

    def _get_obstacles_for_ai(self) -> Set[Tuple[int, int]]:
        """获取AI寻路的障碍物"""
        obstacles = set()

        # 添加其他单位的位置
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        return obstacles

    def _all_units_exhausted(self, units: List[int]) -> bool:
        """检查所有单位是否都无法行动"""
        for unit_entity in units:
            action_points = self.world.get_component(unit_entity, ActionPoints)

            if action_points and action_points.current_ap > 0:
                return False

        return True

    def _end_ai_turn(self):
        """结束AI回合"""
        turn_system = self._get_turn_system()
        if turn_system:
            turn_system.end_turn()

    def _get_combat_system(self):
        """获取战斗系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_reachable_positions_with_terrain_cost(
        self, start_pos: Tuple[int, int], max_movement: int
    ) -> dict:
        """获取考虑地形消耗的可到达位置
        返回：{position: total_cost}
        """
        reachable = {}
        visited = set()
        queue = [(start_pos, 0)]  # (position, total_cost)

        while queue:
            current_pos, current_cost = queue.pop(0)

            if current_pos in visited:
                continue

            visited.add(current_pos)
            reachable[current_pos] = current_cost

            # 探索邻居
            for neighbor in HexMath.hex_neighbors(*current_pos):
                if neighbor in visited:
                    continue

                # 检查是否有障碍物
                if self._is_position_blocked(neighbor):
                    continue

                # 计算移动到该格的地形消耗
                terrain_cost = self._get_terrain_movement_cost(neighbor)
                new_cost = current_cost + terrain_cost

                # 如果移动消耗超过限制，跳过
                if new_cost > max_movement:
                    continue

                queue.append((neighbor, new_cost))

        return reachable

    def _get_terrain_movement_cost(self, pos: Tuple[int, int]) -> int:
        """获取指定位置的地形移动消耗"""
        from ..prefabs.config import GameConfig

        # 获取地形组件
        for entity in self.world.get_entities_with_component(Terrain):
            terrain = self.world.get_component(entity, Terrain)
            terrain_pos = self.world.get_component(entity, HexPosition)

            if terrain_pos and (terrain_pos.col, terrain_pos.row) == pos:
                terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain.terrain_type)
                if terrain_effect:
                    return terrain_effect.movement_cost
                break

        # 默认平原消耗
        return 1

    def _is_position_blocked(self, pos: Tuple[int, int]) -> bool:
        """检查位置是否被阻挡"""
        # 检查是否有其他单位
        for entity in self.world.get_entities_with_component(Unit):
            unit_pos = self.world.get_component(entity, HexPosition)
            if unit_pos and (unit_pos.col, unit_pos.row) == pos:
                return True

        # 检查是否是水域（movement_cost=999表示不可通过）
        terrain_cost = self._get_terrain_movement_cost(pos)
        if terrain_cost >= 999:
            return True

        return False

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _get_action_system(self):
        """获取行动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _make_realtime_ai_decisions(self):
        """实时模式AI决策逻辑"""
        # 获取所有AI玩家
        ai_players = []
        for entity in self.world.query().with_all(Player, AIControlled).entities():
            ai_players.append(entity)

        # 为每个AI玩家执行决策
        for player_entity in ai_players:
            self._make_ai_decisions(player_entity)

    def _debug_ai_status(self):
        """调试AI状态"""
        print("=== AI Status Debug ===")

        # 统计AI单位状态
        ai_unit_count = 0
        active_ai_units = 0

        for entity in self.world.query().with_all(Unit, AIControlled).entities():
            ai_unit_count += 1
            unit = self.world.get_component(entity, Unit)
            movement = self.world.get_component(entity, MovementPoints)
            combat = self.world.get_component(entity, Combat)
            unit_count = self.world.get_component(entity, UnitCount)
            action_points = self.world.get_component(entity, ActionPoints)

            if unit_count and unit_count.current_count > 0:
                can_move = movement and movement.current_mp > 0
                can_attack = combat and not combat.has_attacked
                has_ap = action_points and action_points.current_ap > 0

                if (can_move or can_attack) and has_ap:
                    active_ai_units += 1
                    print(
                        f"AI Unit {entity}: Faction={unit.faction}, Count={unit_count.current_count}, "
                        f"Movement={movement.current_mp}/{movement.max_mp}, "
                        f"AP={action_points.current_ap}/{action_points.max_ap}, "
                        f"CanAttack={can_attack}"
                    )

        print(f"Total AI units: {ai_unit_count}, Active AI units: {active_ai_units}")
        print("======================")

    def _get_movement_system(self):
        """获取移动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None
