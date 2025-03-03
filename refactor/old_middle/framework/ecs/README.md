# 实体-组件-系统 (ECS) 模块

该模块实现了实体-组件-系统架构，支持高效、解耦的游戏对象管理。

## 组件

- **entity.py**: 实体类，作为游戏对象的唯一标识符
- **component.py**: 组件基类，用于存储实体数据
- **system.py**: 系统基类，用于处理具有特定组件的实体
- **world.py**: 世界容器，管理所有实体和系统

## ECS架构介绍

- **实体(Entity)**: 仅由唯一ID标识的游戏对象
- **组件(Component)**: 纯数据容器，不包含逻辑
- **系统(System)**: 处理特定组件组合的实体的逻辑处理器
- **世界(World)**: 管理所有实体和系统的容器

## 使用示例

```python
# 创建ECS世界
world = World()

# 创建实体
player = world.create_entity()

# 添加组件
player.add_component(TransformComponent(x=100, y=100))
player.add_component(SpriteComponent("player.png"))
player.add_component(PlayerControlComponent())

# 注册系统
world.register_system(MovementSystem())
world.register_system(RenderSystem())

# 在游戏循环中更新世界
def game_loop():
    while running:
        delta_time = calculate_delta_time()
        world.update(delta_time)
```
