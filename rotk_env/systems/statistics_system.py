"""
统计系统 - 负责游戏数据统计和记录
严格遵守ECS规范：只处理业务逻辑，不存储数据
"""

import time
from typing import Dict, Set, Tuple, Optional, List, Any
from framework_v2 import System, World
from ..components import (
    Unit,
    Health,
    HexPosition,
    Movement,
    Combat,
    Vision,
    GameStats,
    BattleLog,
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
    GameState,
    FogOfWar,
    Terrain,
    Tile,
)
from ..prefabs.config import Faction, TerrainType


class StatisticsSystem(System):
    """统计系统 - 管理游戏统计和数据记录"""

    def __init__(self):
        super().__init__(priority=15)
        self.last_update_time = 0.0
        self.observation_interval = 1.0  # 每秒记录一次观测数据

    def initialize(self, world: World) -> None:
        """初始化统计系统"""
        self.world = world

        # 初始化统计组件
        self._initialize_statistics_components()

    def subscribe_events(self) -> None:
        """订阅事件"""
        pass

    def _initialize_statistics_components(self) -> None:
        """初始化所有统计相关组件"""
        # 游戏统计
        if not self.world.get_singleton_component(GameStats):
            stats = GameStats()
            stats.game_start_time = time.time()
            self.world.add_singleton_component(stats)

        # 游戏模式统计
        if not self.world.get_singleton_component(GameModeStatistics):
            mode_stats = GameModeStatistics()
            self.world.add_singleton_component(mode_stats)

        # 可见性追踪器
        if not self.world.get_singleton_component(VisibilityTracker):
            visibility_tracker = VisibilityTracker()
            self.world.add_singleton_component(visibility_tracker)

    def update(self, delta_time: float) -> None:
        """更新统计系统"""
        current_time = time.time()

        # 更新游戏时间
        self._update_game_time(delta_time)

        # 定期记录单位观测数据
        if current_time - self.last_update_time >= self.observation_interval:
            self._record_unit_observations()
            self._update_visibility_tracking()
            self._update_faction_statistics()
            self.last_update_time = current_time

    def _update_game_time(self, dt: float) -> None:
        """更新游戏时间"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)

        if stats:
            stats.total_game_time += dt

        if mode_stats and mode_stats.current_mode == "realtime":
            mode_stats.realtime_stats["total_game_time"] += dt

    def _record_unit_observations(self) -> None:
        """记录单位观测数据"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        current_time = time.time()

        # 为每个单位记录观测数据
        for entity in self.world.query().with_all(Unit, Health, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)
            position = self.world.get_component(entity, HexPosition)
            movement = self.world.get_component(entity, Movement)
            combat = self.world.get_component(entity, Combat)

            if not all([unit, health, position]):
                continue

            # 获取或创建观测组件
            observation = self.world.get_component(entity, UnitObservation)
            if not observation:
                observation = UnitObservation()
                self.world.add_component(entity, observation)

            # 更新观测数据
            observation.previous_position = observation.current_position
            observation.current_position = (position.col, position.row)
            observation.health_percentage = (health.current / health.maximum) * 100

            if movement:
                observation.movement_remaining = movement.current_movement
                observation.has_acted_this_turn = movement.has_moved

                # 计算移动距离
                if observation.previous_position != observation.current_position:
                    observation.total_distance_moved += 1
                    observation.movement_path.append(observation.current_position)

                    # 限制路径长度
                    if len(observation.movement_path) > 50:
                        observation.movement_path = observation.movement_path[-50:]

            if combat:
                observation.in_combat = combat.has_attacked
                if combat.has_attacked:
                    observation.last_combat_time = current_time

            # 获取地形信息
            terrain_type = self._get_terrain_at_position(position.col, position.row)
            observation.current_terrain_type = terrain_type

            # 记录到历史数据
            observation_data = {
                "entity": entity,
                "faction": unit.faction.value,
                "unit_type": unit.unit_type.value,
                "position": observation.current_position,
                "health_percentage": observation.health_percentage,
                "movement_remaining": observation.movement_remaining,
                "in_combat": observation.in_combat,
                "terrain_type": observation.current_terrain_type,
                "timestamp": stats.total_game_time,
            }

            # 添加观测记录
            stats.unit_observation_history.append(observation_data)

            # 限制历史记录数量
            if len(stats.unit_observation_history) > 10000:
                stats.unit_observation_history = stats.unit_observation_history[-5000:]

    def _get_terrain_at_position(self, col: int, row: int) -> str:
        """获取指定位置的地形类型"""
        try:
            # 尝试从地图数据中获取地形信息
            from ..components import MapData

            map_data = self.world.get_singleton_component(MapData)
            if map_data and (col, row) in map_data.tiles:
                tile_entity = map_data.tiles[(col, row)]
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain:
                    return terrain.terrain_type.value
        except:
            pass
        return "plains"  # 默认地形

    def _update_visibility_tracking(self) -> None:
        """更新可见性追踪"""
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if not visibility_tracker or not fog_of_war:
            return

        # 清空当前可见单位
        for faction in visibility_tracker.faction_visible_units:
            visibility_tracker.faction_visible_units[faction].clear()

        # 更新每个单位的可见性
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position:
                continue

            visible_to = set()
            unit_pos = (position.col, position.row)

            # 检查哪些阵营能看到这个单位
            for faction, vision_tiles in fog_of_war.faction_vision.items():
                if unit_pos in vision_tiles and faction != unit.faction:
                    visible_to.add(faction)

            # 单位自己的阵营总是能看到
            visible_to.add(unit.faction)

            # 更新可见性数据
            self._update_unit_visibility(entity, visible_to, visibility_tracker)

    def _update_unit_visibility(
        self,
        unit_entity: int,
        visible_to: Set[Faction],
        visibility_tracker: VisibilityTracker,
    ) -> None:
        """更新单位可见性数据"""
        current_time = time.time()

        # 更新可见单位映射
        for faction in visible_to:
            if faction not in visibility_tracker.faction_visible_units:
                visibility_tracker.faction_visible_units[faction] = set()
            visibility_tracker.faction_visible_units[faction].add(unit_entity)

        # 记录可见性历史
        if unit_entity not in visibility_tracker.visibility_history:
            visibility_tracker.visibility_history[unit_entity] = []

        visibility_record = {
            "timestamp": current_time,
            "visible_to": list(visible_to),
            "newly_spotted": False,
            "lost_sight": False,
        }

        visibility_tracker.visibility_history[unit_entity].append(visibility_record)

        # 限制历史记录数量
        if len(visibility_tracker.visibility_history[unit_entity]) > 100:
            visibility_tracker.visibility_history[unit_entity] = (
                visibility_tracker.visibility_history[unit_entity][-100:]
            )

        # 更新单位观测组件
        observation = self.world.get_component(unit_entity, UnitObservation)
        if observation:
            observation.is_visible_to = visible_to
            observation.last_seen_time = current_time

    def _update_faction_statistics(self) -> None:
        """更新阵营统计"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        # 为每个阵营统计领土控制
        faction_territories = {}

        # 统计每个阵营控制的单位和位置
        for entity in self.world.query().with_all(Unit, HexPosition, Health).entities():
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)

            if not unit or not health or health.current <= 0:
                continue

            faction = unit.faction

            # 初始化阵营统计
            self._initialize_faction_stats(faction, stats)

            # 统计领土（简化：每个活着的单位控制1个领土）
            faction_territories[faction] = faction_territories.get(faction, 0) + 1

        # 更新领土控制统计
        for faction, territory_count in faction_territories.items():
            if faction in stats.faction_stats:
                stats.faction_stats[faction]["territory_controlled"] = territory_count

    def _initialize_faction_stats(self, faction: Faction, stats: GameStats) -> None:
        """初始化阵营统计数据"""
        if faction not in stats.faction_stats:
            stats.faction_stats[faction] = {
                "kills": 0,
                "losses": 0,
                "damage_dealt": 0,
                "damage_taken": 0,
                "units_created": 0,
                "turns_played": 0,
                "territory_controlled": 0,
                "actions_taken": 0,
                "movement_distance": 0,
                "battles_won": 0,
                "battles_lost": 0,
            }

    # === 公共接口方法 - 供其他系统调用 ===

    def record_combat_action(
        self, attacker_entity: int, target_entity: int, damage: int, result: str
    ) -> None:
        """记录战斗行动"""
        stats = self.world.get_singleton_component(GameStats)
        battle_log = self.world.get_singleton_component(BattleLog)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)

        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        if not attacker_unit or not target_unit:
            return

        # 更新单位统计
        self._update_unit_combat_stats(attacker_entity, target_entity, damage, result)

        # 更新阵营统计
        if stats:
            self._initialize_faction_stats(attacker_unit.faction, stats)
            self._initialize_faction_stats(target_unit.faction, stats)

            stats.faction_stats[attacker_unit.faction]["damage_dealt"] += damage
            stats.faction_stats[target_unit.faction]["damage_taken"] += damage

            if result == "kill":
                stats.faction_stats[attacker_unit.faction]["kills"] += 1
                stats.faction_stats[target_unit.faction]["losses"] += 1

            # 记录战斗历史
            battle_record = {
                "attacker_faction": attacker_unit.faction.value,
                "target_faction": target_unit.faction.value,
                "damage": damage,
                "result": result,
                "attacker_entity": attacker_entity,
                "target_entity": target_entity,
                "timestamp": stats.total_game_time,
            }
            stats.battle_history.append(battle_record)

        # 记录到战况日志
        if battle_log:
            self._add_battle_log_entry(
                battle_log, attacker_unit, target_unit, damage, result
            )

        # 记录游戏模式统计
        if mode_stats:
            self._record_mode_action(mode_stats, attacker_unit.faction, "combat")

    def _update_unit_combat_stats(
        self, attacker_entity: int, target_entity: int, damage: int, result: str
    ) -> None:
        """更新单位战斗统计"""
        # 攻击者统计
        attacker_stats = self.world.get_component(attacker_entity, UnitStatistics)
        if not attacker_stats:
            attacker_stats = UnitStatistics()
            self.world.add_component(attacker_entity, attacker_stats)

        attacker_stats.attacks_made += 1
        attacker_stats.damage_dealt += damage
        attacker_stats.battles_participated += 1

        # 目标统计
        target_stats = self.world.get_component(target_entity, UnitStatistics)
        if not target_stats:
            target_stats = UnitStatistics()
            self.world.add_component(target_entity, target_stats)

        target_stats.damage_taken += damage
        target_stats.battles_participated += 1

        # 如果目标死亡
        if result == "kill":
            attacker_stats.kills += 1
            attacker_stats.battles_won += 1
            target_stats.deaths += 1
            target_stats.battles_lost += 1

    def _add_battle_log_entry(
        self,
        battle_log: BattleLog,
        attacker_unit: Unit,
        target_unit: Unit,
        damage: int,
        result: str,
    ) -> None:
        """添加战斗日志条目"""
        if result == "kill":
            message = f"{attacker_unit.faction.value}击败了{target_unit.faction.value}的{target_unit.unit_type.value}"
            log_type = "combat"
            color = (255, 100, 100)
        else:
            message = f"{attacker_unit.faction.value}对{target_unit.faction.value}造成{damage}点伤害"
            log_type = "combat"
            color = (255, 200, 100)

        battle_log.add_entry(message, log_type, attacker_unit.faction.value, color)

    def record_movement_action(
        self, entity: int, from_pos: Tuple[int, int], to_pos: Tuple[int, int]
    ) -> None:
        """记录移动行动"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # 更新单位统计
        unit_stats = self.world.get_component(entity, UnitStatistics)
        if not unit_stats:
            unit_stats = UnitStatistics()
            self.world.add_component(entity, unit_stats)

        unit_stats.moves_made += 1

        # 更新游戏统计
        stats = self.world.get_singleton_component(GameStats)
        if stats:
            self._initialize_faction_stats(unit.faction, stats)
            stats.faction_stats[unit.faction]["actions_taken"] += 1
            stats.faction_stats[unit.faction]["movement_distance"] += 1

        # 记录游戏模式统计
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        if mode_stats:
            self._record_mode_action(mode_stats, unit.faction, "movement")

    def record_turn_change(
        self, previous_faction: Optional[Faction], new_faction: Faction
    ) -> None:
        """记录回合变化"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        game_state = self.world.get_singleton_component(GameState)

        if not game_state:
            return

        # 记录回合历史
        if stats:
            turn_record = {
                "turn_number": game_state.turn_number,
                "previous_faction": (
                    previous_faction.value if previous_faction else None
                ),
                "new_faction": new_faction.value,
                "game_mode": game_state.game_mode.value,
                "timestamp": stats.total_game_time,
            }
            stats.turn_history.append(turn_record)

        # 更新游戏模式统计
        if mode_stats:
            self._handle_turn_change(mode_stats, previous_faction, new_faction)

        # 更新阵营回合统计
        if stats:
            self._initialize_faction_stats(new_faction, stats)
            stats.faction_stats[new_faction]["turns_played"] += 1

    def _record_mode_action(
        self, mode_stats: GameModeStatistics, faction: Faction, action_type: str
    ) -> None:
        """记录游戏模式行动"""
        current_time = time.time()

        if mode_stats.current_mode == "turn_based":
            mode_stats.actions_this_turn += 1
        else:  # realtime
            # 更新每分钟行动数
            if current_time - mode_stats.last_action_time > 60:
                mode_stats.actions_this_minute = 0
            mode_stats.actions_this_minute += 1

            # 更新实时统计
            if faction not in mode_stats.realtime_stats["faction_activity"]:
                mode_stats.realtime_stats["faction_activity"][faction] = 0
            mode_stats.realtime_stats["faction_activity"][faction] += 1

            mode_stats.realtime_stats["action_frequency"].append(
                {
                    "timestamp": current_time,
                    "faction": faction,
                    "action_type": action_type,
                }
            )

        mode_stats.last_action_time = current_time

    def _handle_turn_change(
        self,
        mode_stats: GameModeStatistics,
        previous_faction: Optional[Faction],
        new_faction: Faction,
    ) -> None:
        """处理回合变化的统计"""
        if mode_stats.current_mode == "turn_based":
            # 结束前一个回合
            if previous_faction and mode_stats.current_turn_start_time > 0:
                turn_duration = time.time() - mode_stats.current_turn_start_time

                # 更新统计
                mode_stats.turn_based_stats["total_turns"] += 1
                mode_stats.turn_based_stats["turn_durations"].append(turn_duration)

                if (
                    previous_faction
                    not in mode_stats.turn_based_stats["faction_turn_times"]
                ):
                    mode_stats.turn_based_stats["faction_turn_times"][
                        previous_faction
                    ] = []
                mode_stats.turn_based_stats["faction_turn_times"][
                    previous_faction
                ].append(turn_duration)

                # 更新平均值
                durations = mode_stats.turn_based_stats["turn_durations"]
                mode_stats.turn_based_stats["average_turn_duration"] = sum(
                    durations
                ) / len(durations)
                mode_stats.turn_based_stats["longest_turn"] = max(durations)
                mode_stats.turn_based_stats["shortest_turn"] = min(durations)

                # 记录本回合行动数
                turn_num = mode_stats.turn_based_stats["total_turns"]
                mode_stats.turn_based_stats["actions_per_turn"][
                    turn_num
                ] = mode_stats.actions_this_turn

            # 开始新回合
            mode_stats.current_turn_start_time = time.time()
            mode_stats.actions_this_turn = 0

            if new_faction not in mode_stats.turn_based_stats["faction_turn_times"]:
                mode_stats.turn_based_stats["faction_turn_times"][new_faction] = []

    # === 数据查询方法 ===

    def get_detailed_statistics(self) -> Dict:
        """获取详细统计信息"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)

        result = {
            "game_stats": {},
            "mode_stats": {},
            "visibility_stats": {},
            "unit_stats": {},
        }

        if stats:
            result["game_stats"] = {
                "total_game_time": stats.total_game_time,
                "faction_summaries": {
                    faction.value: self._get_faction_summary(faction, stats)
                    for faction in stats.faction_stats.keys()
                },
                "battle_count": len(stats.battle_history),
                "turn_count": len(stats.turn_history),
                "observation_count": len(stats.unit_observation_history),
            }

        if mode_stats:
            result["mode_stats"] = self._get_performance_metrics(mode_stats)

        if visibility_tracker:
            result["visibility_stats"] = {
                "total_units_tracked": len(visibility_tracker.visibility_history),
                "faction_visible_counts": {
                    faction.value: len(units)
                    for faction, units in visibility_tracker.faction_visible_units.items()
                },
            }

        # 收集单位统计
        result["unit_stats"] = self._collect_unit_statistics()

        return result

    def _get_faction_summary(self, faction: Faction, stats: GameStats) -> Dict:
        """获取阵营统计摘要"""
        if faction not in stats.faction_stats:
            return {}

        faction_stats = stats.faction_stats[faction].copy()
        faction_stats["kd_ratio"] = faction_stats["kills"] / max(
            1, faction_stats["losses"]
        )
        faction_stats["damage_ratio"] = faction_stats["damage_dealt"] / max(
            1, faction_stats["damage_taken"]
        )
        faction_stats["win_rate"] = faction_stats["battles_won"] / max(
            1, faction_stats["battles_won"] + faction_stats["battles_lost"]
        )
        return faction_stats

    def _get_performance_metrics(self, mode_stats: GameModeStatistics) -> Dict:
        """获取性能指标"""
        if mode_stats.current_mode == "turn_based":
            return {
                "mode": "turn_based",
                "avg_turn_duration": mode_stats.turn_based_stats[
                    "average_turn_duration"
                ],
                "total_turns": mode_stats.turn_based_stats["total_turns"],
                "actions_per_turn": mode_stats.actions_this_turn,
                "efficiency": mode_stats.actions_this_turn
                / max(1, mode_stats.turn_based_stats["average_turn_duration"]),
            }
        else:
            return {
                "mode": "realtime",
                "game_time": mode_stats.realtime_stats["total_game_time"],
                "actions_per_minute": mode_stats.actions_this_minute,
                "total_actions": sum(
                    mode_stats.realtime_stats["faction_activity"].values()
                ),
                "activity_level": (
                    "high"
                    if mode_stats.actions_this_minute > 10
                    else "medium" if mode_stats.actions_this_minute > 5 else "low"
                ),
            }

    def _collect_unit_statistics(self) -> Dict:
        """收集单位统计信息"""
        unit_stats_summary = {}
        for entity in self.world.query().with_all(Unit, UnitStatistics).entities():
            unit = self.world.get_component(entity, Unit)
            unit_stats = self.world.get_component(entity, UnitStatistics)

            if unit and unit_stats:
                faction_key = unit.faction.value
                if faction_key not in unit_stats_summary:
                    unit_stats_summary[faction_key] = {
                        "total_kills": 0,
                        "total_damage": 0,
                        "total_moves": 0,
                        "total_battles": 0,
                        "unit_count": 0,
                    }

                faction_summary = unit_stats_summary[faction_key]
                faction_summary["total_kills"] += unit_stats.kills
                faction_summary["total_damage"] += unit_stats.damage_dealt
                faction_summary["total_moves"] += unit_stats.moves_made
                faction_summary["total_battles"] += unit_stats.battles_participated
                faction_summary["unit_count"] += 1

        return unit_stats_summary

    def get_unit_visibility_summary(self, unit_entity: int) -> Dict:
        """获取单位可见性摘要"""
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)
        if (
            not visibility_tracker
            or unit_entity not in visibility_tracker.visibility_history
        ):
            return {}

        history = visibility_tracker.visibility_history[unit_entity]
        if not history:
            return {}

        total_time = (
            history[-1]["timestamp"] - history[0]["timestamp"]
            if len(history) > 1
            else 0
        )
        visible_time = 0
        sight_changes = 0

        for i, record in enumerate(history):
            if record["visible_to"]:
                if i < len(history) - 1:
                    visible_time += history[i + 1]["timestamp"] - record["timestamp"]

            if i > 0 and len(record["visible_to"]) != len(history[i - 1]["visible_to"]):
                sight_changes += 1

        return {
            "total_time": total_time,
            "visible_time": visible_time,
            "visibility_ratio": visible_time / max(1, total_time),
            "sight_changes": sight_changes,
            "currently_visible_to": history[-1]["visible_to"] if history else [],
        }
