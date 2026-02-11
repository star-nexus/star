"""
资源恢复系统 - 处理多层次资源的自动和手动恢复
按照MULTILAYER_RESOURCE_SYSTEM_DESIGN.md实现
"""

from typing import Dict, Set

from framework import System, World
from ..components import ActionPoints, MovementPoints, AttackPoints, SkillPoints, Terrain, GameTime
from ..prefabs.config import TerrainType


class ResourceRecoverySystem(System):
    """多层次资源恢复系统"""

    def __init__(self):
        super().__init__(priority=50)  # 早期执行，确保资源状态正确
        
        # 行动点（AP）恢复配置：默认每5秒恢复1点
        # 注意：如需防止spam，建议配合操作冷却系统使用（见AP_RECOVERY_IMPROVEMENT_PROPOSAL.md）
        self.ap_recovery_interval = 1.0
        self.ap_recovery_amount = 1
        
        # 移动力（MP）恢复配置：默认每10秒完全恢复
        self.mp_recovery_interval = 3.0

        # 普通攻击次数恢复配置：每5秒重置
        self.attack_recovery_interval = 1.0

        # 技能冷却更新配置：与攻击恢复同步，默认每5秒更新一次
        self.skill_cooldown_interval = 5.0

        # 记录每个实体的累计恢复时间，防止"刚消耗即恢复"现象
        self.ap_elapsed: Dict[int, float] = {}
        self.mp_elapsed: Dict[int, float] = {}
        self.attack_elapsed: Dict[int, float] = {}
        self.skill_elapsed: Dict[int, float] = {}
        # 记录移动力最近一次观测的数值，用于检测新的移动操作
        self.mp_last_points: Dict[int, int] = {}
        
        # ===== 方案2：决策质量奖励（可选，需要配合ActionSystem实现）=====
        # 记录每个单位的"决策质量分数"，用于加速资源恢复
        # self.unit_decision_quality: Dict[int, float] = {}  # 0.0-1.0，1.0表示完美决策

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新资源恢复"""
        game_time = self.world.get_singleton_component(GameTime)
        if not game_time:
            return

        # 检查是否需要实时恢复
        if game_time.is_real_time():
            self._update_action_points(delta_time)
            self._update_movement_points(delta_time)
            self._update_attack_points(delta_time)
            self._update_skill_cooldowns(delta_time)

    # === 行动点恢复 ===
    def _update_action_points(self, delta_time: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.ap_recovery_interval
        amount = self.ap_recovery_amount

        for entity in self.world.query().with_component(ActionPoints).entities():
            seen_entities.add(entity)
            action_points = self.world.get_component(entity, ActionPoints)
            if not action_points:
                continue

            if action_points.current_ap >= action_points.max_ap:
                self.ap_elapsed.pop(entity, None)
                continue

            elapsed = self.ap_elapsed.get(entity, 0.0) + delta_time
            if elapsed < interval:
                self.ap_elapsed[entity] = elapsed
                continue

            recover_ticks = int(elapsed // interval)
            if recover_ticks <= 0:
                self.ap_elapsed[entity] = elapsed
                continue

            increment = amount * recover_ticks
            action_points.current_ap = min(
                action_points.max_ap,
                action_points.current_ap + increment,
            )

            elapsed -= interval * recover_ticks
            if action_points.current_ap >= action_points.max_ap:
                self.ap_elapsed.pop(entity, None)
            else:
                self.ap_elapsed[entity] = elapsed

        # 清理已经不存在的实体计时器
        stale_entities = set(self.ap_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.ap_elapsed.pop(entity, None)

    # === 移动力恢复 ===
    def _update_movement_points(self, delta_time: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.mp_recovery_interval

        for entity in self.world.query().with_component(MovementPoints).entities():
            seen_entities.add(entity)
            movement_points = self.world.get_component(entity, MovementPoints)
            if not movement_points:
                continue

            prev_points = self.mp_last_points.get(entity)
            if prev_points is None:
                prev_points = movement_points.current_mp
            else:
                if movement_points.current_mp < prev_points:
                    # 检测到新的移动操作，重新计时
                    self.mp_elapsed[entity] = 0.0
                    self.mp_last_points[entity] = movement_points.current_mp
                    continue

            if movement_points.current_mp >= movement_points.max_mp:
                self.mp_elapsed.pop(entity, None)
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            elapsed = self.mp_elapsed.get(entity, 0.0) + delta_time
            if elapsed < interval:
                self.mp_elapsed[entity] = elapsed
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            recover_ticks = int(elapsed // interval)
            if recover_ticks <= 0:
                self.mp_elapsed[entity] = elapsed
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            # 完全恢复移动力
            movement_points.reset()
            elapsed -= interval * recover_ticks

            if movement_points.current_mp >= movement_points.max_mp:
                self.mp_elapsed.pop(entity, None)
            else:
                self.mp_elapsed[entity] = elapsed

            self.mp_last_points[entity] = movement_points.current_mp

        stale_entities = set(self.mp_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.mp_elapsed.pop(entity, None)
        stale_last = set(self.mp_last_points.keys()) - seen_entities
        for entity in stale_last:
            self.mp_last_points.pop(entity, None)

    # === 普通攻击次数恢复 ===
    def _update_attack_points(self, delta_time: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.attack_recovery_interval

        for entity in self.world.query().with_component(AttackPoints).entities():
            seen_entities.add(entity)
            attack_points = self.world.get_component(entity, AttackPoints)
            if not attack_points:
                continue

            if attack_points.normal_attacks >= attack_points.max_normal_attacks:
                self.attack_elapsed.pop(entity, None)
                continue

            elapsed = self.attack_elapsed.get(entity, 0.0) + delta_time
            if elapsed < interval:
                self.attack_elapsed[entity] = elapsed
                continue

            recover_ticks = int(elapsed // interval)
            if recover_ticks <= 0:
                self.attack_elapsed[entity] = elapsed
                continue

            attack_points.reset_normal_attacks()
            elapsed -= interval * recover_ticks

            if attack_points.normal_attacks >= attack_points.max_normal_attacks:
                self.attack_elapsed.pop(entity, None)
            else:
                self.attack_elapsed[entity] = elapsed

        stale_entities = set(self.attack_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.attack_elapsed.pop(entity, None)

    # === 技能冷却更新 ===
    def _update_skill_cooldowns(self, delta_time: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.skill_cooldown_interval

        for entity in self.world.query().with_component(SkillPoints).entities():
            seen_entities.add(entity)
            skill_points = self.world.get_component(entity, SkillPoints)
            if not skill_points:
                continue

            elapsed = self.skill_elapsed.get(entity, 0.0) + delta_time
            if elapsed < interval:
                self.skill_elapsed[entity] = elapsed
                continue

            reduce_ticks = int(elapsed // interval)
            if reduce_ticks <= 0:
                self.skill_elapsed[entity] = elapsed
                continue

            for _ in range(reduce_ticks):
                skill_points.update_cooldowns()

            elapsed -= interval * reduce_ticks

            if not getattr(skill_points, "skill_cooldowns", None):
                self.skill_elapsed.pop(entity, None)
            else:
                self.skill_elapsed[entity] = elapsed

        stale_entities = set(self.skill_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.skill_elapsed.pop(entity, None)


    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """获取位置的地形类型"""
        from ..components import MapData

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN
