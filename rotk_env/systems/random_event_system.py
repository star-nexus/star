"""
随机事件系统 - 处理地形事件和技能事件（按规则手册v1.2）
"""

import random
from typing import Dict, Any, Optional
from framework import System, World
from ..components import (
    HexPosition,
    Unit,
    UnitCount,
    UnitStatus,
    UnitSkills,
    DiceRoll,
    TerrainEvent,
    UnitSkillEvent,
    RandomEventQueue,
    MapData,
    Terrain,
)
from ..prefabs.config import GameConfig, TerrainType, UnitType, UnitState


class RandomEventSystem(System):
    """随机事件系统"""

    def __init__(self):
        super().__init__(priority=400)

    def initialize(self, world: World) -> None:
        self.world = world

        # 确保有随机事件队列
        if not self.world.get_singleton_component(RandomEventQueue):
            self.world.add_singleton_component(RandomEventQueue())

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """处理事件队列"""
        event_queue = self.world.get_singleton_component(RandomEventQueue)
        if not event_queue:
            return

        # 处理所有待处理事件
        while True:
            event = event_queue.process_next_event()
            if not event:
                break

            self._handle_event(event)

    def trigger_terrain_event(self, entity: int, action: str) -> bool:
        """触发地形事件"""
        position = self.world.get_component(entity, HexPosition)
        unit = self.world.get_component(entity, Unit)

        if not position or not unit:
            return False

        terrain_type = self._get_terrain_at_position((position.col, position.row))
        event_result = self._check_terrain_event(terrain_type, unit.unit_type, action)

        if event_result:
            # 添加到事件队列
            event_queue = self.world.get_singleton_component(RandomEventQueue)
            if event_queue:
                event_queue.add_event("terrain", entity, event_result)
            return True

        return False

    def trigger_skill_event(self, entity: int, skill_name: str) -> bool:
        """触发技能事件"""
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)
        unit_skills = self.world.get_component(entity, UnitSkills)

        if not all([unit, unit_count, unit_skills]):
            return False

        # 检查技能是否可用
        if not unit_skills.can_use_skill(skill_name):
            return False

        # 检查人数要求并执行骰子判定
        skill_result = self._check_skill_requirements(
            unit.unit_type, unit_count, skill_name
        )

        if skill_result is not None:
            # 添加到事件队列
            event_queue = self.world.get_singleton_component(RandomEventQueue)
            if event_queue:
                event_queue.add_event("skill", entity, skill_result)
            return True

        return False

    def _check_terrain_event(
        self, terrain_type: TerrainType, unit_type: UnitType, action: str
    ) -> Optional[Dict]:
        """检查地形事件"""
        # 地形事件定义（按规则手册v1.2）
        terrain_events = {
            TerrainType.PLAIN: {
                "name": "扬尘",
                "trigger": {"cavalry": ["move_end"]},
                "threshold": 5,
                "success": "自身获得「隐蔽」1回合",
                "failure": "无",
            },
            TerrainType.MOUNTAIN: {
                "name": "落石",
                "trigger": {"any": ["enter"]},
                "threshold": 6,
                "success": "对该单位造成2点真实伤害",
                "failure": "无",
            },
            TerrainType.URBAN: {
                "name": "守城器械",
                "trigger": {"archer": ["garrison"]},
                "threshold": 4,
                "success": "下次射击伤害+50%",
                "failure": "器械卡壳，无加成",
            },
            TerrainType.FOREST: {
                "name": "迷途",
                "trigger": {"any": ["enter"]},
                "threshold": 6,
                "success": "随机方向多移动1格",
                "failure": "无",
            },
            TerrainType.HILL: {
                "name": "高地风势",
                "trigger": {"archer": ["attack"]},
                "threshold": 4,
                "success": "射程再+1",
                "failure": "射程-1",
            },
        }

        event_data = terrain_events.get(terrain_type)
        if not event_data:
            return None

        # 检查触发条件
        triggers = event_data["trigger"]
        unit_triggers = triggers.get(unit_type.value, [])
        any_triggers = triggers.get("any", [])

        if action not in unit_triggers and action not in any_triggers:
            return None

        # 执行骰子判定
        dice_roll = random.randint(1, 6)
        success = dice_roll >= event_data["threshold"]

        return {
            "name": event_data["name"],
            "dice_roll": dice_roll,
            "threshold": event_data["threshold"],
            "success": success,
            "effect": event_data["success"] if success else event_data["failure"],
        }

    def _check_skill_requirements(
        self, unit_type: UnitType, unit_count: UnitCount, skill_name: str
    ) -> Optional[Dict]:
        """检查技能要求并执行判定"""
        # 技能定义（按规则手册v1.2）
        skill_definitions = {
            UnitType.INFANTRY: {
                "盾墙·反射": {
                    "count_req": 0.5,
                    "threshold": 5,
                    "success": "远程伤害再-25%",
                    "failure": "仅基础盾墙加成",
                },
                "密集方阵": {
                    "count_req": 0.3,
                    "threshold": 4,
                    "success": "自身及相邻1格友军步兵D+30%",
                    "failure": "仅自身D+15%",
                },
            },
            UnitType.CAVALRY: {
                "冲锋·致命一击": {
                    "count_req": 0.4,
                    "threshold": 5,
                    "success": "冲势增伤每层+30%",
                    "failure": "保持原每层+20%",
                },
                "奔袭·踩踏": {
                    "count_req": 0.4,
                    "threshold": 4,
                    "success": "造成正常碰撞伤害",
                    "failure": "该格无伤害",
                },
            },
            UnitType.ARCHER: {
                "狙击·暴击": {
                    "count_req": 0.7,
                    "threshold": 4,
                    "success": "首次射击暴击×1.5",
                    "failure": "正常伤害",
                },
                "火力压制·混乱": {
                    "count_req": 0.5,
                    "threshold": 5,
                    "success": "区域目标强制混乱1回合",
                    "failure": "仅造成伤害",
                },
            },
        }

        unit_skills = skill_definitions.get(unit_type, {})
        skill_data = unit_skills.get(skill_name)

        if not skill_data:
            return None

        # 检查人数要求
        if unit_count.ratio < skill_data["count_req"]:
            return None

        # 执行骰子判定
        dice_roll = random.randint(1, 6)
        success = dice_roll >= skill_data["threshold"]

        return {
            "skill_name": skill_name,
            "dice_roll": dice_roll,
            "threshold": skill_data["threshold"],
            "success": success,
            "effect": skill_data["success"] if success else skill_data["failure"],
        }

    def _handle_event(self, event: Dict[str, Any]):
        """处理事件"""
        event_type = event["type"]
        entity = event["entity"]
        data = event["data"]

        if event_type == "terrain":
            self._apply_terrain_effect(entity, data)
        elif event_type == "skill":
            self._apply_skill_effect(entity, data)

    def _apply_terrain_effect(self, entity: int, data: Dict[str, Any]):
        """应用地形事件效果"""
        effect = data["effect"]

        if "隐蔽" in effect:
            # 获得隐蔽状态
            unit_status = self.world.get_component(entity, UnitStatus)
            if unit_status:
                unit_status.current_status = UnitState.HIDDEN
                unit_status.status_duration = 1

        elif "真实伤害" in effect:
            # 造成真实伤害
            unit_count = self.world.get_component(entity, UnitCount)
            if unit_count:
                damage = 2  # 2点真实伤害
                unit_count.current_count = max(0, unit_count.current_count - damage)

        elif "射击伤害" in effect:
            # 下次射击伤害加成（需要添加临时效果组件）
            pass

        elif "多移动" in effect:
            # 随机方向多移动1格（需要移动系统配合）
            pass

    def _apply_skill_effect(self, entity: int, data: Dict[str, Any]):
        """应用技能效果"""
        skill_name = data["skill_name"]
        effect = data["effect"]
        success = data["success"]

        # 设置技能冷却
        unit_skills = self.world.get_component(entity, UnitSkills)
        if unit_skills:
            cooldown = 3 if success else 1  # 成功冷却3回合，失败1回合
            unit_skills.use_skill(skill_name, cooldown)

        # 应用效果
        if "混乱" in effect and success:
            # 找到目标并施加混乱状态（需要目标选择逻辑）
            pass

        elif "暴击" in effect and success:
            # 下次攻击必定暴击（需要添加临时效果组件）
            pass

        elif "冲势增伤" in effect:
            unit_status = self.world.get_component(entity, UnitStatus)
            if unit_status:
                # 更新冲锋效果
                if success:
                    unit_status.charge_stacks = min(3, unit_status.charge_stacks + 1)

    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """获取位置的地形类型"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN
