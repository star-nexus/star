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

    def perform_turn_based_recovery(self):
        """回合制恢复 - 在回合开始时调用"""
        print("执行回合制资源恢复...")
        self._perform_auto_recovery()

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

    def perform_rest_action(self, entity: int) -> bool:
        """执行休整动作 - 恢复技能点数"""
        # 检查单位是否有行动点执行休整决策
        action_points = self.world.get_component(entity, ActionPoints)
        if not action_points or not action_points.can_perform_action("wait"):
            return False

        # 消耗1点行动点执行休整决策
        action_points.consume_ap("wait")

        # 恢复技能点数
        skill_points = self.world.get_component(entity, SkillPoints)
        if skill_points:
            skill_points.restore_by_rest()

        print(f"单位 {entity} 完成休整，技能点数已恢复")
        return True

    def perform_city_resupply(self, entity: int) -> bool:
        """在城市执行补给 - 恢复建造点数"""
        # 检查单位是否在城市中
        position = self.world.get_component(entity, HexPosition)
        if not position:
            return False

        terrain_type = self._get_terrain_at_position((position.col, position.row))
        if terrain_type not in [TerrainType.CITY, TerrainType.URBAN]:
            return False

        # 检查是否为己方控制的城市
        if not self._is_friendly_territory(entity, (position.col, position.row)):
            return False

        # 检查单位是否有行动点执行补给决策
        action_points = self.world.get_component(entity, ActionPoints)
        if not action_points or not action_points.can_perform_action("garrison"):
            return False

        # 消耗1点行动点执行补给决策
        action_points.consume_ap("garrison")

        # 恢复建造点数
        construction_points = self.world.get_component(entity, ConstructionPoints)
        if construction_points:
            construction_points.restore_to_city()

        print(f"单位 {entity} 在城市完成补给，建造点数已恢复")
        return True

    def get_recovery_info(self, entity: int) -> dict:
        """获取单位的资源恢复信息"""
        info = {
            "auto_recovery": {
                "action_points": "每回合/5秒自动恢复",
                "movement_points": "每回合/5秒自动恢复",
                "normal_attacks": "每回合/5秒自动恢复",
            },
            "manual_recovery": {
                "skill_points": "需要休整动作",
                "construction_points": "需要在城市补给",
            },
            "current_status": {},
        }

        # 获取当前资源状态
        action_points = self.world.get_component(entity, ActionPoints)
        if action_points:
            info["current_status"][
                "action_points"
            ] = f"{action_points.current_ap}/{action_points.max_ap}"

        movement_points = self.world.get_component(entity, MovementPoints)
        if movement_points:
            info["current_status"][
                "movement_points"
            ] = f"{movement_points.current_mp}/{movement_points.max_mp}"

        attack_points = self.world.get_component(entity, AttackPoints)
        if attack_points:
            info["current_status"][
                "attack_points"
            ] = f"{attack_points.normal_attacks}/{attack_points.max_normal_attacks}"
            info["current_status"][
                "skill_points_attack"
            ] = f"{attack_points.skill_points}/{attack_points.max_skill_points}"

        skill_points = self.world.get_component(entity, SkillPoints)
        if skill_points:
            info["current_status"][
                "skill_points"
            ] = f"{skill_points.current_sp}/{skill_points.max_sp}"

        construction_points = self.world.get_component(entity, ConstructionPoints)
        if construction_points:
            info["current_status"][
                "construction_points"
            ] = f"{construction_points.current_cp}/{construction_points.max_cp}"

        return info

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

    def _is_friendly_territory(self, entity: int, position: tuple) -> bool:
        """检查位置是否为友方领土"""
        from ..components import MapData

        unit = self.world.get_component(entity, Unit)
        if not unit:
            return False

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True  # 默认为友方

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return True

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return True  # 中立领土可以补给

        return territory_control.controlled_by == unit.faction
