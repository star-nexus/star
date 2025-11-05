"""
资源恢复系统 - 处理多层次资源的自动和手动恢复
按照MULTILAYER_RESOURCE_SYSTEM_DESIGN.md实现
"""

from framework import System, World
from ..components import (
    ActionPoints,
    MovementPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    Unit,
    HexPosition,
    Terrain,
    TerritoryControl,
    GameTime,
)
from ..prefabs.config import TerrainType, GameConfig


class ResourceRecoverySystem(System):
    """多层次资源恢复系统"""

    def __init__(self):
        super().__init__(priority=50)  # 早期执行，确保资源状态正确
        self.last_recovery_time = 0.0
        self.realtime_recovery_interval = 5.0  # 实时模式5秒恢复间隔

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
            self.last_recovery_time += delta_time
            if self.last_recovery_time >= self.realtime_recovery_interval:
                self._perform_auto_recovery()
                self.last_recovery_time = 0.0

    def _perform_auto_recovery(self):
        """执行自动恢复（行动点、移动力、攻击次数）"""
        for entity in self.world.query().with_component(Unit).entities():
            # 恢复行动点
            action_points = self.world.get_component(entity, ActionPoints)
            if action_points:
                action_points.reset()

            # 恢复移动力
            movement_points = self.world.get_component(entity, MovementPoints)
            if movement_points:
                movement_points.reset()

            # 恢复普通攻击次数
            attack_points = self.world.get_component(entity, AttackPoints)
            if attack_points:
                attack_points.reset_normal_attacks()

            # 更新技能冷却（但不恢复技能点数）
            skill_points = self.world.get_component(entity, SkillPoints)
            if skill_points:
                skill_points.update_cooldowns()


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