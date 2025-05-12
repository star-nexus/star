import pygame
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

from rotk.logics.components import (
    UnitStatsComponent,
    FactionComponent,
)
from rotk.logics.components.misc_components import VictoryConditionComponent
# from rotk.scenes.end_scene import EndScene


class VictorySystem(System):
    """
    胜利系统 - 负责检测游戏胜负条件并触发相应结果
    """

    def __init__(self):
        super().__init__([], priority=80)  # 高优先级，但在战斗系统之后
        self.player_faction_id = 2  # 默认玩家为蜀国
        self.engine = None
        self.check_interval = 1.0  # 每秒检查一次
        self.time_since_last_check = 0.0
        self.game_over = False

        # 战斗统计数据
        self.total_damage = 0
        self.killed_enemies = 0
        self.lost_allies = 0

    def initialize(self, world: World, event_manager: EventManager, engine) -> None:
        """初始化胜利系统"""
        self.event_manager = event_manager
        self.engine = engine

        # 确保存在胜利条件组件
        # self._ensure_victory_condition_component(world)

        # 订阅可能影响胜负条件的事件
        self.event_manager.subscribe(
            "UNIT_KILLED", lambda message: self._on_unit_killed(world, message)
        )
        self.event_manager.subscribe(
            "FACTION_DEFEATED",
            lambda message: self._on_faction_defeated(world, message),
        )
        self.event_manager.subscribe(
            "FACTION_SWITCHED",
            lambda message: self._on_faction_switched(world, message),
        )

    def _on_unit_killed(self, world: World, message: Message) -> None:
        """单位阵亡事件处理"""
        unit_entity = message.data.get("unit_entity")
        faction_id = message.data.get("faction_id")

        # 更新统计信息
        if faction_id != self.player_faction_id:
            # 敌方单位被杀
            self.killed_enemies = getattr(self, "killed_enemies", 0) + 1

            # 更新胜利条件组件的进度
            victory_entities = world.get_entities_with_components(
                VictoryConditionComponent
            )
            if victory_entities:
                victory_comp = world.get_component(
                    victory_entities[0], VictoryConditionComponent
                )
                if not hasattr(victory_comp, "eliminated_enemy_count"):
                    victory_comp.eliminated_enemy_count = 0
                victory_comp.eliminated_enemy_count += 1
        else:
            # 友方单位被杀
            self.lost_allies = getattr(self, "lost_allies", 0) + 1

    def _on_faction_defeated(self, world, message: Message) -> None:
        """阵营被击败事件处理"""
        defeated_faction_id = message.data.get("faction_id")

        # 若玩家阵营被击败，触发失败
        if defeated_faction_id == self.player_faction_id:
            self._trigger_game_over(world, False)

    def _on_faction_switched(self, world: World, message: Message) -> None:
        """阵营切换事件处理"""
        self.player_faction_id = message.data.get("faction_id")

    def update(self, world: World, delta_time: float) -> None:
        """定期检查胜负条件"""
        if self.game_over:
            return

        self.time_since_last_check += delta_time
        if self.time_since_last_check >= self.check_interval:
            self.time_since_last_check = 0
            self._check_victory_conditions(world)

    def _check_victory_conditions(self, world: World) -> None:
        """检查游戏胜负条件，支持多种胜利类型"""
        # 获取胜利条件组件
        victory_condition_entities = world.get_entities_with_components(
            VictoryConditionComponent
        )
        if not victory_condition_entities:
            return  # 没有胜利条件组件，不执行检查

        victory_comp = world.get_component(
            victory_condition_entities[0], VictoryConditionComponent
        )

        # 根据不同的胜利类型执行不同的检查
        if victory_comp.victory_type == "ANNIHILATION":
            self._check_annihilation_victory(world, victory_comp)
        elif victory_comp.victory_type == "CAPTURE":
            self._check_capture_victory(world, victory_comp)
        elif victory_comp.victory_type == "SURVIVAL":
            self._check_survival_victory(world, victory_comp, delta_time)

    def _check_annihilation_victory(self, world: World, victory_comp) -> None:
        """检查歼灭胜利条件"""
        # 获取玩家阵营单位数量和敌方单位数量
        player_units = []
        enemy_units = []

        # 检查所有单位
        units = world.get_entities_with_components(UnitStatsComponent)
        for unit in units:
            unit_stats = world.get_component(unit, UnitStatsComponent)
            if unit_stats.faction_id == self.player_faction_id:
                player_units.append(unit)
            else:
                enemy_units.append(unit)

        # 计算进度 - 击杀敌方单位的百分比
        if hasattr(victory_comp, "eliminated_enemy_count"):
            total_enemy_units = len(enemy_units) + victory_comp.eliminated_enemy_count
            if total_enemy_units > 0:
                victory_comp.progress = (
                    victory_comp.eliminated_enemy_count / total_enemy_units
                )

        # 检查胜负条件
        if len(player_units) == 0:
            # 玩家单位全部阵亡，游戏失败
            self._trigger_game_over(world, False)
        elif len(enemy_units) == 0:
            # 敌方单位全部阵亡，游戏胜利
            self._trigger_game_over(True)

    def _check_capture_victory(self, world: World, victory_comp) -> None:
        """检查占领胜利条件"""
        # 此处实现占领目标的检查逻辑
        pass

    def _check_survival_victory(
        self, world: World, victory_comp, delta_time: float
    ) -> None:
        """检查生存胜利条件"""
        # 更新已经过的时间
        victory_comp.elapsed_time += delta_time

        # 计算进度
        victory_comp.progress = min(
            1.0, victory_comp.elapsed_time / victory_comp.survival_time
        )

        # 检查是否达到目标生存时间
        if victory_comp.elapsed_time >= victory_comp.survival_time:
            self._trigger_game_over(True)

        # 检查是否还有玩家单位存活
        player_units = []
        units = world.get_entities_with_components(UnitStatsComponent)
        for unit in units:
            unit_stats = world.get_component(unit, UnitStatsComponent)
            if unit_stats.faction_id == self.player_faction_id:
                player_units.append(unit)

        if len(player_units) == 0:
            self._trigger_game_over(False)

    def _trigger_game_over(self, world, victory: bool) -> None:
        """触发游戏结束"""
        if self.game_over:
            return  # 防止多次触发

        self.game_over = True

        # 收集游戏统计数据
        stats = self._collect_game_stats(world, victory)

        # 发布游戏结束事件
        self.event_manager.publish(
            "GAME_OVER",
            Message(
                topic="GAME_OVER",
                data_type="game_event",
                data={"victory": victory, "stats": stats},
            ),
        )

        # 使用类变量传递数据给结束场景
        # EndScene.victory_status = victory
        # EndScene.game_stats = stats

        # 切换到结束场景
        if self.engine:
            self.engine.switch_scene("end")

    def _collect_game_stats(self, world: World, victory: bool) -> dict:
        """收集游戏统计数据"""
        # 获取玩家阵营单位
        player_units = []
        units = world.get_entities_with_components(UnitStatsComponent)
        for unit in units:
            unit_stats = world.get_component(unit, UnitStatsComponent)
            if unit_stats.faction_id == self.player_faction_id:
                player_units.append(unit)

        # 获取阵营名称
        faction_names = ["Wei", "Shu", "Wu", "Huang"]
        faction_name = (
            faction_names[self.player_faction_id - 1]
            if 0 < self.player_faction_id <= len(faction_names)
            else f"faction_{self.player_faction_id}"
        )

        # Assemble basic statistics
        stats = {
            "Time": f"{int(pygame.time.get_ticks() / 1000)} seconds",
            "Remaining Units": len(player_units) if victory else 0,
            "Faction": faction_name,
        }

        # 添加战斗统计数据
        combat_stats = self._get_combat_statistics()
        stats.update(combat_stats)

        return stats

    def _get_combat_statistics(self) -> dict:
        """获取战斗统计数据"""
        return {"Kills": self.killed_enemies or 0, "Losses": self.lost_allies or 0}
