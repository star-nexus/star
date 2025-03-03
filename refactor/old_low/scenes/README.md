# 游戏场景

## 概述
本目录包含控制游戏不同状态的场景类。

## 主要场景
- `MainMenuScene`: 带有游戏选项的初始菜单画面
- `GameScene`: 具有不同游戏方面控制器的主游戏场景
- `VictoryScene`: 玩家获胜时显示的场景

## 场景架构
每个场景继承自`BaseScene`类，并实现标准生命周期方法：
- `initialize()`: 设置场景资源
- `update(delta_time)`: 每帧更新场景逻辑
- `render(surface)`: 绘制场景
- `on_enter()`和`on_exit()`: 处理场景转换

## UI实现
场景支持：
- 带有`UIManager`集成的现代UI系统
- 向后兼容的传统直接渲染方法

## 游戏数据
场景通过游戏状态管理器共享游戏数据：
- `get_game_data()`: 获取共享游戏信息
- `update_game_data(key, value)`: 更新共享信息

## 实现模式
- 场景特定事件处理
- 滚动场景的相机管理
- 实体生命周期管理
