# 场景管理模块

该模块提供场景管理功能，允许游戏在不同状态（如主菜单、游戏、暂停等）之间切换。

## 组件

- **scene.py**: 场景基类，所有游戏场景的基础
- **scene_manager.py**: 场景管理器，负责场景的加载、切换和管理

## 场景系统功能

- 定义不同游戏状态的场景
- 场景之间的平滑切换
- 场景栈，支持场景嵌套（如游戏中的暂停菜单）
- 场景生命周期管理（加载、卸载、更新、渲染）
- UI元素与场景集成

## 使用示例

```python
# 定义自定义场景
class MenuScene(Scene):
    def load(self):
        # 创建UI元素
        self.add_ui_element(UIText(400, 100, "主菜单", font, (255, 255, 255)))
        start_button = self.add_ui_element(UIButton(400, 200, 200, 50, "开始游戏"))
        start_button.callback = self.start_game
    
    def start_game(self):
        self.game.scene_manager.change_scene("game")

# 注册和使用场景
game.scene_manager.register_scene("menu", MenuScene)
game.scene_manager.register_scene("game", GameScene)
game.scene_manager.register_scene("game_over", GameOverScene)

# 切换到初始场景
game.scene_manager.change_scene("menu")

# 场景栈操作示例
game.scene_manager.push_scene("pause_menu")  # 压入暂停菜单
game.scene_manager.pop_scene()  # 返回上一个场景
```
