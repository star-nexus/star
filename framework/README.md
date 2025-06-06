# Game Framework 游戏框架

一个基于 Entity-Component-System (ECS) 架构的 Python 游戏开发框架，专为构建复杂的策略游戏而设计。

## 目录

- [设计架构](#设计架构)
- [设计思路](#设计思路)
- [目录结构](#目录结构)
- [架构图](#架构图)
- [使用方法](#使用方法)
- [示例代码](#示例代码)

## 设计架构

本框架采用 **Entity-Component-System (ECS)** 架构模式，结合现代游戏引擎设计理念，提供了一个模块化、可扩展的游戏开发平台。

### 核心架构组件

1. **ECS 系统 (`ecs/`)**

   - **Entity（实体）**: 游戏中的基本对象，使用整数 ID 表示
   - **Component（组件）**: 纯数据容器，存储游戏对象的属性
   - **System（系统）**: 包含游戏逻辑，处理具有特定组件的实体
   - **World（世界）**: ECS 的核心管理器，协调所有实体、组件和系统

2. **游戏引擎 (`engine/`)**

   - **Engine**: 主游戏引擎，管理游戏循环和核心系统
   - **SceneManager**: 场景管理器，处理不同游戏场景的切换
   - **EventManager**: 事件管理器，实现发布-订阅模式的系统间通信
   - **RenderManager**: 渲染管理器，处理图形渲染
   - **InputManager**: 输入管理器，处理用户输入

3. **用户界面 (`ui/`)**

   - **UI Components**: 提供按钮、面板、文本等 UI 组件
   - **UI Systems**: 处理 UI 逻辑的系统

4. **工具模块 (`utils/`)**
   - **Logging**: 日志系统，用于调试和错误追踪

## 设计思路

### 1. 模块化设计

框架采用高度模块化的设计，每个模块职责单一，便于维护和扩展。通过依赖注入和上下文对象实现模块间的松耦合。

### 2. 数据与逻辑分离

严格遵循 ECS 架构原则：

- **组件只存储数据**，不包含任何业务逻辑
- **系统只包含逻辑**，通过查询组件来处理实体
- **实体只是 ID**，作为组件的容器

### 3. 事件驱动架构

采用事件驱动模式实现系统间通信，降低系统耦合度，提高代码可维护性。

### 4. 场景管理

支持多场景切换，每个场景可以有独立的实体、组件和系统，便于构建复杂的游戏状态。

### 5. 并发支持

内置线程池支持，可以并发执行耗时操作，提高游戏性能。

## 目录结构

```
framework/
├── README.md                 # 本文档
├── __init__.py              # 模块初始化文件
├── ecs/                     # ECS 核心模块
│   ├── __init__.py
│   ├── component.py         # 组件基类定义
│   ├── context.py           # ECS 上下文管理
│   ├── entity.py            # 实体定义（整数 ID）
│   ├── manager.py           # 实体、组件、系统管理器
│   ├── query.py             # 组件查询系统
│   ├── system.py            # 系统基类定义
│   └── world.py             # ECS 世界容器
├── engine/                  # 游戏引擎模块
│   ├── __init__.py
│   ├── engine.py            # 主游戏引擎
│   ├── events.py            # 事件管理系统
│   ├── inputs.py            # 输入管理系统
│   ├── renders.py           # 渲染管理系统
│   └── scenes.py            # 场景管理系统
├── ui/                      # 用户界面模块
│   ├── __init__.py
│   ├── components/          # UI 组件定义
│   │   ├── __init__.py
│   │   └── ui_components.py # 按钮、面板、文本等 UI 组件
│   └── systems/             # UI 系统
│       └── __init__.py
└── utils/                   # 工具模块
    ├── __init__.py
    └── logging.py           # 日志系统
```

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Game Engine                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │SceneManager │ │EventManager │ │RenderManager│ │InputMgr │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│                        ECS World                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │EntityManager│ │ComponentMgr │ │SystemManager│ │QueryMgr │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Game Systems                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │RenderSystem │ │MovementSys  │ │CombatSystem │ │UISystems│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│                   Game Components                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │Position     │ │Velocity     │ │Health       │ │UITransf │ │
│  │Component    │ │Component    │ │Component    │ │Component│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────────┤
│                      Entities                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │ Entity 001  │ │ Entity 002  │ │ Entity 003  │ │   ...   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 数据流图

```
用户输入 → InputManager → EventManager → Systems → Components → Entities
                             ↓
                      RenderManager → 屏幕输出
```

## 使用方法

### 1. 基本设置

```python
from framework.engine.engine import Engine
from framework.ecs.world import World

# 创建游戏引擎
engine = Engine(title="我的游戏", width=1024, height=768, fps=60)

# 获取世界实例
world = engine.world
```

### 2. 创建组件

```python
from dataclasses import dataclass
from framework.ecs.component import Component

@dataclass
class PositionComponent(Component):
    x: float = 0.0
    y: float = 0.0

@dataclass
class HealthComponent(Component):
    max_health: int = 100
    current_health: int = 100
```

### 3. 创建系统

```python
from framework.ecs.system import System
from framework.ecs.entity import Entity

class MovementSystem(System):
    def __init__(self):
        # 指定系统需要的组件类型
        super().__init__([PositionComponent, VelocityComponent])

    def update(self, delta_time: float) -> None:
        if not self.context:
            return

        # 查询具有所需组件的实体
        entities = self.context.query_manager.query_entities(
            self.required_components
        )

        for entity in entities:
            position = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            velocity = self.context.component_manager.get_component(
                entity, VelocityComponent
            )

            # 更新位置
            position.x += velocity.x * delta_time
            position.y += velocity.y * delta_time
```

### 4. 创建场景

```python
from framework.engine.scenes import Scene

class GameScene(Scene):
    def enter(self, **kwargs):
        super().enter(**kwargs)

        # 添加系统
        self.world.add_system(MovementSystem())

        # 创建实体
        player = self.world.create_entity()
        self.world.add_component(player, PositionComponent(x=100, y=100))
        self.world.add_component(player, HealthComponent())

    def update(self, delta_time: float):
        # 更新世界（会调用所有系统的 update 方法）
        self.world.update(delta_time)
```

### 5. 启动游戏

```python
# 注册场景
engine.scene_manager.add_scene("game", GameScene)

# 加载初始场景
engine.scene_manager.load_scene("game")

# 启动游戏循环
engine.start()
```

### 6. 事件系统使用

```python
from framework.engine.events import EventManager, EventType

# 订阅事件
def on_unit_created(event):
    print(f"单位创建: {event.data}")

engine.event_manager.subscribe(EventType.UNIT_CREATED, on_unit_created)

# 发布事件
engine.event_manager.publish(EventType.UNIT_CREATED, {"unit_id": 123})
```

## 示例代码

### 完整的简单游戏示例

```python
from dataclasses import dataclass
from framework.engine.engine import Engine
from framework.engine.scenes import Scene
from framework.ecs.component import Component
from framework.ecs.system import System

# 定义组件
@dataclass
class PositionComponent(Component):
    x: float = 0.0
    y: float = 0.0

@dataclass
class VelocityComponent(Component):
    x: float = 0.0
    y: float = 0.0

# 定义系统
class MovementSystem(System):
    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = self.context.query_manager.query_entities(
            self.required_components
        )

        for entity in entities:
            pos = self.context.component_manager.get_component(
                entity, PositionComponent
            )
            vel = self.context.component_manager.get_component(
                entity, VelocityComponent
            )

            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time

# 定义场景
class SimpleGameScene(Scene):
    def enter(self, **kwargs):
        super().enter(**kwargs)

        # 添加系统
        self.world.add_system(MovementSystem())

        # 创建移动的实体
        entity = self.world.create_entity()
        self.world.add_component(entity, PositionComponent(x=0, y=0))
        self.world.add_component(entity, VelocityComponent(x=50, y=30))

    def update(self, delta_time: float):
        self.world.update(delta_time)

# 主程序
def main():
    engine = Engine(title="简单游戏", width=800, height=600)
    engine.scene_manager.add_scene("simple", SimpleGameScene)
    engine.scene_manager.load_scene("simple")
    engine.start()

if __name__ == "__main__":
    main()
```

## 扩展指南

### 添加新组件

1. 继承 `Component` 基类
2. 使用 `@dataclass` 装饰器定义数据字段
3. 确保组件只包含数据，不包含逻辑

### 添加新系统

1. 继承 `System` 基类
2. 在构造函数中指定所需的组件类型
3. 实现 `update` 方法处理业务逻辑
4. 通过 `context.query_manager` 查询符合条件的实体

### 添加新场景

1. 继承 `Scene` 基类
2. 实现 `enter` 方法初始化场景
3. 实现 `update` 方法更新场景逻辑
4. 通过 `SceneManager` 注册和切换场景

这个框架为构建复杂的策略游戏提供了坚实的基础，支持模块化开发、易于扩展和维护。
