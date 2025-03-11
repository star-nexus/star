# 用户界面模块 (UI)

用户界面模块负责RTS游戏中所有可视化交互元素，提供游戏状态反馈和用户输入接口。

## 模块概述

UI系统为玩家提供游戏信息和交互界面，包括资源显示、小地图、单位信息面板和游戏流程界面。所有UI组件都继承自基础的UIElement类，保持一致的接口和行为。

## 主要组件

### 资源显示面板 (ResourceDisplay)

显示玩家的资源状态：
- 展示四种基本资源：金币、武器、食物和辎重
- 显示当前资源数量和最大存储量
- 使用颜色编码区分不同资源类型
- 支持动态更新资源数据

### 小地图 (Minimap)

显示整个游戏地图的缩略图：
- 显示地形和单位位置
- 用方框标示当前视口区域
- 支持点击小地图导航到相应位置
- 动态更新视口位置

### 实体信息面板 (EntityInfoPanel)

显示选中单位或建筑的详细信息：
- 展示实体的基本属性（名称、类型、阵营）
- 显示生命值、攻击力、防御力等战斗数据
- 显示建筑的建造进度和生产状态
- 展示资源生成速率和其他特殊属性

### 游戏流程UI (GameFlowUI)

管理游戏各状态的界面元素：
- 主菜单界面（游戏开始、退出选项）
- 胜利/失败屏幕
- 暂停菜单
- 状态转换处理

## 共享UI元素

### 文本元素 (TextElement)

显示文本信息：
- 支持自定义字体和颜色
- 可以居中或自定义位置
- 支持动态文本更新

### 按钮元素 (ButtonElement)

提供可点击的交互按钮：
- 支持悬停效果和点击回调
- 可自定义文本、颜色和大小
- 处理鼠标事件

## 使用示例

```python
# 创建资源显示面板
resource_display = ResourceDisplay(x=0, y=0, width=screen_width, height=60)
resource_display.set_font(normal_font)
scene.add_ui_element(resource_display)

# 创建小地图
minimap = Minimap(x=screen_width-210, y=screen_height-210, width=200, height=200)
minimap.set_map_data(map_data, map_renderer)
scene.add_ui_element(minimap)

# 创建实体信息面板
entity_info = EntityInfoPanel(x=10, y=screen_height-330, width=250, height=300)
entity_info.set_fonts(title_font, normal_font)
scene.add_ui_element(entity_info)

# 更新资源显示
resource_display.update_resources(faction_resource_component)

# 设置选中实体
entity_info.set_entity(selected_entity)

# 处理小地图点击
map_pos = minimap.handle_click(mouse_pos)
if map_pos:
    # 移动视图到点击位置
    pass
```

## 事件处理

UI组件使用以下事件处理机制：

1. **渲染**：所有UI组件都有render(surface)方法，按顺序渲染
2. **事件处理**：通过handle_event()方法处理鼠标和键盘事件
3. **更新**：使用update(dt)方法处理动画和状态变化
4. **回调**：通过回调函数处理用户交互
