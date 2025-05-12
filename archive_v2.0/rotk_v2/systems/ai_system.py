import random
import logging
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from framework_v2.engine.events import EventMessage, EventType
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.ai_component import AIComponent
from rotk_v2.components.movable_component import MovableComponent
from rotk_v2.components.army_component import ArmyComponent

# 配置日志格式
logger = logging.getLogger("AISystem")

class AISystem(System):
    """
    AI 系统，负责控制 NPC 实体的行为
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = [AIComponent]
        super().__init__(required_components, priority)
        self.timer = 0
        logger.info(f"🤖 AI系统初始化完成，优先级：{priority}")
        
    def update(self, delta_time: float) -> None:
        if not self.context:
            return
            
        self.timer += delta_time
        
        if self.timer >= 1.0:
            logger.debug(f"⏱️ AI系统定时更新触发（间隔：{self.timer:.2f}s）")
            self.timer = 0
            self.update_ai()
            
    def update_ai(self):
        entities = self.context.with_all(AIComponent).result()
        logger.debug(f"🔄 更新AI实体，总数：{len(entities)}")
        
        for entity in entities:
            ai = self.context.component_manager.get_component(entity, AIComponent)
            logger.debug(f"处理实体 {entity}，当前状态：[{ai.state}]")

            if self.check_army_status(entity):
                logger.warning(f"⚠️ 实体 {entity} 触发撤退条件")
                ai.state = "retreat"
                ai.target = None
                self.retreat(entity)
                continue
            
            if ai.state == "idle":
                if random.random() < 0.2:
                    logger.info(f"🚦 实体 {entity} 开始巡逻")
                    ai.state = "patrol"
                    self.start_patrol(entity)
                    
            elif ai.state == "patrol":
                enemy = self.find_nearest_enemy(entity)
                if enemy:
                    logger.info(f"⚔️ 实体 {entity} 发现敌人 {enemy}")
                    ai.state = "attack"
                    ai.target = enemy
                    self.start_attack(entity, enemy)
                    
            elif ai.state == "attack":
                if not ai.target or not self.context.entity_exists(ai.target):
                    logger.debug(f"🕳️ 实体 {entity} 攻击目标已消失")
                    ai.state = "idle"
                    ai.target = None
                else:
                    logger.debug(f"⚡ 实体 {entity} 持续攻击目标 {ai.target}")
                    self.continue_attack(entity, ai.target)
                    
            elif ai.state == "retreat":
                logger.info(f"🏃 实体 {entity} 正在撤退")
                if not self.check_army_status(entity):
                    logger.info(f"✅ 实体 {entity} 脱离危险状态")
                    ai.state = "idle"
                    ai.target = None

    def start_patrol(self, entity):
        """
        开始巡逻
        
        参数:
            entity: 实体 ID
        """
        # 如果实体可移动，设置随机巡逻点
        if self.context.component_manager.has_component(entity, MovableComponent) and self.context.component_manager.has_component(entity, TransformComponent):
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            movable = self.context.component_manager.get_component(entity, MovableComponent)
            
            # 设置随机目标点
            x = transform.x + random.randint(-100, 100)
            y = transform.y + random.randint(-100, 100)
            
            # 确保目标点在地图范围内
            x = max(0, min(x, 1000))
            y = max(0, min(y, 1000))
            
            movable.target_x = x
            movable.target_y = y
            movable.moving = True
            
            # 发布移动开始事件
            if self.context.event_manager:
                self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_STARTED, {
                    "entity": entity,
                    "target_x": x,
                    "target_y": y
                }))
            
    def find_nearest_enemy(self, entity):
        logger.debug(f"🔍 实体 {entity} 正在搜索敌人...")
        
        if not self.context.component_manager.has_component(entity, ArmyComponent):
            logger.warning(f"❌ 实体 {entity} 缺少军队组件")
            return None
            
        army = self.context.component_manager.get_component(entity, ArmyComponent)
        entity_force = army.force
        
        if not self.context.component_manager.has_component(entity, TransformComponent):
            logger.warning(f"❌ 实体 {entity} 缺少位置组件")
            return None
            
        transform = self.context.component_manager.get_component(entity, TransformComponent)
        entity_x, entity_y = transform.x, transform.y
        
        # 获取所有敌方实体
        enemy_entities = []
        
        # query = self.context.query_manager.create_query()
        # query.with_component(ArmyComponent)
        # all_entities = query.execute()
        all_entities = self.context.with_all(ArmyComponent).result()
        
        for other in all_entities:
            if other == entity:
                continue
                
            other_army = self.context.component_manager.get_component(other, ArmyComponent)
            if other_army.force != entity_force:
                enemy_entities.append(other)
                
        if not enemy_entities:
            return None
            
        # 找到最近的敌人
        nearest_enemy = None
        min_distance = float('inf')
        
        for enemy in enemy_entities:
            if not self.context.component_manager.has_component(enemy, TransformComponent):
                continue
                
            enemy_transform = self.context.component_manager.get_component(enemy, TransformComponent)
            dx = enemy_transform.x - entity_x
            dy = enemy_transform.y - entity_y
            distance = dx * dx + dy * dy
            
            if distance < min_distance:
                min_distance = distance
                nearest_enemy = enemy
                
        return nearest_enemy
        
    def start_attack(self, entity, target):
        """
        开始攻击
        
        参数:
            entity: 攻击者实体 ID
            target: 目标实体 ID
        """
        # 如果实体可移动，移动到目标附近
        if self.context.component_manager.has_component(entity, MovableComponent) and self.context.component_manager.has_component(target, TransformComponent):
            movable = self.context.component_manager.get_component(entity, MovableComponent)
            target_transform = self.context.component_manager.get_component(target, TransformComponent)
            
            movable.target_x = target_transform.x
            movable.target_y = target_transform.y
            movable.moving = True
            
            # 发布移动开始事件
            if self.context.event_manager:
                self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_STARTED, {
                    "entity": entity,
                    "target_x": target_transform.x,
                    "target_y": target_transform.y
                }))
            
    def continue_attack(self, entity, target):
        """
        继续攻击
        
        参数:
            entity: 攻击者实体 ID
            target: 目标实体 ID
        """
        # 检查是否在攻击范围内
        if not self.context.component_manager.has_component(entity, TransformComponent) or not self.context.component_manager.has_component(target, TransformComponent):
            return
            
        transform = self.context.component_manager.get_component(entity, TransformComponent)
        target_transform = self.context.component_manager.get_component(target, TransformComponent)
        
        dx = target_transform.x - transform.x
        dy = target_transform.y - transform.y
        distance = dx * dx + dy * dy
        
        # 如果距离太远，移动到目标附近
        if distance > 100 * 100:
            if self.context.component_manager.has_component(entity, MovableComponent):
                movable = self.context.component_manager.get_component(entity, MovableComponent)
                movable.target_x = target_transform.x
                movable.target_y = target_transform.y
                movable.moving = True
        else:
            # 在攻击范围内，执行攻击
            self.attack(entity, target)
            
    def attack(self, entity, target):
        logger.info(f"💥 实体 {entity} 攻击 {target}")
        
        attacker_army = self.context.component_manager.get_component(entity, ArmyComponent)
        defender_army = self.context.component_manager.get_component(target, ArmyComponent)
        
        attack_power = attacker_army.troops * (attacker_army.training / 100) * (attacker_army.morale / 100)
        defense_power = defender_army.troops * (defender_army.training / 100) * (defender_army.morale / 100)
        logger.debug(f"📊 攻击力：{attack_power:.1f} vs 防御力：{defense_power:.1f}")

        damage_ratio = attack_power / (attack_power + defense_power)
        damage = int(damage_ratio * 100 * random.uniform(0.8, 1.2))
        logger.info(f"💢 造成伤害 {damage}，剩余兵力 {defender_army.troops}")

        # 应用伤害
        defender_army.troops = max(0, defender_army.troops - damage)
        
        # 降低士气
        defender_army.morale = max(10, defender_army.morale - 5)
        
        # 消耗补给
        attacker_army.supply = max(0, attacker_army.supply - 10)
        
        # 发布战斗事件
        if self.context.event_manager:
            self.context.event_manager.publish(EventMessage(EventType.COMBAT_STARTED, {
                "attacker": entity,
                "defender": target,
                "damage": damage
            }))
            
        # 检查是否消灭了目标
        if defender_army.troops <= 0:
            # 发布单位死亡事件
            if self.context.event_manager:
                self.context.event_manager.publish(EventMessage(EventType.UNIT_DIED, {
                    "entity": target
                }))
                
            # 删除目标实体
            self.context.entity_manager.destroy_entity(target)
            
    def retreat(self, entity):
        """
        撤退
        
        参数:
            entity: 实体 ID
        """
        # 如果实体可移动，向安全区域移动
        if self.context.component_manager.has_component(entity, MovableComponent) and self.context.component_manager.has_component(entity, TransformComponent):
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            movable = self.context.component_manager.get_component(entity, MovableComponent)
            
            # 获取实体的阵营
            if self.context.component_manager.has_component(entity, ArmyComponent):
                army = self.context.component_manager.get_component(entity, ArmyComponent)
                force = army.force
                
                # 找到友方城市
                friendly_city = self.find_nearest_friendly_city(entity, force)
                
                if friendly_city:
                    # 移动到友方城市
                    city_transform = self.context.component_manager.get_component(friendly_city, TransformComponent)
                    movable.target_x = city_transform.x
                    movable.target_y = city_transform.y
                    movable.moving = True
                    
                    # 发布移动开始事件
                    if self.context.event_manager:
                        self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_STARTED, {
                            "entity": entity,
                            "target_x": city_transform.x,
                            "target_y": city_transform.y
                        }))
                else:
                    # 没有友方城市，随机移动
                    x = transform.x + random.randint(-200, 200)
                    y = transform.y + random.randint(-200, 200)
                    
                    # 确保目标点在地图范围内
                    x = max(0, min(x, 1000))
                    y = max(0, min(y, 1000))
                    
                    movable.target_x = x
                    movable.target_y = y
                    movable.moving = True
                    
                    # 发布移动开始事件
                    if self.context.event_manager:
                        self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_STARTED, {
                            "entity": entity,
                            "target_x": x,
                            "target_y": y
                        }))
            
    def find_nearest_friendly_city(self, entity, force):
        """
        寻找最近的友方城市
        
        参数:
            entity: 实体 ID
            force: 势力
            
        返回:
            城市实体 ID 或 None
        """
        from rotk_v2.components.city_component import CityComponent
        
        # 获取实体的位置
        if not self.context.component_manager.has_component(entity, TransformComponent):
            return None
            
        transform = self.context.component_manager.get_component(entity, TransformComponent)
        entity_x, entity_y = transform.x, transform.y
        
        # 获取所有友方城市
        friendly_cities = []
        

        all_cities = self.context.with_all(CityComponent).result()
        
        for city in all_cities:
            city_component = self.context.component_manager.get_component(city, CityComponent)
            if city_component.force == force:
                friendly_cities.append(city)
                
        if not friendly_cities:
            return None
            
        # 找到最近的友方城市
        nearest_city = None
        min_distance = float('inf')
        
        for city in friendly_cities:
            if not self.context.component_manager.has_component(city, TransformComponent):
                continue
                
            city_transform = self.context.component_manager.get_component(city, TransformComponent)
            dx = city_transform.x - entity_x
            dy = city_transform.y - entity_y
            distance = dx * dx + dy * dy
            
            if distance < min_distance:
                min_distance = distance
                nearest_city = city
                
        return nearest_city
        
    def check_army_status(self, entity):
        logger.debug(f"🛡️ 检查实体 {entity} 军队状态")
        
        if not self.context.component_manager.has_component(entity, ArmyComponent):
            logger.warning(f"❌ 实体 {entity} 缺少军队组件")
            return False
            
        army = self.context.component_manager.get_component(entity, ArmyComponent)
        
        if army.troops < 200:
            logger.debug("撤退原因：兵力不足")
            return True
        if army.morale < 30:
            logger.debug("撤退原因：士气低落")
            return True
        if army.supply < 50:
            logger.debug("撤退原因：补给不足")
            return True
            
        return False