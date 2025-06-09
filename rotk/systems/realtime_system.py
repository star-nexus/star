"""
实时系统 - 管理实时游戏模式的逻辑
"""

from framework_v2 import System, World
from ..components import (
    Player,
    GameState,
    Movement,
    Combat,
    Unit,
    GameModeComponent,
    Health,
)
from ..prefabs.config import GameConfig, GameMode, Faction


class RealtimeSystem(System):
    """实时系统 - 管理实时游戏模式的逻辑"""

    def __init__(self):
        super().__init__(required_components={Player}, priority=85)
        self.ai_decision_timer = 0.0
        self.ai_decision_interval = 2.0  # AI每2秒做一次决策

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        game_mode = self.world.get_singleton_component(GameModeComponent)
        game_state = self.world.get_singleton_component(GameState)

        if not game_mode or not game_mode.is_real_time():
            return

        if not game_state or game_state.game_over:
            return

        # 检查游戏结束条件
        if self._check_game_over():
            return

        # 实时恢复单位行动力
        self._regenerate_action_points(delta_time)

        # 实时AI决策更新
        self._update_ai_decisions(delta_time)

    def _check_game_over(self) -> bool:
        """检查游戏是否结束"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or game_state.game_over:
            return True

        # 检查是否有玩家没有单位了
        factions_with_units = set()
        faction_unit_counts = {}

        for entity in self.world.query().with_all(Unit, Health).entities():
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)

            # 只计算活着的单位
            if unit and health and health.current > 0:
                factions_with_units.add(unit.faction)
                faction_unit_counts[unit.faction] = (
                    faction_unit_counts.get(unit.faction, 0) + 1
                )

        # 检查是否只有在少于2个阵营有单位时才结束游戏
        if len(factions_with_units) < 2:
            game_state.game_over = True
            if factions_with_units:
                game_state.winner = list(factions_with_units)[0]

            # 记录游戏结束统计
            statistics_system = self._get_statistics_system()
            if statistics_system:
                # 可以在这里记录游戏结束的统计信息
                pass

            return True

        # 检查是否达到最大回合数
        if (
            hasattr(game_state, "max_turns")
            and game_state.turn_number >= game_state.max_turns
        ):
            game_state.game_over = True
            return True

        return False

    def _get_statistics_system(self):
        """获取统计系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _regenerate_action_points(self, delta_time: float) -> None:
        """实时恢复单位行动点数"""
        regen_rate = 0.4  # 每秒恢复的行动点数比例（增加恢复速度）

        # 恢复移动力
        for entity in self.world.query().with_component(Movement).entities():
            movement = self.world.get_component(entity, Movement)
            if movement and movement.current_movement < movement.max_movement:
                movement.current_movement = min(
                    movement.max_movement,
                    movement.current_movement
                    + movement.max_movement * regen_rate * delta_time,
                )
                # 如果移动力恢复到足够，重置已移动标志
                if movement.current_movement >= movement.max_movement * 0.7:  # 降低阈值
                    movement.has_moved = False

        # 恢复攻击能力
        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)
            if combat and combat.has_attacked:
                # 添加攻击冷却时间
                if not hasattr(combat, "attack_cooldown"):
                    combat.attack_cooldown = 2.0  # 2秒攻击冷却（减少冷却时间）
                else:
                    combat.attack_cooldown -= delta_time
                    if combat.attack_cooldown <= 0:
                        combat.has_attacked = False
                        combat.attack_cooldown = 0.0

    def _update_ai_decisions(self, delta_time: float) -> None:
        """实时模式下的AI决策更新"""
        self.ai_decision_timer += delta_time

        if self.ai_decision_timer >= self.ai_decision_interval:
            self.ai_decision_timer = 0.0

            # 触发AI系统进行决策
            # 这里可以发送事件或直接调用AI系统
            # 现在简单地让AI单位有更多机会行动
            self._boost_ai_units()

    def _boost_ai_units(self):
        """给AI单位提供额外的行动机会"""
        from ..components import AIControlled

        for entity in self.world.query().with_all(Unit, AIControlled).entities():
            movement = self.world.get_component(entity, Movement)
            combat = self.world.get_component(entity, Combat)
            health = self.world.get_component(entity, Health)

            # 只增强活着的单位
            if not health or health.current <= 0:
                continue

            # 给AI单位少量额外的行动力
            if movement and movement.current_movement < movement.max_movement:
                movement.current_movement = min(
                    movement.max_movement,
                    movement.current_movement + 0.2,  # 增加额外行动力
                )

            # 减少AI单位的攻击冷却时间
            if combat and hasattr(combat, "attack_cooldown"):
                combat.attack_cooldown = max(
                    0, combat.attack_cooldown - 0.8
                )  # 更大幅度减少冷却
