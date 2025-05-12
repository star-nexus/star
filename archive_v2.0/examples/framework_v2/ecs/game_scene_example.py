import logging
import time
import random
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich import box

from framework_v2.ecs.world import World
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.system import System
from framework_v2.ecs.context import ECSContext
from framework_v2.engine.events import EventManager, EventMessage

# 配置 Rich 日志处理
FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger("rich")
console = Console()

# 定义组件
class CharacterComponent(Component):
    def __init__(self, name, faction, level=1):
        self.name = name
        self.faction = faction
        self.level = level

class AttributeComponent(Component):
    def __init__(self, strength=10, intelligence=10, leadership=10):
        self.strength = strength
        self.intelligence = intelligence
        self.leadership = leadership

class PositionComponent(Component):
    def __init__(self, x=0, y=0, region=""):
        self.x = x
        self.y = y
        self.region = region

class ArmyComponent(Component):
    def __init__(self, troops=1000, morale=100, training=50):
        self.troops = troops
        self.morale = morale
        self.training = training

class StatusComponent(Component):
    def __init__(self):
        self.statuses = []  # 例如："行军中", "休整中", "战斗中"

# 定义系统
class MovementSystem(System):
    def __init__(self):
        super().__init__([CharacterComponent, PositionComponent, StatusComponent],priority=10)
        self.logger = logging.getLogger("MovementSystem")
        
    def update(self, delta_time):
        # 使用新的查询接口
        for entity, (character, position, status) in self.context.with_all(
            CharacterComponent, PositionComponent, StatusComponent
        ).iter_components(CharacterComponent, PositionComponent, StatusComponent):
            # 如果角色正在行军
            if "行军中" in status.statuses:
                # 模拟移动
                position.x += (random.random() - 0.5) * 10 * delta_time
                position.y += (random.random() - 0.5) * 10 * delta_time
                
                # 随机更改区域
                if random.random() < 0.1:
                    regions = ["荆州", "益州", "幽州", "冀州", "青州", "兖州", "徐州", "扬州", "交州"]
                    position.region = random.choice(regions)
                
                self.logger.info(f"[bold]{character.name}[/bold] 正在 [green]{position.region}[/green] 行军，位置: ({position.x:.1f}, {position.y:.1f})")

class ArmySystem(System):
    def __init__(self):
        super().__init__([CharacterComponent, ArmyComponent, StatusComponent],priority=8)
        self.logger = logging.getLogger("ArmySystem")
        
    def update(self, delta_time):
        # 使用新的查询接口
        for entity, (character, army, status) in self.context.with_all(
            CharacterComponent, ArmyComponent, StatusComponent
        ).iter_components(CharacterComponent, ArmyComponent, StatusComponent):
            # 如果军队在休整
            if "休整中" in status.statuses:
                # 提高士力和训练
                army.morale = min(100, army.morale + 5 * delta_time)
                army.training = min(100, army.training + 2 * delta_time)
                
                # 补充兵力
                army.troops = min(5000, army.troops + 100 * delta_time)
                
                self.logger.info(f"[bold]{character.name}[/bold] 的军队正在休整: [blue]兵力[/blue]={army.troops:.0f}, [yellow]士气[/yellow]={army.morale:.1f}, [green]训练[/green]={army.training:.1f}")
            
            # 如果军队在战斗
            elif "战斗中" in status.statuses:
                # 降低士力和兵力
                army.morale = max(10, army.morale - 10 * delta_time)
                army.troops = max(100, army.troops - 200 * delta_time)
                
                self.logger.info(f"[bold red]{character.name}[/bold red] 的军队正在战斗: [blue]兵力[/blue]={army.troops:.0f}, [yellow]士气[/yellow]={army.morale:.1f}")

class BattleSystem(System):
    def __init__(self):
        super().__init__([CharacterComponent, PositionComponent, ArmyComponent, StatusComponent], priority=5)
        self.logger = logging.getLogger("BattleSystem")
        self.battle_timer = 0
        self.pending_battles = []  # 存储待处理的战斗
        
    def update(self, delta_time):
        self.battle_timer += delta_time
        
        # 处理待结束的战斗
        if self.pending_battles:
            new_pending_battles = []
            for battle in self.pending_battles:
                battle['time'] -= delta_time
                if battle['time'] <= 0:
                    # 时间到，结束战斗
                    self.end_battle(battle['attacker'], battle['defender'])
                else:
                    # 继续等待
                    new_pending_battles.append(battle)
            self.pending_battles = new_pending_battles
        
        # 每3秒检查一次是否发生战斗
        if self.battle_timer >= 3:
            self.battle_timer = 0
            
            # 获取所有角色
            entities = self.context.with_all(
                CharacterComponent, PositionComponent, ArmyComponent, StatusComponent
            ).result()
            
            # 如果有足够的角色，随机选择两个进行战斗
            if len(entities) >= 2:
                attacker_idx = random.randint(0, len(entities) - 1)
                defender_idx = random.randint(0, len(entities) - 1)
                
                # 确保攻击者和防御者不是同一个
                while attacker_idx == defender_idx:
                    defender_idx = random.randint(0, len(entities) - 1)
                
                attacker = entities[attacker_idx]
                defender = entities[defender_idx]
                
                attacker_char = self.context.get_component(attacker, CharacterComponent)
                defender_char = self.context.get_component(defender, CharacterComponent)
                
                attacker_status = self.context.get_component(attacker, StatusComponent)
                defender_status = self.context.get_component(defender, StatusComponent)
                
                # 开始战斗
                attacker_status.statuses = ["战斗中"]
                defender_status.statuses = ["战斗中"]
                
                self.logger.info(f"[bold red]战斗爆发![/bold red] [bold]{attacker_char.name}[/bold] 攻击了 [bold]{defender_char.name}[/bold]")
                
                # 使用 publish 方法发送事件消息
                battle_event = EventMessage(
                    type="battle_start",
                    data={
                        "attacker": attacker,
                        "defender": defender
                    }
                )
                self.context.publish(battle_event)
                
                # 3秒后结束战斗 - 使用自定义的延迟机制
                self.pending_battles.append({
                    'attacker': attacker,
                    'defender': defender,
                    'time': 3.0  # 3秒后结束
                })
    
    def end_battle(self, attacker, defender):
        attacker_char = self.context.get_component(attacker, CharacterComponent)
        defender_char = self.context.get_component(defender, CharacterComponent)
        
        attacker_status = self.context.get_component(attacker, StatusComponent)
        defender_status = self.context.get_component(defender, StatusComponent)
        
        # 结束战斗，进入休整状态
        attacker_status.statuses = ["休整中"]
        defender_status.statuses = ["休整中"]
        
        # 随机决定胜负
        if random.random() < 0.5:
            winner, loser = attacker_char, defender_char
        else:
            winner, loser = defender_char, attacker_char
            
        self.logger.info(f"[bold green]战斗结束![/bold green] [bold]{winner.name}[/bold] 击败了 [bold]{loser.name}[/bold]")


def create_character(world, name, faction, strength, intelligence, leadership, troops, x, y, region, status):
    # 使用 context 的便捷方法
    entity = world.create_entity()
    
    world.add_component(entity, CharacterComponent(name, faction, level=random.randint(1, 10)))
    world.add_component(entity, AttributeComponent(strength, intelligence, leadership))
    world.add_component(entity, PositionComponent(x, y, region))
    world.add_component(entity, ArmyComponent(troops, random.randint(70, 100), random.randint(50, 90)))
    
    status_comp = StatusComponent()
    status_comp.statuses.append(status)
    world.add_component(entity, status_comp)
    
    return entity

def main():
    layout = Layout()
    layout.split_column(
        Layout(Panel.fit("[bold magenta]三国志 ECS 框架示例[/bold magenta]", border_style="cyan"), size=3),
        Layout(name="main")
    )
    console.print(layout)
    
    # 创建世界
    world = World()
    logger.info("创建三国志世界")
    
    # 创建事件管理器
    event_manager = EventManager()
    world.event_manager = event_manager
    world.context.event_manager = event_manager
    
    # 添加系统
    world.add_system(MovementSystem())
    world.add_system(ArmySystem())
    world.add_system(BattleSystem())
    
    logger.info(f"添加了 [bold green]{world.system_manager.get_system_count()}[/bold green] 个系统")
    
    # 创建角色
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("创建武将...", total=None)
        
        # 蜀国武将
        create_character(world, "刘备", "蜀", 70, 85, 95, 3000, 10, 20, "益州", "行军中")
        create_character(world, "关羽", "蜀", 95, 75, 80, 2500, 15, 25, "荆州", "战斗中")
        create_character(world, "张飞", "蜀", 97, 65, 75, 2000, 12, 18, "益州", "休整中")
        
        # 魏国武将
        create_character(world, "曹操", "魏", 75, 95, 95, 4000, 50, 60, "兖州", "休整中")
        create_character(world, "夏侯惇", "魏", 90, 70, 80, 2800, 55, 65, "冀州", "行军中")
        create_character(world, "许褚", "魏", 93, 60, 70, 2200, 52, 58, "兖州", "战斗中")
        
        # 吴国武将
        create_character(world, "孙权", "吴", 75, 85, 90, 3500, 90, 80, "扬州", "休整中")
        create_character(world, "周瑜", "吴", 80, 95, 85, 2000, 95, 85, "扬州", "行军中")
        create_character(world, "太史慈", "吴", 90, 75, 80, 1800, 92, 78, "扬州", "战斗中")
    
    # 显示武将信息
    table = Table(title="三国武将", box=box.ROUNDED)
    table.add_column("姓名", style="cyan", no_wrap=True)
    table.add_column("势力", style="magenta")
    table.add_column("武力", justify="center", style="red")
    table.add_column("智力", justify="center", style="green")
    table.add_column("统率", justify="center", style="yellow")
    table.add_column("兵力", justify="right", style="blue")
    table.add_column("地区", style="cyan")
    table.add_column("状态", style="bold")
    
    # 使用新的查询接口
    for entity, (char, attr, pos, army, status) in world.context.with_all(
        CharacterComponent, AttributeComponent, PositionComponent, ArmyComponent, StatusComponent
    ).iter_components(CharacterComponent, AttributeComponent, PositionComponent, ArmyComponent, StatusComponent):
        table.add_row(
            char.name,
            char.faction,
            str(attr.strength),
            str(attr.intelligence),
            str(attr.leadership),
            f"{army.troops:,}",
            pos.region,
            ", ".join(status.statuses)
        )
    
    console.print(table)
    
    # 模拟游戏循环
    console.print(Panel.fit("[bold yellow]开始模拟三国世界[/bold yellow]", border_style="yellow"))
    
    for i in range(10):
        delta_time = 1.0
        logger.info(f"[bold]第 {i+1} 回合[/bold] (时间流逝: {delta_time})")
        
        # # 更新事件管理器
        # event_manager.update()
        
        # 更新世界
        world.update(delta_time)
        
        # 暂停以便观察输出
        time.sleep(1.5)
    
    # 显示最终状态
    console.print(Panel.fit("[bold green]模拟完成[/bold green]", border_style="green"))
    
    # 显示最终武将信息
    final_table = Table(title="三国武将最终状态", box=box.ROUNDED)
    final_table.add_column("姓名", style="cyan", no_wrap=True)
    final_table.add_column("势力", style="magenta")
    final_table.add_column("兵力", justify="right", style="blue")
    final_table.add_column("士气", justify="center", style="yellow")
    final_table.add_column("训练", justify="center", style="green")
    final_table.add_column("地区", style="cyan")
    final_table.add_column("状态", style="bold")
    
    # 使用新的查询接口
    for entity, (char, pos, army, status) in world.context.with_all(
        CharacterComponent, PositionComponent, ArmyComponent, StatusComponent
    ).iter_components(CharacterComponent, PositionComponent, ArmyComponent, StatusComponent):
        final_table.add_row(
            char.name,
            char.faction,
            f"{army.troops:.0f}",
            f"{army.morale:.1f}",
            f"{army.training:.1f}",
            pos.region,
            ", ".join(status.statuses)
        )
    
    console.print(final_table)

if __name__ == "__main__":
    main()