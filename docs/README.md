# Framework V2 - 简化的 ECS 架构

这是一个简化重构的实体-组件-系统(ECS)框架，专注于易用性、性能和最佳实践。

## 主要特性

### ✨ 简化设计

- **单例 World 管理器**: 全局唯一的世界实例，避免传递引用的复杂性
- **简化查询 API**: 直观的组件查询接口，支持链式调用
- **合并管理器**: 减少了管理器的数量，降低复杂性

### 🚀 性能优化

- **查询缓存**: 自动缓存查询结果，提高重复查询性能
- **高效存储**: 使用字典嵌套结构优化组件存储和访问
- **延迟更新**: 只在需要时更新缓存

### 🛡️ 最佳实践

- **符合 ECS 原则**: 清晰的职责分离（实体、组件、系统）
- **类型安全**: 使用 TypeVar 和泛型提供类型提示
- **线程安全**: 单例模式使用线程锁保证安全

## 快速开始

### 基本使用

```python
from framework_v2 import World, get_world
from framework_v2.components import Position, Velocity, Health
from framework_v2.systems import MovementSystem

# 获取世界单例
world = get_world()

# 创建实体
player = world.create_entity()

# 添加组件
world.add_component(player, Position(10, 20, 0))
world.add_component(player, Velocity(1, 0, 0))
world.add_component(player, Health(100, 100))

# 添加系统
world.add_system(MovementSystem())

# 游戏循环
def game_loop():
    delta_time = 0.016  # ~60 FPS
    world.update(delta_time)
```

### 使用 EntityBuilder（推荐）

```python
from framework_v2.utils import EntityBuilder

# 链式API创建实体
player = (EntityBuilder()
          .with_component(Position(10, 20, 0))
          .with_component(Velocity(1, 0, 0))
          .with_component(Health(100, 100))
          .build())
```

### 查询实体

```python
# 查询拥有特定组件的实体
movable_entities = world.query(Position, Velocity)

# 迭代实体和组件
for entity, pos, vel in movable_entities.with_components():
    pos.x += vel.x * delta_time
    pos.y += vel.y * delta_time

# 获取匹配的实体集合
entities = world.query(Health).entities()

# 获取第一个匹配的实体
first_entity = world.query(Position).first()
```

## 核心概念

### 实体 (Entity)

实体是一个简单的整数 ID，用于标识游戏对象。

```python
Entity = int  # 实体就是一个整数
```

### 组件 (Component)

组件是纯数据容器，使用 dataclass 定义。

```python
from dataclasses import dataclass
from framework_v2 import Component

@dataclass
class Position(Component):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class Health(Component):
    current: float = 100.0
    max: float = 100.0
```

### 系统 (System)

系统包含游戏逻辑，处理拥有特定组件的实体。

```python
from framework_v2 import System

class MovementSystem(System):
    def update(self, delta_time: float) -> None:
        # 查询所有可移动的实体
        for entity, pos, vel in self.world.query(Position, Velocity).with_components():
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time
```

## 架构对比

### Framework V1 vs V2

| 特性       | V1                  | V2                 |
| ---------- | ------------------- | ------------------ |
| 管理器数量 | 4 个独立管理器      | 1 个 World 单例    |
| 查询 API   | 复杂的 QueryManager | 简化的 query()方法 |
| 性能优化   | 基础缓存            | 智能查询缓存       |
| 代码复杂度 | 高                  | 低                 |
| 线程安全   | 部分                | 完全               |

### 简化的查询

```python
# V1: 复杂的查询
query_manager = QueryManager(entity_manager, component_manager)
entities = query_manager.query_entities([Position, Velocity])

# V2: 简化的查询
entities = world.query(Position, Velocity).entities()
```

## 内置组件

框架提供了常用的组件：

- `Position`: 位置组件
- `Velocity`: 速度组件
- `Health`: 生命值组件
- `Name`: 名称组件
- `Renderable`: 渲染组件
- `Transform`: 变换组件
- `Collider`: 碰撞体组件

## 内置系统

框架提供了基础系统：

- `MovementSystem`: 移动系统
- `HealthSystem`: 生命值系统
- `SimplePhysicsSystem`: 简单物理系统

## 性能测试

运行性能测试：

```python
from framework_v2.example import performance_test
performance_test()
```

## 示例

查看完整示例：

```bash
python framework_v2/example.py
```

## 设计原则

1. **简单性**: 优先选择简单直观的 API
2. **性能**: 在保持简单的前提下优化性能
3. **扩展性**: 易于添加新的组件和系统
4. **类型安全**: 使用类型提示避免运行时错误
5. **最佳实践**: 遵循 ECS 架构的核心原则

## 未来规划

- [ ] 事件系统
- [ ] 组件序列化
- [ ] 多线程支持
- [ ] 更多内置组件和系统
- [ ] 性能分析工具
