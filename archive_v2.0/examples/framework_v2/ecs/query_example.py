import logging
from dataclasses import dataclass
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from framework_v2.ecs.world import World
from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component
from framework_v2.ecs.query import QueryManager

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
class HealthComponent(Component):
    health: float = 100

@dataclass
class TagComponent(Component):
    tag: str = ""

def main():
    console.print(Panel.fit("[bold magenta]QueryManager 使用示例[/bold magenta]", border_style="cyan"))
    
    # 创建世界
    world = World()
    logger.info("创建 ECS 世界")
    
    # 获取查询管理器
    query_manager = world.query_manager
    
    # 创建一些实体并添加组件
    logger.info("创建实体并添加组件")
    
    # 实体1: 位置 + 生命值
    entity1 = world.entity_manager.create_entity()
    world.component_manager.add_component(entity1, PositionComponent(10, 20))
    world.component_manager.add_component(entity1, HealthComponent(100))
    
    # 实体2: 位置 + 标签
    entity2 = world.entity_manager.create_entity()
    world.component_manager.add_component(entity2, PositionComponent(30, 40))
    world.component_manager.add_component(entity2, TagComponent("玩家"))
    
    # 实体3: 生命值 + 标签
    entity3 = world.entity_manager.create_entity()
    world.component_manager.add_component(entity3, HealthComponent(50))
    world.component_manager.add_component(entity3, TagComponent("敌人"))
    
    # 实体4: 位置 + 生命值 + 标签
    entity4 = world.entity_manager.create_entity()
    world.component_manager.add_component(entity4, PositionComponent(50, 60))
    world.component_manager.add_component(entity4, HealthComponent(80))
    world.component_manager.add_component(entity4, TagComponent("NPC"))
    
    # 显示所有实体
    table = Table(title="所有实体")
    table.add_column("实体ID", style="cyan")
    table.add_column("组件", style="green")
    
    for entity in world.entity_manager.entities:
        components = world.component_manager.get_all_component(entity)
        component_str = ", ".join(f"{type(comp).__name__}({', '.join([f'{k}={v}' for k, v in comp.__dict__.items() if not k.startswith('_')])})" for comp in components)
        table.add_row(str(entity), component_str)
    
    console.print(table)
    
    # 示例1: 使用 with_all 方法查询
    console.print("\n[bold]示例1: 使用 with_all 方法查询[/bold]")
    query = query_manager.with_all(PositionComponent)
    results = query.result()
    logger.info(f"拥有位置组件的实体: {results}")
    
    # 示例2: 链式调用查询方法
    console.print("\n[bold]示例2: 链式调用查询方法[/bold]")
    query = query_manager.query().with_all(PositionComponent).with_all(HealthComponent)
    results = query.result()
    logger.info(f"同时拥有位置和生命值组件的实体: {results}")
    
    # 示例3: 使用 without 排除特定组件
    console.print("\n[bold]示例3: 使用 without 排除特定组件[/bold]")
    query = query_manager.query().with_all(PositionComponent).without(TagComponent)
    results = query.result()
    logger.info(f"拥有位置组件但没有标签组件的实体: {results}")
    
    # 示例4: 使用 with_any 查询至少包含其中一个组件的实体
    console.print("\n[bold]示例4: 使用 with_any 查询至少包含其中一个组件的实体[/bold]")
    query = query_manager.query().with_any(HealthComponent, TagComponent)
    results = query.result()
    logger.info(f"至少拥有生命值或标签组件的实体: {results}")
    
    # 示例5: 使用 iter_components 方法迭代查询结果
    console.print("\n[bold]示例5: 使用 iter_components 方法迭代查询结果[/bold]")
    query = query_manager.with_all(PositionComponent, HealthComponent)
    logger.info("迭代拥有位置和生命值组件的实体:")
    for entity, (position, health) in query.iter_components(PositionComponent, HealthComponent):
        logger.info(f"实体 {entity}: 位置({position.x}, {position.y}), 生命值({health.health})")
    
    # 示例6: 使用 iter_components 方法迭代特定组件
    console.print("\n[bold]示例6: 使用 iter_components 方法迭代特定组件[/bold]")
    query = query_manager.with_all(PositionComponent, HealthComponent, TagComponent)
    logger.info("迭代拥有位置、生命值和标签组件的实体的位置和标签:")
    for entity, (position, tag) in query.iter_components(PositionComponent, TagComponent):
        logger.info(f"实体 {entity}: 位置({position.x}, {position.y}), 标签({tag.tag})")
    
    # 示例7: 使用 count 方法获取匹配实体数量
    console.print("\n[bold]示例7: 使用 count 方法获取匹配实体数量[/bold]")
    query = query_manager.with_all(TagComponent)
    count = query.count()
    logger.info(f"拥有标签组件的实体数量: {count}")
    
    # 示例8: 使用 first 方法获取第一个匹配的实体
    console.print("\n[bold]示例8: 使用 first 方法获取第一个匹配的实体[/bold]")
    query = query_manager.with_all(HealthComponent, TagComponent)
    first_entity = query.first()
    if first_entity is not None:
        health = world.component_manager.get_component(first_entity, HealthComponent)
        tag = world.component_manager.get_component(first_entity, TagComponent)
        logger.info(f"第一个同时拥有生命值和标签组件的实体: {first_entity}, 生命值({health.health}), 标签({tag.tag})")
    else:
        logger.info("没有找到同时拥有生命值和标签组件的实体")
    
    # 示例9: 使用 for_each 方法对每个匹配的实体执行操作
    console.print("\n[bold]示例9: 使用 for_each 方法对每个匹配的实体执行操作[/bold]")
    query = query_manager.with_all(HealthComponent)
    
    def heal_entity(entity, components):
        health = next(comp for comp in components if isinstance(comp, HealthComponent))
        old_health = health.health
        health.health = min(100, health.health + 20)
        logger.info(f"治疗实体 {entity}: 生命值从 {old_health} 增加到 {health.health}")
    
    logger.info("对所有拥有生命值组件的实体进行治疗:")
    query.for_each(heal_entity)
    
    # 示例10: 缓存查询
    console.print("\n[bold]示例10: 缓存查询[/bold]")
    query = query_manager.with_all(PositionComponent).build()
    query_manager.cache_query("position_query", query)
    
    cached_query = query_manager.get_cached_query("position_query")
    if cached_query:
        results = cached_query.result()
        logger.info(f"从缓存中获取拥有位置组件的实体: {results}")
    
    # 示例11: 使查询缓存失效
    console.print("\n[bold]示例11: 使查询缓存失效[/bold]")
    query_manager.invalidate_all_caches()
    logger.info("所有查询缓存已失效")
    
    # 示例12: 清除查询缓存
    console.print("\n[bold]示例12: 清除查询缓存[/bold]")
    query_manager.clear_cache()
    logger.info("所有查询缓存已清除")
    
    # 示例13: 使用 where 方法添加自定义过滤条件
    console.print("\n[bold]示例13: 使用 where 方法添加自定义过滤条件[/bold]")
    query = query_manager.with_all(HealthComponent).where(
        lambda entity, components: next(comp for comp in components if isinstance(comp, HealthComponent)).health > 70
    )
    results = query.result()
    logger.info(f"生命值大于70的实体: {results}")
    
    # 示例14: 使用 order_by 方法排序结果
    console.print("\n[bold]示例14: 使用 order_by 方法排序结果[/bold]")
    query = query_manager.with_all(HealthComponent).order_by(
        lambda entity, components: next(comp for comp in components if isinstance(comp, HealthComponent)).health
    )
    logger.info("按生命值从低到高排序的实体:")
    for entity, (health,) in query.iter_components(HealthComponent):
        logger.info(f"实体 {entity}: 生命值({health.health})")
    
    # 示例15: 使用 limit 方法限制结果数量
    console.print("\n[bold]示例15: 使用 limit 方法限制结果数量[/bold]")
    query = query_manager.with_all(PositionComponent).limit(2)
    results = query.result()
    logger.info(f"限制最多2个拥有位置组件的实体: {results}")
    
    # 示例16: 使用 on_change 方法注册变化回调
    console.print("\n[bold]示例16: 使用 on_change 方法注册变化回调[/bold]")
    query = query_manager.with_all(TagComponent).build()
    
    def on_tag_entities_change(entities):
        logger.info(f"拥有标签组件的实体列表变化: {entities}")
    
    query.on_change(on_tag_entities_change)
    logger.info("注册了拥有标签组件的实体变化回调")
    
    # 触发变化
    logger.info("添加一个新的带标签的实体，触发变化回调")
    entity5 = world.entity_manager.create_entity()
    world.component_manager.add_component(entity5, TagComponent("新实体"))
    query.invalidate_cache()  # 手动使缓存失效，触发重新查询
    query.result()  # 执行查询，触发回调
    
    console.print(Panel.fit("[bold green]QueryManager 示例完成[/bold green]", border_style="green"))

if __name__ == "__main__":
    main()