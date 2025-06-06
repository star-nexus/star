"""
AI系统 - 处理AI玩家的决策
"""

import random
from typing import Set, List, Tuple, Optional
from framework_v2 import System, World
from ..components import (
    Player,
    AIControlled,
    Unit,
    HexPosition,
    Movement,
    Combat,
    Health,
    GameState,
    MapData,
    Terrain,
)
from ..prefabs.config import GameConfig, TerrainType
from ..utils.hex_utils import HexMath, PathFinding


class AISystem(System):
    """AI系统 - 处理AI玩家的决策"""

    def __init__(self):
        super().__init__(required_components={Player, AIControlled})
        self.decision_timer = 0.0
        self.decision_interval = 1.0  # AI决策间隔（秒）

    def initialize(self, world: World) -> None:
        """初始化AI系统"""
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新AI系统"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or game_state.game_over or game_state.paused:
            return

        self.decision_timer += delta_time

        # 检查是否轮到AI玩家
        current_player = self._get_current_player()
        if not current_player:
            return

        ai_controlled = self.world.get_component(current_player, AIControlled)
        if not ai_controlled:
            return

        # AI决策
        if self.decision_timer >= self.decision_interval:
            self._make_ai_decisions(current_player)
            self.decision_timer = 0.0

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
                ai_units.append(unit_entity)

        if not ai_units:
            # 没有单位了，结束回合
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
        movement = self.world.get_component(unit_entity, Movement)
        combat = self.world.get_component(unit_entity, Combat)

        # 检查单位是否还能行动
        if (movement and movement.has_moved) and (combat and combat.has_attacked):
            return False

        # 寻找敌人
        enemy_target = self._find_nearest_enemy(unit_entity)
        if enemy_target:
            # 尝试攻击
            if combat and not combat.has_attacked:
                if self._try_attack(unit_entity, enemy_target):
                    return True

            # 尝试移动接近敌人
            if movement and not movement.has_moved:
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

        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            enemy_unit = self.world.get_component(entity, Unit)
            enemy_pos = self.world.get_component(entity, HexPosition)

            if enemy_unit and enemy_pos and enemy_unit.faction != unit.faction:
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
            # 执行攻击（这里需要调用战斗系统）
            combat_system = self._get_combat_system()
            if combat_system:
                return combat_system.attack(attacker_entity, target_entity)

        return False

    def _move_towards_enemy(self, unit_entity: int, enemy_entity: int) -> bool:
        """移动接近敌人"""
        position = self.world.get_component(unit_entity, HexPosition)
        enemy_pos = self.world.get_component(enemy_entity, HexPosition)
        movement = self.world.get_component(unit_entity, Movement)

        if not position or not enemy_pos or not movement:
            return False

        # 计算移动路径
        obstacles = self._get_obstacles_for_ai()

        # 寻找最佳移动位置
        best_pos = None
        best_distance = float("inf")

        # 获取移动范围内的所有位置
        movement_range = PathFinding.get_movement_range(
            (position.col, position.row), movement.current_movement, obstacles
        )

        for pos in movement_range:
            if pos == (position.col, position.row):
                continue

            distance = HexMath.hex_distance(pos, (enemy_pos.col, enemy_pos.row))
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
        movement = self.world.get_component(unit_entity, Movement)

        if not position or not movement or movement.has_moved:
            return False

        # 寻找有利地形
        best_terrain_pos = self._find_best_defensive_terrain(unit_entity)
        if best_terrain_pos and best_terrain_pos != (position.col, position.row):
            movement_system = self._get_movement_system()
            if movement_system:
                return movement_system.move_unit(unit_entity, best_terrain_pos)

        return False

    def _find_best_defensive_terrain(
        self, unit_entity: int
    ) -> Optional[Tuple[int, int]]:
        """寻找最佳防御地形"""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, Movement)

        if not position or not movement:
            return None

        obstacles = self._get_obstacles_for_ai()
        movement_range = PathFinding.get_movement_range(
            (position.col, position.row), movement.current_movement, obstacles
        )

        best_pos = None
        best_score = -1

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        for pos in movement_range:
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain:
                    # 计算地形防御价值
                    terrain_effect = GameConfig.TERRAIN_EFFECTS.get(
                        terrain.terrain_type
                    )
                    if terrain_effect:
                        score = terrain_effect.defense_bonus
                        if score > best_score:
                            best_score = score
                            best_pos = pos

        return best_pos

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
            movement = self.world.get_component(unit_entity, Movement)
            combat = self.world.get_component(unit_entity, Combat)

            if (movement and not movement.has_moved) or (
                combat and not combat.has_attacked
            ):
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

    def _get_movement_system(self):
        """获取移动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None
