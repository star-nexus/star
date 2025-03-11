# UI系统

## 概述
本目录包含游戏的UI框架，实现了一个层次化的UI系统，包含各种UI元素。

## 主要组件
- `UIElement`: 所有UI元素的基类
- `TextLabel`: 文本显示组件
- `Button`: 具有悬停/按下状态的交互式按钮
- `Panel`: 可以容纳其他UI元素的容器
- `UIManager`: 管理所有UI元素和渲染

## 架构
UI系统使用父子关系模型，元素可以嵌套。`UIManager`作为中央协调器，处理元素创建、字体管理和事件传播。

## 使用示例
```python
# 通过UI管理器创建一个UI元素
ui_manager.create_button(
    "panel_name",
    x=100, y=100,
    width=200, height=50,
    text="点击我",
    on_click=my_callback_function
)
```

## 最佳实践
- 使用命名面板组织UI元素
- 在游戏事件之前处理UI事件
- 切换场景时确保UI元素被正确清理
