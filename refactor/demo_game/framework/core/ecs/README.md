# 游戏开发框架

这是一个基于ECS（Entity-Component-System）架构的游戏开发框架，提供了清晰的架构设计和易用的API，帮助开发者构建结构良好的游戏项目。

## 核心概念

### ECS架构

框架采用ECS（实体-组件-系统）架构，将游戏对象的数据和行为分离，提供更好的代码组织和性能优化：

- **实体（Entity）**：游戏对象的唯一标识符，本身不包含任何数据或行为
- **组件（Component）**：纯数据容器，附加到实体上，定义实体的属性
- **系统（System）**：包含游戏逻辑，处理拥有特定组件的实体

### 世界（World）

世界是ECS的核心容器，管理所有实体、组件和系统之间的关系：

- 创建和销毁实体
- 添加和移除组件
- 注册和注销系统
- 协调系统的更新顺序

## 快速开始

### 1. 定义组件

```python
from dataclasses import dataclass

@dataclass
class Position:
    x: float
    y: float

@dataclass
class Velocity:
    x: float
    y: float
```

### 2. 创建系统

```python
from framework.core.ecs.system import System

class MovementSystem(System):
    def __init__(self):
        super().__init__([Position, Velocity])
    
    def update(self, delta_time: float):
        for entity in self.world.get_entities_with_components(Position, Velocity):
            pos = self.world.get_component(entity, Position)
            vel = self.world.get_component(entity, Velocity)
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time
```

### 3. 使用世界管理游戏对象

```python
from framework.core.ecs.world import World

# 创建世界实例
world = World()

# 创建实体
entity = world.create_entity()

# 添加组件
world.add_component(entity, Position(0, 0))
world.add_component(entity, Velocity(1, 1))

# 注册系统
world.add_system(MovementSystem())

# 更新世界
world.update(delta_time)
```

## API文档

### Entity

实体类提供唯一标识符功能：

- `__init__()`: 创建新实体，自动分配唯一ID
- `__hash__()`: 支持实体作为字典键使用

### Component

组件基类定义了组件的基本接口：

- `__init__()`: 初始化组件，子类应该定义具体的数据属性

### System

系统基类提供了以下功能：

- `__init__(required_components, priority=0)`: 初始化系统，指定所需组件和优先级
- `update(delta_time)`: 更新系统逻辑（抽象方法）
- `is_enabled()`: 检查系统是否启用
- `set_enabled(enabled)`: 设置系统启用状态

### World

世界类提供了完整的ECS管理功能：

- `create_entity()`: 创建新实体
- `remove_entity(entity)`: 移除实体及其所有组件
- `add_component(entity, component)`: 为实体添加组件
- `remove_component(entity, component_type)`: 移除实体的指定组件
- `get_component(entity, component_type)`: 获取实体的指定组件
- `has_component(entity, component_type)`: 检查实体是否拥有指定组件
- `add_system(system)`: 注册系统
- `remove_system(system)`: 注销系统
- `update(delta_time)`: 更新所有启用的系统
- `get_entities_with_components(*component_types)`: 获取拥有指定组件的实体列表

## 最佳实践

1. 组件设计
   - 组件应该只包含数据，不包含行为逻辑
   - 使用dataclass简化组件定义
   - 避免在组件中保存实体引用

2. 系统实现
   - 系统应该只关注特定的功能
   - 合理设置系统优先级确保正确的更新顺序
   - 使用is_enabled控制系统的启用状态

3. 实体管理
   - 及时移除不需要的实体和组件
   - 使用get_entities_with_components高效查询实体
   - 避免在组件中存储实体间的直接引用