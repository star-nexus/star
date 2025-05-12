import pygame
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum, auto
from framework.ecs.system import System
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger
from framework.engine.events import EventType, EventMessage
from game.components import UnitComponent, UnitState, UnitType
from game.components import MapComponent, TileComponent, TerrainType
from game.components.status.battle_stats_component import BattleStatsComponent
from game.utils.game_types import ViewMode


class GameStatsSystem(System):
    """游戏状态统计系统，用于收集和分析游戏中的各种统计数据。"""

    def __init__(self, priority: int = 5):
        """初始化游戏状态统计系统。"""
        super().__init__(required_components=[], priority=priority)
        self.logger = get_logger(self.__class__.__name__)

        # 游戏状态数据
        self.unit_counts = {}  # 按阵营统计的单位数量
        self.event_stats = {
            "kills": {},  # 击杀统计
            "kills_by_player": {},  # 按玩家统计的击杀数
            "damage": {},  # 伤害统计
            "damage_by_player": {},  # 按玩家统计的伤害
        }

        # 游戏结束状态
        self.game_over = False
        self.winner = None

        # 战场统计组件
        self.battlefield_stats_entity = None
        self.battlefield_stats_component = None

        # 视图模式
        self.view_mode = ViewMode.GLOBAL

        # 可见单位集合（用于玩家视角模式）
        self.visible_units = set()

    def initialize(self, context):
        """初始化系统。"""
        self.context = context
        self.logger.info("初始化游戏状态统计系统")
        self.subscribe_events()

        # 创建战场统计组件
        # self.create_battlefield_stats_component()

    def subscribe_events(self):
        # 注册事件处理器
        self.context.event_manager.subscribe(
            EventType.UNIT_KILLED, self._handle_unit_killed
        )
        self.context.event_manager.subscribe(
            EventType.UNIT_ATTACKED, self._handle_damage_dealt
        )
        self.context.event_manager.subscribe(
            EventType.UNIT_MOVED, self._handle_unit_moved
        )

    def update_current_stats(self):
        """更新当前游戏统计数据。"""
        # 重置单位计数
        self.unit_counts = {}

        # 统计各阵营单位数量
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            faction = unit.faction
            if faction not in self.unit_counts:
                self.unit_counts[faction] = 0
            self.unit_counts[faction] += 1
        # self.logger.msg(f"当前单位数量: {self.unit_counts}")

    def record_kill(self, killer_id, killed_id):
        """记录击杀事件。"""
        # 初始化数据结构
        if killer_id not in self.event_stats["kills"]:
            self.event_stats["kills"][killer_id] = {}

        if killed_id not in self.event_stats["kills"][killer_id]:
            self.event_stats["kills"][killer_id][killed_id] = 0

        # 记录击杀
        self.event_stats["kills"][killer_id][killed_id] += 1

        # 按玩家统计击杀数
        if killer_id not in self.event_stats["kills_by_player"]:
            self.event_stats["kills_by_player"][killer_id] = {}

        if killed_id not in self.event_stats["kills_by_player"][killer_id]:
            self.event_stats["kills_by_player"][killer_id][killed_id] = 0

        self.event_stats["kills_by_player"][killer_id][killed_id] += 1

    def record_damage(self, attacker_id, target_id, damage):
        """记录伤害事件。"""
        # 初始化数据结构
        if attacker_id not in self.event_stats["damage"]:
            self.event_stats["damage"][attacker_id] = {}

        if target_id not in self.event_stats["damage"][attacker_id]:
            self.event_stats["damage"][attacker_id][target_id] = 0

        # 记录伤害
        self.event_stats["damage"][attacker_id][target_id] += damage

        # 按玩家统计伤害
        if attacker_id not in self.event_stats["damage_by_player"]:
            self.event_stats["damage_by_player"][attacker_id] = {}

        if target_id not in self.event_stats["damage_by_player"][attacker_id]:
            self.event_stats["damage_by_player"][attacker_id][target_id] = 0

        self.event_stats["damage_by_player"][attacker_id][target_id] += damage

    def set_view_mode(self, mode: ViewMode):
        """设置视图模式。"""
        self.view_mode = mode

    def set_visible_units(self, visible_units: Set[Entity]):
        """设置可见单位集合。"""
        self.visible_units = visible_units

    def update(self, delta_time: float):
        """更新游戏状态统计系统。"""
        if not self.is_enabled():
            return

        # 更新统计数据
        self.update_current_stats()

        # 更新战场统计数据
        self.update_battlefield_stats()

        # 检查游戏结束条件
        self.check_game_over()

    def _handle_unit_moved(self, event: EventMessage):
        """处理单位移动事件，用于跟踪调动情况。"""
        entity = event.data.get("entity")
        target_x = event.data.get("target_x")
        target_y = event.data.get("target_y")

        if entity and target_x is not None and target_y is not None:
            unit_comp = self.context.get_component(entity, UnitComponent)
            if unit_comp:
                # 更新战场统计组件中的调动情况
                # if self.battlefield_stats_component:
                faction = unit_comp.faction

                # 初始化调动情况数据结构
                # if faction not in self.battlefield_stats_component.transfer_situation:
                #     self.battlefield_stats_component.transfer_situation[faction] = []

                # 记录调动事件
                # movement = {
                #     "unit_type": unit_comp.unit_type.name,
                #     "from": (unit_comp.position_x, unit_comp.position_y),
                #     "to": (target_x, target_y),
                #     "distance": abs(target_x - unit_comp.position_x)
                #     + abs(target_y - unit_comp.position_y),
                # }
                self.logger.msg(
                    f"阵营{faction}的{unit_comp.name}(ID:{entity}) 移动到 ({target_x}, {target_y})"
                )

                for entity, (stat_comp,) in self.context.with_all(
                    BattleStatsComponent
                ).iter_components(BattleStatsComponent):
                    if stat_comp.faction == faction:
                        stat_comp.my_transfer_situation[
                            f"阵营{unit_comp.faction}{unit_comp.name}(ID:{entity})"
                        ] = f"移动到 ({target_x}, {target_y})"
                    else:
                        stat_comp.enemy_transfer_situation[
                            f"阵营{unit_comp.faction}{unit_comp.name}(ID:{entity})"
                        ] = f"移动到 ({target_x}, {target_y})"

                # 添加到调动记录列表
                # self.battlefield_stats_component.transfer_situation[faction].append(
                #     movement
                # )

                # 限制列表长度，只保留最近的10条记录
                # if (
                #     len(self.battlefield_stats_component.transfer_situation[faction])
                #     > 10
                # ):
                #     self.battlefield_stats_component.transfer_situation[faction].pop(0)

    def _handle_unit_killed(self, event: EventMessage):
        """处理单位被击杀事件。"""
        killer_entity = event.data.get("killer")
        killed_entity = event.data.get("target")

        if killer_entity and killed_entity:
            killer_comp = self.context.get_component(killer_entity, UnitComponent)
            killed_comp = self.context.get_component(killed_entity, UnitComponent)

            if killer_comp and killed_comp:
                # killer_owner_id = killer_comp.owner_id
                # killed_owner_id = killed_comp.owner_id
                killer_faction = killer_comp.faction
                killed_faction = killed_comp.faction

                self.record_kill(killer_faction, killed_faction)
                self.logger.msg(
                    f"阵营{killer_faction}的{killer_comp.name}(ID:{killer_entity}) 击杀 阵营{killed_faction}的{killed_comp.name}(ID:{killed_entity})"
                )

                # 更新战场统计组件中的伤亡情况
                for entity, (stat_comp,) in self.context.with_all(
                    BattleStatsComponent
                ).iter_components(BattleStatsComponent):
                    if stat_comp.faction == killed_faction:
                        stat_comp.death_status["损失"].append(
                            f"{killed_comp.name}(ID:{killed_entity})"
                        )
                    if stat_comp.faction == killer_faction:
                        stat_comp.death_status["击杀"].append(
                            f"{killed_comp.name}(ID:{killed_entity})"
                        )

        # After handling event-driven stats, update state-based stats
        # self.update_current_stats()

    def check_game_over(self):
        """检查游戏是否结束。"""
        # 简单的游戏结束条件：某一方的单位全部阵亡
        # Ensure unit_counts is up-to-date before checking
        # self.update_current_stats() # Called in main update loop already

        factions_with_units = [
            faction for faction, count in self.unit_counts.items() if count > 0
        ]

        active_factions_count = len(factions_with_units)

        # Consider only factions that are part of the game (e.g., not neutral if neutrals don't count for winning)
        # This might require a list of active/playing factions.
        # For now, assume all factions in unit_counts are playing factions.

        if active_factions_count == 1 and not self.game_over:
            self.game_over = True
            self.winner = factions_with_units[0]
            self.logger.info(f"游戏结束，胜利者: {self.winner}")
            # Post GAME_OVER event if your event system supports it
            # self.context.event_manager.post(EventMessage(EventType.GAME_OVER, {"winner": self.winner}))

            # 更新战场统计组件中的作战进程信息
            if self.battlefield_stats_component:
                self.battlefield_stats_component.death_status["game_over"] = True
                self.battlefield_stats_component.death_status["winner"] = self.winner
        elif active_factions_count == 0 and not self.game_over:
            # 所有阵营都没有单位，平局
            self.game_over = True
            self.winner = None  # Or a special 'DRAW' status
            self.logger.info("游戏结束，平局")
            # self.context.event_manager.post(EventMessage(EventType.GAME_OVER, {"winner": None}))

            # 更新战场统计组件中的作战进程信息
            if self.battlefield_stats_component:
                self.battlefield_stats_component.death_status["game_over"] = True
                self.battlefield_stats_component.death_status["winner"] = "DRAW"
        # If more than one faction has units, game continues (unless other conditions apply)

    def _handle_damage_dealt(self, event: EventMessage):
        """处理伤害造成事件。"""
        attacker_entity = event.data.get("entity")
        target_entity = event.data.get("target")
        # damage = event.data.get("damage")

        if attacker_entity and target_entity:  # and damage is not None:
            attacker_comp = self.context.get_component(attacker_entity, UnitComponent)
            target_comp = self.context.get_component(target_entity, UnitComponent)

            if attacker_comp and target_comp:
                # attacker_owner_id = attacker_comp.owner_id
                # target_owner_id = target_comp.owner_id
                attacker_faction = attacker_comp.faction
                target_faction = target_comp.faction
                # 获取伤害值
                damage = max(
                    1, attacker_comp.attack - target_comp.defense // 2
                )  # 确保至少造成1点伤害

                self.record_damage(attacker_faction, target_faction, damage)
                self.logger.msg(
                    f"阵营{attacker_faction}的{attacker_comp.name}(ID:{attacker_entity}) 对 阵营{target_faction}的{target_comp.name}(ID:{target_entity}),造成{damage}点伤害"
                )

                # # 更新战场统计组件中的交火情况
                for entity, (stat_comp,) in self.context.with_all(
                    BattleStatsComponent
                ).iter_components(BattleStatsComponent):
                    if stat_comp.faction == attacker_faction:
                        if target_faction not in stat_comp.contact_and_fire:
                            stat_comp.contact_and_fire[target_faction] = []
                        stat_comp.contact_and_fire[target_faction].append(
                            f"阵营{attacker_faction}的{attacker_comp.name}(ID:{attacker_entity}) 对 阵营{target_faction}的{target_comp.name}(ID:{target_entity}),造成{damage}点伤害"
                        )
                        if (
                            len(stat_comp.contact_and_fire[target_faction]) > 10
                        ):  # 限制列表长度
                            stat_comp.contact_and_fire[target_faction].pop(0)
                    if stat_comp.faction == target_faction:
                        if attacker_faction not in stat_comp.contact_and_fire:
                            stat_comp.contact_and_fire[attacker_faction] = []
                        stat_comp.contact_and_fire[attacker_faction].append(
                            f"阵营{target_faction}的{target_comp.name}(ID:{target_entity}) 受到 阵营{attacker_faction}的{attacker_comp.name}(ID:{attacker_entity}),造成{damage}点伤害"
                        )
                        if (
                            len(stat_comp.contact_and_fire[attacker_faction]) > 10
                        ):  # 限制列表长度
                            stat_comp.contact_and_fire[attacker_faction].pop(0)
                # if self.battlefield_stats_component:
                #     # 初始化交火情况数据结构
                #     if len(self.battlefield_stats_component.contact_and_fire) == 0:
                #         self.battlefield_stats_component.contact_and_fire[
                #             "engagements"
                #         ] = []

                #     # 记录交火事件
                #     engagement = {
                #         "attacker_faction": attacker_faction,
                #         "target_faction": target_faction,
                #         "damage": damage,
                #         "attacker_position": (
                #             attacker_comp.position_x,
                #             attacker_comp.position_y,
                #         ),
                #         "target_position": (
                #             target_comp.position_x,
                #             target_comp.position_y,
                #         ),
                #         "attacker_type": attacker_comp.unit_type.name,
                #         "target_type": target_comp.unit_type.name,
                #     }

                #     # 添加到交火记录列表
                #     self.battlefield_stats_component.contact_and_fire[
                #         "engagements"
                #     ].append(engagement)

                #     # 限制列表长度，只保留最近的20条记录
                #     if (
                #         len(
                #             self.battlefield_stats_component.contact_and_fire[
                #                 "engagements"
                #             ]
                #         )
                #         > 20
                #     ):
                #         self.battlefield_stats_component.contact_and_fire[
                #             "engagements"
                #         ].pop(0)

        # After handling event-driven stats, update state-based stats
        # self.update_current_stats()

    def update_battlefield_stats(self):
        """更新战场统计数据。"""

        for entity, (battle_stats,) in self.context.with_all(
            BattleStatsComponent
        ).iter_components(BattleStatsComponent):
            # 更新玩家阵营
            if battle_stats.faction in self.unit_counts.keys():
                # 更新敌方情况
                self._update_enemy_status(battle_stats)

                # 更新我方情况
                self._update_my_status(battle_stats)

                # 更新战场环境
                self._update_terrain_environment()

    def _update_enemy_status(self, battle_stats: BattleStatsComponent):
        """更新敌方兵力部署与状态。"""

        # 遍历所有单位，统计敌方单位状态
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            # 跳过我方单位
            if unit.faction == battle_stats.faction:
                continue

            # 在玩家视角模式下，只统计可见单位
            if self.view_mode == ViewMode.PLAYER and entity not in self.visible_units:
                continue

            # 初始化该阵营的统计数据
            battle_stats.enemy_status_info[
                f"阵营{unit.faction}{unit.name}(ID:{entity})"
            ] = {
                "health": f"{unit.current_health} / {unit.max_health}",
                "position": (unit.position_x, unit.position_y),
            }

        #     # 更新统计数据
        #     enemy_status[faction]["unit_count"] += 1

        #     # 按类型统计
        #     unit_type = unit.unit_type.value
        #     enemy_status[faction]["unit_types"].setdefault(unit_type, 0)
        #     enemy_status[faction]["unit_types"][unit_type] += 1

        #     # 按状态统计
        #     unit_state = unit.state.name
        #     enemy_status[faction]["unit_states"].setdefault(unit_state, 0)
        #     enemy_status[faction]["unit_states"][unit_state] += 1

        #     # 记录位置
        #     enemy_status[faction]["positions"].append(
        #         (unit.position_x, unit.position_y)
        #     )

        #     # 计算健康度百分比
        #     health_percentage = (unit.current_health / unit.max_health) * 100
        #     enemy_status[faction]["health_percentage"] += health_percentage

        # # 计算平均健康度
        # for faction, data in enemy_status.items():
        #     if data["unit_count"] > 0:
        #         data["health_percentage"] /= data["unit_count"]

        # 更新战场统计组件
        # battlefield_stats_component.enemy_status = enemy_status

    def _update_my_status(self, battle_stats):
        """更新我方兵力状态和任务执行进度。"""

        # 遍历所有单位，统计我方单位状态
        for entity, (unit,) in self.context.with_all(UnitComponent).iter_components(
            UnitComponent
        ):
            # 只统计我方单位
            if unit.faction != battle_stats.faction:
                continue

            battle_stats.my_status_info[
                f"阵营{unit.faction}{unit.name}(ID:{entity})"
            ] = {
                "health": f"{unit.current_health} / {unit.max_health}",
                "position": (unit.position_x, unit.position_y),
            }
            # # 按类型统计
            # unit_type = unit.unit_type.name
            # my_status["unit_types"].setdefault(unit_type, 0)
            # my_status["unit_types"][unit_type] += 1

            # # 按状态统计
            # unit_state = unit.state.name
            # my_status["unit_states"].setdefault(unit_state, 0)
            # my_status["unit_states"][unit_state] += 1

            # # 记录位置
            # my_status["positions"].append((unit.position_x, unit.position_y))

            # # 计算健康度百分比
            # health_percentage = (unit.current_health / unit.max_health) * 100
            # my_status["health_percentage"] += health_percentage

        # # 计算平均健康度
        # if my_status["unit_count"] > 0:
        #     my_status["health_percentage"] /= my_status["unit_count"]

        # # 更新战场统计组件
        # self.battlefield_stats_component.my_status = my_status

        # # 更新任务执行进度（这里只是一个示例，实际游戏中可能有更复杂的任务系统）
        # # 假设任务是消灭敌方单位，进度为已消灭的敌方单位数量占总数的百分比
        # task_progress = {}

        # # 获取敌方单位总数
        # enemy_total = sum(
        #     self.unit_counts.get(faction, 0)
        #     for faction in self.unit_counts
        #     if faction != self.player_faction
        # )

        # # 获取已消灭的敌方单位数量
        # enemy_killed = sum(
        #     self.event_stats["kills_by_player"].get(self.player_faction, 0)
        # )

        # # 计算进度百分比
        # if enemy_total > 0:
        #     task_progress["eliminate_enemies"] = (enemy_killed / enemy_total) * 100
        # else:
        #     task_progress["eliminate_enemies"] = 100  # 如果没有敌人，则任务完成

        # # 更新战场统计组件
        # self.battlefield_stats_component.task_progress = task_progress

    def _update_terrain_environment(self):
        """更新战场地理环境信息。"""
        if not self.battlefield_stats_component or not self.map_component:
            return

        terrain_environment = {
            "terrain_types": {},
            "terrain_distribution": {},
            "strategic_points": [],
        }

        # 统计地形类型分布
        for pos, tile_entity in self.map_component.tile_entities.items():
            tile_component = self.context.get_component(tile_entity, TileComponent)
            if tile_component:
                terrain_type = tile_component.terrain_type.name
                terrain_environment["terrain_types"].setdefault(terrain_type, 0)
                terrain_environment["terrain_types"][terrain_type] += 1

                # 记录地形分布
                if terrain_type not in terrain_environment["terrain_distribution"]:
                    terrain_environment["terrain_distribution"][terrain_type] = []
                terrain_environment["terrain_distribution"][terrain_type].append(pos)

                # 识别战略要点（例如，关隘、城市、城堡等）
                if tile_component.terrain_type in [
                    TerrainType.CITY,
                    TerrainType.CASTLE,
                    TerrainType.PASS,
                ]:
                    terrain_environment["strategic_points"].append(
                        {
                            "position": pos,
                            "type": terrain_type,
                        }
                    )

        # 更新战场统计组件
        self.battlefield_stats_component.terrain_environment = terrain_environment
