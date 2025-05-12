# 游戏引擎架构设计文档

## 1. 目录结构

```
rotk/
├── core/                   # 核心引擎模块
│   ├── ecs/                # 实体组件系统
│   │   ├── world.py        # 世界管理
│   │   ├── entity.py       # 实体类
│   │   ├── component.py    # 组件基类
│   │   ├── system.py       # 系统基类
│   │   ├── query.py        # 查询构建器
│   │   └── scheduler.py    # 系统调度器
│   ├── events/             # 事件系统
│   │   ├── manager.py      # 事件管理器
│   │   ├── event.py        # 事件基类
│   │   └── history.py      # 事件历史
│   └── config/             # 配置系统
│       ├── manager.py      # 配置管理器
│       └── loader.py       # 配置加载器
...
```

## 2. 架构设计

### 2.1 核心架构
- 采用纯ECS架构，所有实体都是ID
- 事件驱动的系统间通信
- 基于查询的实体筛选
- 可配置的系统调度
- 统一的配置管理

### 2.2 设计原则
- 单一职责原则：每个系统只负责一个领域
- 依赖注入：通过构造函数注入依赖
- 接口隔离：系统间通过事件通信
- 开闭原则：通过组件扩展功能
- 配置驱动：关键参数通过配置管理

## 3. 核心接口设计

### 3.1 World 类

```python
class World:
    """世界管理器，负责实体、组件和系统的管理"""
    
    def __init__(self) -> None:
        """初始化世界管理器"""
        
    def create_entity(self) -> EntityId:
        """创建新实体
        Returns:
            EntityId: 新创建的实体ID
        """
        
    def destroy_entity(self, entity_id: EntityId) -> None:
        """销毁实体
        Args:
            entity_id: 要销毁的实体ID
        """
        
    def add_component(self, entity_id: EntityId, component: Component) -> None:
        """添加组件
        Args:
            entity_id: 目标实体ID
            component: 要添加的组件
        """
        
    def remove_component(self, entity_id: EntityId, component_type: Type[Component]) -> None:
        """移除组件
        Args:
            entity_id: 目标实体ID
            component_type: 要移除的组件类型
        """
        
    def get_component(self, entity_id: EntityId, component_type: Type[Component]) -> Optional[Component]:
        """获取组件
        Args:
            entity_id: 目标实体ID
            component_type: 组件类型
        Returns:
            Optional[Component]: 组件实例，如果不存在则返回None
        """
        
    def query(self) -> QueryBuilder:
        """创建查询构建器
        Returns:
            QueryBuilder: 查询构建器实例
        """
        
    def add_system(self, system: System, group: str = "default", priority: int = 0) -> None:
        """添加系统
        Args:
            system: 系统实例
            group: 系统组名
            priority: 优先级
        """
        
    def remove_system(self, system: System) -> None:
        """移除系统
        Args:
            system: 要移除的系统
        """
        
    def update(self, delta_time: float) -> None:
        """更新世界状态
        Args:
            delta_time: 时间增量
        """
```

### 3.2 QueryBuilder 类

```python
class QueryBuilder:
    """查询构建器，用于构建实体查询"""
    
    def with_component(self, component_type: Type[Component]) -> 'QueryBuilder':
        """添加组件条件
        Args:
            component_type: 组件类型
        Returns:
            QueryBuilder: 查询构建器实例
        """
        
    def without_component(self, component_type: Type[Component]) -> 'QueryBuilder':
        """添加排除组件条件
        Args:
            component_type: 组件类型
        Returns:
            QueryBuilder: 查询构建器实例
        """
        
    def with_tag(self, tag: str) -> 'QueryBuilder':
        """添加标签条件
        Args:
            tag: 标签名
        Returns:
            QueryBuilder: 查询构建器实例
        """
        
    def execute(self) -> List[EntityId]:
        """执行查询
        Returns:
            List[EntityId]: 符合条件的实体ID列表
        """
```

### 3.3 SystemScheduler 类

```python
class SystemScheduler:
    """系统调度器，负责系统的执行顺序管理"""
    
    def __init__(self) -> None:
        """初始化系统调度器"""
        
    def add_system(self, system: System, group: str = "default", priority: int = 0) -> None:
        """添加系统
        Args:
            system: 系统实例
            group: 系统组名
            priority: 优先级
        """
        
    def remove_system(self, system: System) -> None:
        """移除系统
        Args:
            system: 要移除的系统
        """
        
    def update(self, delta_time: float) -> None:
        """更新所有系统
        Args:
            delta_time: 时间增量
        """
        
    def get_systems_in_group(self, group: str) -> List[System]:
        """获取指定组的所有系统
        Args:
            group: 系统组名
        Returns:
            List[System]: 系统列表
        """
```

### 3.4 EventManager 类

```python
class EventManager:
    """事件管理器，负责事件的发布和订阅"""
    
    def __init__(self) -> None:
        """初始化事件管理器"""
        
    def subscribe(self, topic: str, callback: Callable[[Event], None], priority: int = 0) -> None:
        """订阅事件
        Args:
            topic: 事件主题
            callback: 回调函数
            priority: 优先级
        """
        
    def unsubscribe(self, topic: str, callback: Callable[[Event], None]) -> None:
        """取消订阅
        Args:
            topic: 事件主题
            callback: 回调函数
        """
        
    def publish(self, event: Event) -> None:
        """发布事件
        Args:
            event: 事件实例
        """
        
    def get_history(self, topic: str, limit: int = 10) -> List[Event]:
        """获取事件历史
        Args:
            topic: 事件主题
            limit: 历史记录数量限制
        Returns:
            List[Event]: 事件历史列表
        """
```

### 3.5 ConfigManager 类

```python
class ConfigManager:
    """配置管理器，负责配置的加载和管理"""
    
    def __init__(self) -> None:
        """初始化配置管理器"""
        
    def load_config(self, config_path: str) -> None:
        """加载配置文件
        Args:
            config_path: 配置文件路径
        """
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        Args:
            key: 配置键
            default: 默认值
        Returns:
            Any: 配置值
        """
        
    def set(self, key: str, value: Any) -> None:
        """设置配置值
        Args:
            key: 配置键
            value: 配置值
        """
```

## 4. 类型定义

```python
from typing import Type, List, Optional, Callable, Any, Dict, Set
from dataclasses import dataclass
from enum import Enum

EntityId = int

@dataclass
class Event:
    """事件基类"""
    topic: str
    data: Dict[str, Any]

class Component:
    """组件基类"""
    pass

class System:
    """系统基类"""
    def update(self, delta_time: float) -> None:
        pass
```

## 5. 使用示例

```python
# 创建世界
world = World()

# 创建实体
entity_id = world.create_entity()

# 添加组件
world.add_component(entity_id, UnitComponent())

# 创建查询
entities = world.query().with_component(UnitComponent).execute()

# 添加系统
world.add_system(CombatSystem(), group="combat", priority=1)

# 订阅事件
event_manager.subscribe("COMBAT_HIT", handle_combat_hit)

# 加载配置
config_manager.load_config("game_config.json")
```