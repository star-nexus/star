# 核心引擎模块

该模块包含游戏框架的核心组件，负责游戏生命周期管理。

## 组件

- **game_engine.py**: 游戏引擎主类，负责游戏初始化、主循环、资源管理和游戏状态控制

## 游戏引擎功能

GameEngine类提供：
- 游戏初始化和配置
- 主循环管理
- 帧率控制
- 全局管理器集成（输入、音频、资源、UI、场景）
- ECS世界管理

## 使用示例

```python
from framework.core.game_engine import GameEngine

# 创建游戏引擎实例
game = GameEngine(width=800, height=600, title="我的游戏", fps=60)

# 注册场景
game.scene_manager.register_scene("menu", MenuScene)
game.scene_manager.register_scene("game", GameScene)

# 切换到初始场景
game.scene_manager.change_scene("menu")

# 启动游戏
game.start()
```
