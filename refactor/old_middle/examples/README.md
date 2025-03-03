# 示例游戏

这个目录包含使用游戏框架开发的示例游戏和组件，展示了框架的使用方法和最佳实践。

## 组件

- **components.py**: 示例游戏中使用的组件
- **systems.py**: 示例游戏中使用的系统
- **simple_game.py**: 一个完整的简单游戏示例

## 示例场景

- **scenes/main_menu_scene.py**: 主菜单场景实现
- **scenes/game_over_scene.py**: 游戏结束场景实现
- **scenes/game_scene/**: 游戏主场景模块
  - **game_scene.py**: 游戏主场景实现
  - **entity_factory.py**: 游戏实体的工厂类
  - **game_scene_logic.py**: 游戏逻辑实现
  - **game_scene_ui.py**: 游戏UI实现
  - **pause_menu.py**: 暂停菜单实现

## 运行示例

直接运行simple_game.py来启动示例游戏：

```bash
python -m examples.simple_game
```

## 学习资源

这些示例提供了框架的实际使用案例，展示了：

- ECS架构的最佳实践
- 场景管理和切换
- UI创建和交互
- 游戏状态管理
- 输入处理和响应
- 资源加载和使用

通过学习和修改这些示例，您可以快速掌握框架的使用方法。
