import logging
from dataclasses import dataclass
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from framework_v2.ecs.world import World
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.system import System
from framework_v2.ecs.context import ECSContext



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

# 定义一些组件
@dataclass
class PositionComponent(Component):
    x: float = 0
    y: float = 0

@dataclass
class VelocityComponent(Component):
    vx: float = 0
    vy: float = 0

@dataclass
class HealthComponent(Component):
    health: float = 100
    max_health: float = 100

@dataclass
class NameComponent(Component):
    name: str = "Entity"

# 定义一些系统
class MovementSystem(System):
    def __init__(self):
        # 修复：添加所需组件类型参数
        super().__init__([PositionComponent, VelocityComponent], priority=10)

        self.logger = logging.getLogger("MovementSystem")
    
    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, context: ECSContext):
        self._context = context

    
    def update(self, delta_time):
        # 使用新的查询接口
        for entity, (position, velocity) in self.context.with_all(
            PositionComponent, VelocityComponent
        ).iter_components(PositionComponent, VelocityComponent):
            # 更新位置
            position.x += velocity.vx * delta_time
            position.y += velocity.vy * delta_time
            
            # 记录移动
            if hasattr(entity, 'id'):
                entity_id = entity.id
            else:
                entity_id = str(entity)
                
            self.logger.info(f"实体 {entity_id} 移动到 ({position.x:.2f}, {position.y:.2f})")

class HealthSystem(System):
    def __init__(self):
        # 修复：添加所需组件类型参数
        super().__init__([HealthComponent, NameComponent], priority=5)
        self.logger = logging.getLogger("HealthSystem")
    
    def update(self, delta_time):
        # 使用新的查询接口
        for entity, (health, name) in self.context.with_all(
            HealthComponent, NameComponent
        ).iter_components(HealthComponent, NameComponent):
            # 随机恢复生命值
            if health.health < health.max_health:
                health.health = min(health.max_health, health.health + 5 * delta_time)
                self.logger.info(f"{name.name} 恢复生命值到 {health.health:.1f}/{health.max_health}")

class BoundarySystem(System):
    def __init__(self, min_x=-100, max_x=100, min_y=-100, max_y=100):
        # 修复：添加所需组件类型参数
        super().__init__([PositionComponent, VelocityComponent, NameComponent], priority=8)
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.logger = logging.getLogger("BoundarySystem")
    
    def update(self, delta_time):
        # 使用新的查询接口和自定义过滤条件
        query = self.context.with_all(PositionComponent, VelocityComponent).where(
            lambda entity, components: any(
                isinstance(comp, PositionComponent) and (
                    comp.x < self.min_x or comp.x > self.max_x or
                    comp.y < self.min_y or comp.y > self.max_y
                ) for comp in components
            )
        )
        
        for entity, (position, velocity, name) in query.iter_components(
            PositionComponent, VelocityComponent, NameComponent
        ):
            # 检查边界并反弹
            if position.x < self.min_x:
                position.x = self.min_x
                velocity.vx = -velocity.vx
                self.logger.info(f"{name.name} 在 X 轴左边界反弹")
            elif position.x > self.max_x:
                position.x = self.max_x
                velocity.vx = -velocity.vx
                self.logger.info(f"{name.name} 在 X 轴右边界反弹")
                
            if position.y < self.min_y:
                position.y = self.min_y
                velocity.vy = -velocity.vy
                self.logger.info(f"{name.name} 在 Y 轴下边界反弹")
            elif position.y > self.max_y:
                position.y = self.max_y
                velocity.vy = -velocity.vy
                self.logger.info(f"{name.name} 在 Y 轴上边界反弹")

def main():
    console.print(Panel.fit("[bold magenta]ECS 基础示例[/bold magenta]", border_style="cyan"))
    
    # 创建世界
    world = World()
    logger.info("创建 ECS 世界")
    
    # 添加系统
    world.add_system(MovementSystem())
    world.add_system(HealthSystem())
    world.add_system(BoundarySystem(min_x=-50, max_x=50, min_y=-50, max_y=50))
    
    logger.info(f"添加了 {world.system_manager.get_system_count()} 个系统")
    
    # 创建一些实体
    logger.info("创建实体")
    
    # 实体1: 位置 + 速度 + 生命值 + 名称
    entity1 = world.create_entity()
    world.add_component(entity1, PositionComponent(10, 20))
    world.add_component(entity1, VelocityComponent(5, 8))
    world.add_component(entity1, HealthComponent(80, 100))
    world.add_component(entity1, NameComponent("玩家"))
    
    # 实体2: 位置 + 速度 + 名称
    entity2 = world.create_entity()
    world.add_component(entity2, PositionComponent(-30, 15))
    world.add_component(entity2, VelocityComponent(-3, 6))
    world.add_component(entity2, NameComponent("敌人"))
    
    # 实体3: 位置 + 生命值 + 名称
    entity3 = world.create_entity()
    world.add_component(entity3, PositionComponent(0, 0))
    world.add_component(entity3, HealthComponent(50, 100))
    world.add_component(entity3, NameComponent("NPC"))
    
    # 实体4: 位置 + 速度 + 生命值 + 名称
    entity4 = world.create_entity()
    world.add_component(entity4, PositionComponent(40, -20))
    world.add_component(entity4, VelocityComponent(-7, -4))
    world.add_component(entity4, HealthComponent(30, 100))
    world.add_component(entity4, NameComponent("怪物"))
    
    # 显示所有实体
    table = Table(title="所有实体")
    table.add_column("实体ID", style="cyan")
    table.add_column("组件", style="green")
    
    for entity in world.entity_manager.entities:
        components = world.get_all_components(entity)
        component_str = ", ".join(f"{type(comp).__name__}({', '.join([f'{k}={v}' for k, v in comp.__dict__.items() if not k.startswith('_')])})" for comp in components)
        table.add_row(str(entity), component_str)
    
    console.print(table)
    
    # 使用查询接口示例
    console.print("\n[bold]查询接口示例[/bold]")
    
    # 示例1: 查询拥有位置组件的实体
    console.print("\n[bold]示例1: 查询拥有位置组件的实体[/bold]")
    entities_with_position = world.context.with_all(PositionComponent).result()
    logger.info(f"拥有位置组件的实体: {entities_with_position}")
    
    # 示例2: 查询同时拥有位置和速度组件的实体
    console.print("\n[bold]示例2: 查询同时拥有位置和速度组件的实体[/bold]")
    entities_with_position_and_velocity = world.context.with_all(PositionComponent, VelocityComponent).result()
    logger.info(f"同时拥有位置和速度组件的实体: {entities_with_position_and_velocity}")
    
    # 示例3: 查询拥有位置组件但没有生命值组件的实体
    console.print("\n[bold]示例3: 查询拥有位置组件但没有生命值组件的实体[/bold]")
    entities_with_position_without_health = world.context.with_all(PositionComponent).without(HealthComponent).result()
    logger.info(f"拥有位置组件但没有生命值组件的实体: {entities_with_position_without_health}")
    
    # 示例4: 使用自定义条件查询
    console.print("\n[bold]示例4: 使用自定义条件查询[/bold]")
    entities_at_boundary = world.context.with_all(PositionComponent).where(
        lambda entity, components: any(
            isinstance(comp, PositionComponent) and (abs(comp.x) > 30 or abs(comp.y) > 30)
            for comp in components
        )
    ).result()
    logger.info(f"位置超出边界(±30)的实体: {entities_at_boundary}")
    
    # 示例5: 迭代特定组件
    console.print("\n[bold]示例5: 迭代特定组件[/bold]")
    logger.info("所有实体的名称和位置:")
    for entity, (name, position) in world.context.with_all(NameComponent, PositionComponent).iter_components(NameComponent, PositionComponent):
        logger.info(f"{name.name}: 位置({position.x}, {position.y})")
    
    # 模拟游戏循环
    console.print(Panel.fit("[bold yellow]开始模拟游戏循环[/bold yellow]", border_style="yellow"))
    
    for i in range(5):
        delta_time = 1.0
        logger.info(f"[bold]第 {i+1} 帧[/bold] (时间增量: {delta_time})")
        
        # 更新世界
        world.update(delta_time)
    
    # 显示最终状态
    console.print(Panel.fit("[bold green]模拟完成[/bold green]", border_style="green"))
    
    # 显示最终实体状态
    final_table = Table(title="实体最终状态")
    final_table.add_column("名称", style="cyan")
    final_table.add_column("位置", style="green")
    final_table.add_column("速度", style="yellow")
    final_table.add_column("生命值", style="red")
    
    # 使用查询接口获取所有实体
    for entity, (name,) in world.context.with_all(NameComponent).iter_components(NameComponent):
        position = world.get_component(entity, PositionComponent)
        velocity = world.get_component(entity, VelocityComponent)
        health = world.get_component(entity, HealthComponent)
        
        pos_str = f"({position.x:.2f}, {position.y:.2f})" if position else "N/A"
        vel_str = f"({velocity.vx:.2f}, {velocity.vy:.2f})" if velocity else "N/A"
        health_str = f"{health.health:.1f}/{health.max_health}" if health else "N/A"
        
        final_table.add_row(name.name, pos_str, vel_str, health_str)
    
    console.print(final_table)
    
    # 演示组件修改
    console.print("\n[bold]组件修改示例[/bold]")
    
    # 获取玩家实体
    player_entity = world.context.with_all(NameComponent).where(
        lambda entity, components: any(
            isinstance(comp, NameComponent) and comp.name == "玩家"
            for comp in components
        )
    ).first()
    
    if player_entity:
        # 修改玩家位置和速度
        player_pos = world.get_component(player_entity, PositionComponent)
        player_vel = world.get_component(player_entity, VelocityComponent)
        
        logger.info(f"修改玩家位置从 ({player_pos.x:.2f}, {player_pos.y:.2f}) 到 (0, 0)")
        logger.info(f"修改玩家速度从 ({player_vel.vx:.2f}, {player_vel.vy:.2f}) 到 (10, 10)")
        
        player_pos.x = 0
        player_pos.y = 0
        player_vel.vx = 10
        player_vel.vy = 10
        
        # 再次更新一帧
        world.update(1.0)
        
        # 显示修改后的位置
        updated_pos = world.get_component(player_entity, PositionComponent)
        logger.info(f"更新后玩家位置: ({updated_pos.x:.2f}, {updated_pos.y:.2f})")
    
    console.print(Panel.fit("[bold green]ECS 基础示例完成[/bold green]", border_style="green"))

if __name__ == "__main__":
    main()