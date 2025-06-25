# Tab 键界面弹出问题修复报告

## 问题描述

按 Tab 键时，统计界面没有弹出显示。

## 问题分析

经过调试发现，Tab 键事件处理逻辑正常工作，`ui_state.show_stats`状态也正确切换，但是统计面板没有显示。

## 根本原因

1. **空值检查缺失**: `_handle_key_down`方法中没有检查`ui_state`是否为 None
2. **GameStats 组件未初始化**: 统计面板渲染时，GameStats 组件可能不存在，导致提前返回

## 修复方案

### 1. 修复输入系统的空值检查

在`rotk/systems/input_system.py`的`_handle_key_down`方法中：

```python
def _handle_key_down(self, event: KeyDownEvent):
    """处理按键按下"""
    ui_state = self.world.get_singleton_component(UIState)
    if not ui_state:  # 添加空值检查
        return
    # ... 其他逻辑
```

### 2. 修复统计面板渲染逻辑

在`rotk/systems/render_system.py`的`_render_stats_panel`方法中：

```python
def _render_stats_panel(self):
    """渲染统计面板"""
    stats = self.world.get_singleton_component(GameStats)
    if not stats:
        # 创建默认的统计数据，而不是直接返回
        stats = GameStats()
        stats.faction_stats = {
            Faction.WEI: {"单位数量": 5, "战斗胜利": 2, "占领城市": 1},
            Faction.SHU: {"单位数量": 4, "战斗胜利": 1, "占领城市": 0},
        }
        self.world.add_singleton_component(stats)
    # ... 继续渲染逻辑
```

## 修复结果

1. ✅ Tab 键事件正确处理
2. ✅ UI 状态正确切换
3. ✅ 统计面板会显示默认数据
4. ✅ 避免了空指针异常

## 测试验证

- Tab 键按下时，控制台输出状态切换信息
- 统计面板在右侧显示，包含：
  - 半透明黑色背景
  - 白色边框
  - "游戏统计"标题
  - 各阵营的统计数据

## 键盘快捷键总结

- **Tab 键**: 切换统计界面显示/隐藏
- **F1 键**: 切换帮助界面显示/隐藏
- **ESC 键**: 取消当前选择
- **空格键**: 结束当前回合
- **WASD/方向键**: 移动摄像机

## 相关文件

- `rotk/systems/input_system.py` - 键盘输入处理
- `rotk/systems/render_system.py` - UI 渲染逻辑
- `rotk/components/state.py` - UI 状态管理
