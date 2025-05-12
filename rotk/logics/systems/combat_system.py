import random
from framework.core.ecs.system import System
from framework.core.ecs.world import World
from framework.managers.events import EventManager, Message

# from rotk.logics.components import (
#     UnitStatsComponent,
#     UnitStateComponent,
#     UnitPositionComponent,
#     TerrainType,
#     UnitType,
#     UnitCategory,
#     UnitState,
# )

from rotk.logics.systems.attack_system import AttackSystem
from rotk.logics.systems.damage_system import DamageSystem
from rotk.logics.systems.combat_effects_system import CombatEffectsSystem


class CombatSystem(System):
    """战斗系统，负责协调各个战斗子系统的运行"""

    def __init__(self):
        """初始化战斗系统"""
        super().__init__([], priority=30)
        self.unit_system = None
        self.map_manager = None
        
        # 创建子系统
        self.attack_system = AttackSystem()
        self.damage_system = DamageSystem()
        self.combat_effects_system = CombatEffectsSystem()
        
        # 保存事件记录
        self.combat_log = []
        self.MAX_LOG_SIZE = 100  # 最大日志条目数

    def initialize(
        self,
        world: World,
        event_manager: EventManager,
        map_manager=None,
        unit_system=None,
    ) -> None:
        """初始化战斗系统和所有子系统
        
        Args:
            world: 游戏世界
            event_manager: 事件管理器
            map_manager: 地图管理器
            unit_system: 单位系统
        """
        self.world = world
        self.event_manager = event_manager
        self.map_manager = map_manager
        self.unit_system = unit_system
        
        # 初始化伤害系统
        self.damage_system.initialize(
            world=world,
            event_manager=event_manager,
            map_manager=map_manager,
            unit_system=unit_system,
        )
        
        # 初始化战斗效果系统
        self.combat_effects_system.initialize(
            world=world,
            event_manager=event_manager,
            unit_system=unit_system,
        )
        
        # 初始化攻击系统（需要注入伤害系统的引用）
        self.attack_system.initialize(
            world=world,
            event_manager=event_manager,
            map_manager=map_manager,
            unit_system=unit_system,
            damage_system=self.damage_system,
        )
        
        # 订阅战斗事件，用于记录战斗日志
        self.event_manager.subscribe("COMBAT_HIT", self._log_combat_event)
        self.event_manager.subscribe("COMBAT_MISS", self._log_combat_event)
        self.event_manager.subscribe("UNIT_KILLED", self._log_combat_event)
        self.event_manager.subscribe("UNIT_ROUTING", self._log_combat_event)
        self.event_manager.subscribe("UNIT_RECOVERED_FROM_ROUTING", self._log_combat_event)

    def _log_combat_event(self, message: Message) -> None:
        """记录战斗事件到战斗日志
        
        Args:
            message: 事件消息
        """
        self.combat_log.append(message)
        
        # 限制日志大小
        if len(self.combat_log) > self.MAX_LOG_SIZE:
            self.combat_log = self.combat_log[-self.MAX_LOG_SIZE:]

    def get_combat_log(self) -> list:
        """获取战斗日志
        
        Returns:
            list: 战斗事件日志列表
        """
        return self.combat_log

    def clear_combat_log(self) -> None:
        """清空战斗日志"""
        self.combat_log = []

    def initiate_combat(self, attacker: int, target: int) -> None:
        """发起战斗（委托给攻击系统处理）
        
        Args:
            attacker: 攻击方实体ID
            target: 目标实体ID
        """
        self.attack_system.initiate_combat(attacker, target)

    def update(self, world: World, delta_time: float) -> None:
        """更新战斗系统和所有子系统
        
        Args:
            world: 游戏世界
            delta_time: 帧间隔时间
        """
        # 依次更新各个子系统
        self.attack_system.update(world, delta_time)
        self.damage_system.update(world, delta_time)
        self.combat_effects_system.update(world, delta_time)
