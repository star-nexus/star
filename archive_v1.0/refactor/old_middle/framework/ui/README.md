# 用户界面模块

该模块提供用户界面组件和管理系统，用于创建交互式游戏界面。

## 组件

- **ui_element.py**: UI元素基类，所有UI组件的基础
- **ui_text.py**: 文本显示组件
- **ui_button.py**: 可交互按钮组件
- **ui_manager.py**: UI管理器，管理所有UI元素

## UI系统功能

- 组合式UI元素结构（父子关系）
- 事件处理和传播
- 可见性和启用状态控制
- 自动布局和渲染
- 交互式组件（按钮等）

## 使用示例

```python
# 在场景中使用UI
def load(self):
    # 创建文本
    title = self.add_ui_element(
        UIText(400, 100, "游戏标题", font, (255, 255, 255), centered=True)
    )
    
    # 创建按钮
    start_button = self.add_ui_element(
        UIButton(400, 200, 200, 50, "开始游戏")
    )
    start_button.set_font(font)
    start_button.callback = self.start_game
    
    exit_button = self.add_ui_element(
        UIButton(400, 300, 200, 50, "退出游戏")
    )
    exit_button.set_font(font)
    exit_button.callback = self.exit_game

# 按钮回调函数
def start_game(self):
    self.game.scene_manager.change_scene("game")

def exit_game(self):
    self.game.stop()
```
