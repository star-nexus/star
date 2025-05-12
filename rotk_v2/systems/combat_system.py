from framework_v2.ecs.system import System
from framework_v2.engine.events import EventType
from rotk_v2.components import (
    CombatComponent,
    ArmyComponent,
    TransformComponent
)
import logging
from rich.logging import RichHandler
from typing import List

# 配置日志格式
logging.basicConfig(
    level=logging.DEBUG,  # 从INFO改为DEBUG
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("CombatSystem")

class CombatSystem(System):
    def __init__(self, required_components=[CombatComponent, ArmyComponent], priority=50):
        super().__init__(required_components=required_components, priority=priority)
        logger.info(f"战斗系统初始化完成，优先级：{priority}")
        
    def update(self, delta_time: float):
        entities = self.context.with_all(CombatComponent, ArmyComponent).result()
        # logger.debug(f"更新战斗系统，处理实体数量：{len(entities)}")
        
        for entity in entities:
            combat = self.context.component_manager.get_component(entity, CombatComponent)
            
            # 冷却时间处理日志
            if combat.current_cooldown > 0:
                original = combat.current_cooldown
                combat.current_cooldown = max(0, combat.current_cooldown - delta_time)
                logger.debug(f"实体 {entity} 冷却时间 {original:.1f} → {combat.current_cooldown:.1f}")
                
            if combat.is_in_combat:
                logger.info(f"实体 {entity} 进入战斗状态")
                self.handle_auto_combat(entity, combat)
    
    def handle_auto_combat(self, entity, combat):
        transform = self.context.component_manager.get_component(entity, TransformComponent)
        enemies = self.find_enemies_in_range(entity, transform.x, transform.y, combat.attack_range)
        
        logger.debug(f"实体 {entity} 搜索敌人，范围 {combat.attack_range}px，找到 {len(enemies)} 个目标")
        
        if enemies:
            nearest = self.get_nearest_enemy(entity, enemies)
            if combat.current_cooldown <= 0:
                logger.info(f"实体 {entity} 开始攻击目标 {nearest}")
                self.execute_attack(entity, nearest)
                combat.current_cooldown = combat.cooldown
    
    def execute_attack(self, attacker, defender):
        logger.debug(f"攻击执行：{attacker} → {defender}")
        
        # 获取攻击者和防御者组件
        attacker_combat = self.context.component_manager.get_component(attacker, CombatComponent)
        defender_army = self.context.component_manager.get_component(defender, ArmyComponent)
        
        # 伤害计算示例（实际需要完善）
        damage = 10  
        defender_army.troops = max(0, defender_army.troops - damage)
        
        logger.info(
            f"[bold red]攻击发生[/] {attacker} → {defender} "
            f"造成伤害 {damage}，剩余兵力 {defender_army.troops}"
        )
        
        # 发布事件...
        self.context.event_manager.publish_immediate(
            EventType.COMBAT_ATTACK,
            {"attacker": attacker, "defender": defender}
        )
        
        # 计算伤害逻辑...