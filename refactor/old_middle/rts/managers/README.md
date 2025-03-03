# 管理器模块 (Managers)

管理器模块为RTS游戏提供全局状态管理和协调不同系统间的通信，确保游戏功能协同工作。

## 模块概述

管理器采用单例模式设计，提供全局访问点，负责跨系统的状态管理、事件分发和阵营控制。每个管理器专注于特定领域的功能，共同构成游戏的核心架构。

## 主要管理器

### 游戏状态管理器 (GameStateManager)

负责管理游戏的整体状态：
- 定义游戏状态枚举（主菜单、加载中、游戏中、暂停、胜利、失败）
- 处理状态转换和相关回调
- 管理胜利和失败条件
- 提供游戏流程控制（开始、暂停、恢复、返回菜单）

### 事件管理器 (EventManager)

提供基于订阅的事件系统：
- 事件注册和分发
- 解耦游戏系统间的通信
- 支持多个监听器订阅同一事件
- 使系统间可以松散耦合

### 阵营管理器 (FactionManager)

管理游戏中的阵营定义和配置：
- 预定义阵营模板（红方、蓝方、绿方等）
- 设置阵营初始资源和属性
- 提供阵营特殊加成
- 区分玩家和AI阵营

## 事件类型

事件系统定义了多种事件类型：

### 游戏事件

- **GameStartEvent**: 游戏开始时触发
- **GameOverEvent**: 游戏结束时触发，包含胜利方信息
- **GamePauseEvent**: 游戏暂停时触发
- **GameResumeEvent**: 游戏恢复时触发
- **StateChangeEvent**: 状态改变时触发，包含前后状态信息

## 管理器间的协作

管理器之间通过以下方式协作：

1. **事件通信**: 通过EventManager发送和接收事件
2. **状态查询**: 系统可查询GameStateManager获取当前游戏状态
3. **阵营信息共享**: 系统通过FactionManager获取阵营配置

## 使用示例

```python
# 获取管理器单例
game_state_manager = GameStateManager.get_instance()
event_manager = EventManager.get_instance()
faction_manager = FactionManager()

# 注册事件监听
event_manager.add_listener(GameOverEvent, handle_game_over)

# 状态转换
game_state_manager.change_state(GameState.PLAYING)

# 获取阵营定义
faction_defs = faction_manager.get_faction_definitions(player_faction_id="red")

# 触发事件
event_manager.emit(GameOverEvent(winner_faction_id="red"))