# 游戏框架

一个模块化、高性能的游戏框架，结合实体-组件-系统(ECS)架构和强大的全局管理能力。基于Pygame实现。

## 核心理念

本框架旨在提供：
- **解耦游戏逻辑**：使用ECS分离数据和行为
- **全局管理**：对游戏状态、场景和资源进行集中控制
- **模块化设计**：可重用的系统和组件
- **高性能**：为现代游戏开发优化
- **易用性**：清晰的API，最小化样板代码
- **场景管理**：支持多个场景间的切换和管理

## 架构概览

```
+-----------------------------------+
|             游戏引擎              |
+-----------------------------------+
|                                   |
|  +---------+      +------------+  |
|  |  世界   |<---->|  游戏管理器 |  |
|  +---------+      +------------+  |
|      |                 |          |
| +----------+    +--------------+  |
| |   实体   |    |   全局系统   |  |
| +----------+    +--------------+  |
|      |                 |          |
| +----------+    +--------------+  |
| |   组件   |    |   管理器     |  |
| +----------+    +--------------+  |
|      |                 |          |
| +----------+    +--------------+  |
| |   系统   |    |      UI      |  |
| +----------+    +--------------+  |
|                                   |
+-----------------------------------+
```

### 关键组件

1. **世界(World)**：ECS容器，管理实体、组件和系统
2. **游戏引擎(GameEngine)**：控制游戏生命周期的全局单例
3. **实体(Entities)**：以唯一ID表示的游戏对象
4. **组件(Components)**：附加到实体上的纯数据容器
5. **系统(Systems)**：操作组件的逻辑处理器
6. **全局系统(Global Systems)**：在ECS上下文之外运行的系统
7. **管理器(Managers)**：模块化服务，如输入、音频、网络
8. **UI(UI)**：用户界面元素
9. **场景(Scene)**：游戏不同状态的封装，如主菜单、游戏、结束界面

## 模块结构

- **[核心(Core)](./framework/core/README.md)**：基础类和接口
  - `framework/core/game_engine.py` - 游戏主循环与管理

- **[ECS](./framework/ecs/README.md)**：实体-组件-系统实现
  - `framework/ecs/world.py` - ECS世界管理
  - `framework/ecs/entity.py` - 实体实现
  - `framework/ecs/component.py` - 组件基类
  - `framework/ecs/system.py` - 系统基类

- **[管理器(Managers)](./framework/managers/README.md)**：全局管理器
  - `framework/managers/input_manager.py` - 输入管理
  - `framework/managers/audio_manager.py` - 音频管理
  - `framework/managers/resource_manager.py` - 资源管理

- **[UI](./framework/ui/README.md)**：用户界面
  - `framework/ui/ui_element.py` - UI元素基类
  - `framework/ui/ui_button.py` - 按钮实现
  - `framework/ui/ui_text.py` - 文本实现
  - `framework/ui/ui_manager.py` - UI管理器

- **[场景(Scene)](./framework/scene/README.md)**：场景系统
  - `framework/scene/scene.py` - 场景基类
  - `framework/scene/scene_manager.py` - 场景管理器

- **[示例(Examples)](./examples/README.md)**：参考实现
  - `examples/components.py` - 示例组件
  - `examples/systems.py` - 示例系统
  - `examples/simple_game.py` - 简单游戏示例
  - `examples/scenes/` - 场景实现
    - `main_menu_scene.py` - 主菜单场景
    - `game_over_scene.py` - 游戏结束场景
    - `game_scene/` - 游戏场景模块
      - `game_scene.py` - 游戏主场景
      - `entity_factory.py` - 实体创建工厂
      - `game_scene_logic.py` - 游戏逻辑处理
      - `game_scene_ui.py` - 游戏UI管理
      - `pause_menu.py` - 暂停菜单实现

## 安装

1. 首先确保安装了Python和Pygame:

```bash
pip install pygame
```

2. 然后克隆并使用这个框架:

```bash
git clone https://github.com/yourusername/game_framework.git
cd game_framework
python -m examples.simple_game
```

## 快速入门

### 创建游戏

```python
import pygame
from framework.core.game_engine import GameEngine
from my_scenes import MyMenuScene, MyGameScene

def main():
    # 初始化游戏引擎
    game = GameEngine(width=800, height=600, title="我的游戏")
    
    # 注册场景
    game.scene_manager.register_scene("menu", MyMenuScene)
    game.scene_manager.register_scene("game", MyGameScene)
    
    # 切换到初始场景
    game.scene_manager.change_scene("menu")
    
    # 启动游戏
    game.start()

if __name__ == "__main__":
    main()
```

### 创建场景

```python
from framework.scene.scene import Scene
from framework.ui.ui_text import UIText
from framework.ui.ui_button import UIButton

class MyMenuScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        
    def load(self):
        # 创建UI元素
        font = pygame.font.SysFont("arial", 32)
        
        # 添加标题
        self.add_ui_element(
            UIText(self.game.width//2, 100, "我的游戏", font, (255, 255, 255), centered=True)
        )
        
        # 添加开始按钮
        start_button = self.add_ui_element(
            UIButton(self.game.width//2-75, 200, 150, 40, "开始游戏")
        )
        start_button.set_font(font)
        start_button.callback = self.start_game
        
    def start_game(self):
        # 切换到游戏场景
        self.game.scene_manager.change_scene("game")
```

### 创建组件

```python
from framework.ecs.component import Component

class MyComponent(Component):
    def __init__(self, value):
        super().__init__()
        self.value = value
```

### 创建系统

```python
from framework.ecs.system import System
from my_components import PositionComponent, VelocityComponent

class MovementSystem(System):
    def __init__(self):
        super().__init__([PositionComponent, VelocityComponent])
        
    def update(self, delta_time):
        for entity in self.entities:
            pos = entity.get_component(PositionComponent)
            vel = entity.get_component(VelocityComponent)
            
            pos.x += vel.x * delta_time
            pos.y += vel.y * delta_time
```

## 示例游戏说明

框架包含一个完整的示例游戏实现，展示了框架的各种功能：

- **主菜单场景**: 包含开始游戏和退出按钮
- **游戏场景**: 玩家控制角色，躲避敌人，收集得分
  - 玩家移动：使用方向键控制
  - 敌人AI：追踪玩家
  - 碰撞系统：处理玩家、敌人和障碍物之间的交互
  - 暂停菜单：按ESC键暂停游戏
- **游戏结束场景**: 显示胜利/失败状态和最终得分

运行示例游戏:

```bash
python -m examples.simple_game
```

## 文档结构

- [框架核心文档](./framework/README.md) - 框架整体介绍
  - [核心引擎模块](./framework/core/README.md) - 游戏引擎和核心组件
  - [ECS模块](./framework/ecs/README.md) - 实体-组件-系统架构
  - [管理器模块](./framework/managers/README.md) - 资源、输入和音频管理
  - [场景模块](./framework/scene/README.md) - 场景系统
  - [UI模块](./framework/ui/README.md) - 用户界面系统
- [示例游戏文档](./examples/README.md) - 示例游戏和使用教程

## 文件结构参考

```
game_framwork/
├── framework/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── game_engine.py
│   ├── ecs/
│   │   ├── __init__.py
│   │   ├── component.py
│   │   ├── entity.py
│   │   ├── system.py
│   │   └── world.py
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── audio_manager.py
│   │   ├── input_manager.py
│   │   └── resource_manager.py
│   ├── scene/
│   │   ├── __init__.py
│   │   ├── scene.py
│   │   └── scene_manager.py
│   └── ui/
│       ├── __init__.py
│       ├── ui_button.py
│       ├── ui_element.py
│       ├── ui_manager.py
│       └── ui_text.py
└── examples/
    ├── __init__.py
    ├── assets/
    │   ├── player.png
    │   ├── enemy.png
    │   └── obstacle.png
    ├── components.py
    ├── systems.py
    ├── simple_game.py
    └── scenes/
        ├── __init__.py
        ├── main_menu_scene.py
        ├── game_over_scene.py
        └── game_scene/
            ├── __init__.py
            ├── game_scene.py
            ├── entity_factory.py
            ├── game_scene_logic.py
            ├── game_scene_ui.py
            └── pause_menu.py
