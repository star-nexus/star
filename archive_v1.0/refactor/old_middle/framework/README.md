# 游戏框架核心

这个目录包含了游戏框架的所有核心模块和组件。

## 目录结构

- [**core/**](./core/): 框架的核心引擎组件
- [**ecs/**](./ecs/): 实体-组件-系统架构实现
- [**managers/**](./managers/): 各类资源和功能管理器
- [**scene/**](./scene/): 场景管理系统
- [**ui/**](./ui/): 用户界面组件和管理

## 使用方法

通常，您需要从core模块导入GameEngine来启动您的游戏：

```python
from framework.core.game_engine import GameEngine

game = GameEngine(width=800, height=600, title="我的游戏")
# 配置游戏并启动
game.start()
```

查看各子目录中的README以获取更多详细信息。
