"""
事件系统示例 - 展示事件驱动的系统间通信

这个示例演示了：
1. 如何使用事件管理器
2. 系统间的解耦通信
3. 事件的发布和订阅
4. 复杂的事件链反应
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from dataclasses import dataclass
from framework.ecs.world import World
from framework.ecs.component import Component
from framework.ecs.system import System
from framework.engine.events import EventManager, EventType
import random
import time


# 定义组件
@dataclass
class NameComponent(Component):
    """名称组件"""

    name: str = "Unknown"


@dataclass
class HealthComponent(Component):
    """生命值组件"""

    max_health: int = 100
    current_health: int = 100

    def is_alive(self) -> bool:
        return self.current_health > 0

    def take_damage(self, damage: int):
        self.current_health = max(0, self.current_health - damage)
        return self.current_health == 0  # 返回是否死亡

    def heal(self, amount: int):
        old_health = self.current_health
        self.current_health = min(self.max_health, self.current_health + amount)
        return self.current_health - old_health  # 返回实际治愈量


@dataclass
class WeaponComponent(Component):
    """武器组件"""

    weapon_name: str = "拳头"
    damage: int = 10
    accuracy: float = 0.8  # 命中率


@dataclass
class ExperienceComponent(Component):
    """经验组件"""

    level: int = 1
    experience: int = 0
    experience_to_next: int = 100


# 定义自定义事件类型
class CustomEventType:
    UNIT_ATTACK = "unit_attack"
    UNIT_TAKE_DAMAGE = "unit_take_damage"
    UNIT_DEATH = "unit_death"
    UNIT_LEVEL_UP = "unit_level_up"
    UNIT_HEAL = "unit_heal"
    COMBAT_LOG = "combat_log"


# 定义系统
class CombatSystem(System):
    """战斗系统 - 处理攻击逻辑"""

    def __init__(self, event_manager: EventManager):
        super().__init__([NameComponent, HealthComponent, WeaponComponent])
        self.event_manager = event_manager
        self.combat_timer = 0.0

    def update(self, delta_time: float):
        if not self.context:
            return

        self.combat_timer += delta_time
        if self.combat_timer < 3.0:  # 每3秒进行一次战斗
            return

        self.combat_timer = 0.0

        entities = self.context.query_manager.query_entities(self.required_components)
        alive_entities = []

        # 筛选存活的实体
        for entity in entities:
            health = self.context.component_manager.get_component(
                entity, HealthComponent
            )
            if health.is_alive():
                alive_entities.append(entity)

        if len(alive_entities) < 2:
            return

        # 随机选择攻击者和目标
        attacker = random.choice(alive_entities)
        targets = [e for e in alive_entities if e != attacker]
        if not targets:
            return

        target = random.choice(targets)

        # 执行攻击
        self._perform_attack(attacker, target)

    def _perform_attack(self, attacker_entity, target_entity):
        """执行攻击"""
        attacker_name = self.context.component_manager.get_component(
            attacker_entity, NameComponent
        )
        target_name = self.context.component_manager.get_component(
            target_entity, NameComponent
        )
        weapon = self.context.component_manager.get_component(
            attacker_entity, WeaponComponent
        )
        target_health = self.context.component_manager.get_component(
            target_entity, HealthComponent
        )

        # 发布攻击事件
        self.event_manager.publish(
            CustomEventType.UNIT_ATTACK,
            {
                "attacker": attacker_entity,
                "target": target_entity,
                "attacker_name": attacker_name.name,
                "target_name": target_name.name,
                "weapon": weapon.weapon_name,
            },
        )

        # 检查命中
        if random.random() <= weapon.accuracy:
            # 命中，造成伤害
            is_dead = target_health.take_damage(weapon.damage)

            # 发布受伤事件
            self.event_manager.publish(
                CustomEventType.UNIT_TAKE_DAMAGE,
                {
                    "target": target_entity,
                    "target_name": target_name.name,
                    "damage": weapon.damage,
                    "remaining_health": target_health.current_health,
                },
            )

            # 如果目标死亡，发布死亡事件
            if is_dead:
                self.event_manager.publish(
                    CustomEventType.UNIT_DEATH,
                    {
                        "unit": target_entity,
                        "unit_name": target_name.name,
                        "killer": attacker_entity,
                        "killer_name": attacker_name.name,
                    },
                )
        else:
            # 未命中
            self.event_manager.publish(
                CustomEventType.COMBAT_LOG,
                {
                    "message": f"{attacker_name.name} 攻击 {target_name.name}，但是没有命中！"
                },
            )


class ExperienceSystem(System):
    """经验系统 - 处理经验获得和升级"""

    def __init__(self, event_manager: EventManager):
        super().__init__([ExperienceComponent])
        self.event_manager = event_manager

        # 订阅事件
        self.event_manager.subscribe(CustomEventType.UNIT_DEATH, self._on_unit_death)
        self.event_manager.subscribe(
            CustomEventType.UNIT_TAKE_DAMAGE, self._on_unit_damage
        )

    def _on_unit_death(self, event_data):
        """单位死亡时，给击杀者经验"""
        killer_entity = event_data["killer"]
        exp_comp = self.context.component_manager.get_component(
            killer_entity, ExperienceComponent
        )

        if exp_comp:
            self._gain_experience(killer_entity, exp_comp, 50)

    def _on_unit_damage(self, event_data):
        """造成伤害时给少量经验"""
        # 这里需要找到攻击者，但事件数据中没有直接提供
        # 在实际项目中，可以在事件数据中包含攻击者信息
        pass

    def _gain_experience(self, entity, exp_comp, amount):
        """获得经验"""
        exp_comp.experience += amount

        # 检查升级
        while exp_comp.experience >= exp_comp.experience_to_next:
            exp_comp.experience -= exp_comp.experience_to_next
            exp_comp.level += 1
            exp_comp.experience_to_next = exp_comp.level * 100

            # 发布升级事件
            name = self.context.component_manager.get_component(entity, NameComponent)
            self.event_manager.publish(
                CustomEventType.UNIT_LEVEL_UP,
                {
                    "unit": entity,
                    "unit_name": name.name if name else "Unknown",
                    "new_level": exp_comp.level,
                },
            )

    def update(self, delta_time: float):
        # 经验系统主要通过事件驱动，update方法可以为空
        pass


class HealingSystem(System):
    """治疗系统 - 定期治疗受伤单位"""

    def __init__(self, event_manager: EventManager):
        super().__init__([HealthComponent])
        self.event_manager = event_manager
        self.heal_timer = 0.0

    def update(self, delta_time: float):
        if not self.context:
            return

        self.heal_timer += delta_time
        if self.heal_timer < 5.0:  # 每5秒治疗一次
            return

        self.heal_timer = 0.0

        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            health = self.context.component_manager.get_component(
                entity, HealthComponent
            )

            if health.is_alive() and health.current_health < health.max_health:
                heal_amount = health.heal(20)

                if heal_amount > 0:
                    name = self.context.component_manager.get_component(
                        entity, NameComponent
                    )
                    self.event_manager.publish(
                        CustomEventType.UNIT_HEAL,
                        {
                            "unit": entity,
                            "unit_name": name.name if name else "Unknown",
                            "heal_amount": heal_amount,
                            "current_health": health.current_health,
                        },
                    )


class LoggingSystem(System):
    """日志系统 - 监听所有事件并记录"""

    def __init__(self, event_manager: EventManager):
        super().__init__([])  # 不需要特定组件
        self.event_manager = event_manager

        # 订阅所有感兴趣的事件
        self.event_manager.subscribe(CustomEventType.UNIT_ATTACK, self._on_attack)
        self.event_manager.subscribe(CustomEventType.UNIT_TAKE_DAMAGE, self._on_damage)
        self.event_manager.subscribe(CustomEventType.UNIT_DEATH, self._on_death)
        self.event_manager.subscribe(CustomEventType.UNIT_LEVEL_UP, self._on_level_up)
        self.event_manager.subscribe(CustomEventType.UNIT_HEAL, self._on_heal)
        self.event_manager.subscribe(CustomEventType.COMBAT_LOG, self._on_combat_log)

    def _on_attack(self, event_data):
        print(
            f"⚔️ {event_data['attacker_name']} 使用 {event_data['weapon']} 攻击 {event_data['target_name']}"
        )

    def _on_damage(self, event_data):
        print(
            f"💥 {event_data['target_name']} 受到 {event_data['damage']} 点伤害，剩余生命值: {event_data['remaining_health']}"
        )

    def _on_death(self, event_data):
        print(f"💀 {event_data['unit_name']} 被 {event_data['killer_name']} 击败！")

    def _on_level_up(self, event_data):
        print(f"🎉 {event_data['unit_name']} 升级到 {event_data['new_level']} 级！")

    def _on_heal(self, event_data):
        print(
            f"💚 {event_data['unit_name']} 恢复了 {event_data['heal_amount']} 点生命值，当前: {event_data['current_health']}"
        )

    def _on_combat_log(self, event_data):
        print(f"📝 {event_data['message']}")

    def update(self, delta_time: float):
        # 日志系统主要通过事件驱动
        pass


class StatusDisplaySystem(System):
    """状态显示系统"""

    def __init__(self):
        super().__init__([NameComponent, HealthComponent])
        self.display_timer = 0.0

    def update(self, delta_time: float):
        if not self.context:
            return

        self.display_timer += delta_time
        if self.display_timer < 8.0:  # 每8秒显示一次状态
            return

        self.display_timer = 0.0

        entities = self.context.query_manager.query_entities(self.required_components)

        print("\n" + "=" * 50)
        print("当前战场状态:")
        print("=" * 50)

        alive_count = 0
        for entity in entities:
            name = self.context.component_manager.get_component(entity, NameComponent)
            health = self.context.component_manager.get_component(
                entity, HealthComponent
            )
            exp = self.context.component_manager.get_component(
                entity, ExperienceComponent
            )
            weapon = self.context.component_manager.get_component(
                entity, WeaponComponent
            )

            if health.is_alive():
                alive_count += 1
                status_icon = "🟢"
            else:
                status_icon = "🔴"

            exp_info = (
                f"等级{exp.level}({exp.experience}/{exp.experience_to_next})"
                if exp
                else "无等级"
            )
            weapon_info = weapon.weapon_name if weapon else "无武器"

            print(
                f"{status_icon} [{entity}] {name.name} - "
                f"生命值:{health.current_health}/{health.max_health} - "
                f"{exp_info} - 武器:{weapon_info}"
            )

        print(f"\n存活单位: {alive_count}/{len(entities)}")
        print("=" * 50)


def main():
    print("=== 事件系统示例 ===")
    print("这个示例展示了事件驱动的系统间通信")
    print("观察不同系统如何通过事件进行协作")
    print("按 Ctrl+C 退出\n")

    # 创建事件管理器
    event_manager = EventManager()

    # 创建世界
    world = World()

    # 添加系统（注意添加顺序）
    world.add_system(CombatSystem(event_manager))
    world.add_system(ExperienceSystem(event_manager))
    world.add_system(HealingSystem(event_manager))
    world.add_system(LoggingSystem(event_manager))
    world.add_system(StatusDisplaySystem())

    # 创建战斗单位
    warriors = [
        ("赵云", 120, "银枪", 25, 0.9),
        ("关羽", 150, "青龙偃月刀", 30, 0.85),
        ("张飞", 140, "丈八蛇矛", 28, 0.8),
        ("马超", 110, "虎头湛金枪", 26, 0.88),
        ("黄忠", 100, "凤嘴刀", 22, 0.95),
    ]

    for name, max_hp, weapon_name, damage, accuracy in warriors:
        entity = world.create_entity()
        world.add_component(entity, NameComponent(name=name))
        world.add_component(
            entity, HealthComponent(max_health=max_hp, current_health=max_hp)
        )
        world.add_component(
            entity,
            WeaponComponent(weapon_name=weapon_name, damage=damage, accuracy=accuracy),
        )
        world.add_component(entity, ExperienceComponent())

        print(
            f"创建战士: {name} - 生命值:{max_hp} - 武器:{weapon_name}(伤害:{damage}, 命中率:{accuracy*100}%)"
        )

    print(f"\n创建了 {len(warriors)} 个战士，战斗即将开始！")
    print("观察事件如何在系统间传递...")

    # 游戏循环
    try:
        last_time = time.time()
        while True:
            current_time = time.time()
            delta_time = current_time - last_time
            last_time = current_time

            # 更新世界
            world.update(delta_time)

            # 控制更新频率
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n战斗结束!")


if __name__ == "__main__":
    main()
