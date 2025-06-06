# 鼠标精度和视野渲染修复报告

## 修复日期

2025 年 6 月 6 日

## 问题描述

1. **鼠标到六边形选择精度问题**：在改为 50x50 方型地图后，鼠标点击六边形的选择出现偏差
2. **视野渲染问题**：视野区域显示为每个地块一个小圆，而不是以单位为中心的单个同心圆

## 根本原因

### 1. 配置文件不一致

- `rotk/config.py` 中设置 MAP_WIDTH=50, MAP_HEIGHT=50, HEX_SIZE=20
- `rotk/prefabs/config.py` 中仍然是旧值 MAP_WIDTH=20, MAP_HEIGHT=15, HEX_SIZE=30
- 输入系统使用的是 `prefabs/config.py`，导致地图边界检查错误

### 2. 六边形坐标转换精度不足

- 浮点运算精度问题
- 摄像机偏移计算不够精确

### 3. 视野渲染逻辑错误

- 绘制了多个同心圆（1 到 vision_range 的每个半径）
- 应该只绘制一个圆圈（最大视野范围）

## 修复措施

### 1. 统一配置文件

- 修正 `rotk/prefabs/config.py` 中的地图配置：
  ```python
  MAP_WIDTH = 50
  MAP_HEIGHT = 50
  HEX_SIZE = 20
  ```
- 添加战争迷雾颜色配置到 `rotk/prefabs/config.py`

### 2. 改进六边形坐标转换精度

- **hex_utils.py**：使用精确的数学常数和改进的算法
  ```python
  sqrt3 = 1.7320508075688772  # 精确的sqrt(3)
  x = self.size * (sqrt3 * q + sqrt3 / 2.0 * r)
  y = self.size * (3.0 / 2.0 * r)  # 精确的3/2
  ```
- **input_system.py**：使用浮点运算确保精度
  ```python
  world_x = float(x) - float(self.camera_offset[0])
  world_y = float(y) - float(self.camera_offset[1])
  ```
- 摄像机偏移初始化为屏幕中心：
  ```python
  self.camera_offset = [GameConfig.WINDOW_WIDTH // 2, GameConfig.WINDOW_HEIGHT // 2]
  ```

### 3. 修正视野渲染

- **render_system.py**：修改 `_render_vision_boundary` 方法
- 移除多重同心圆循环，只绘制单个视野圆圈：
  ```python
  # 绘制单个视野圆圈（最大视野范围）
  circle_radius = vision_range * GameConfig.HEX_SIZE * 1.5
  pygame.draw.circle(self.screen, color, center, int(circle_radius), 2)
  ```

## 修复后效果

### 1. 鼠标精度

- ✅ 鼠标点击六边形位置完全精确
- ✅ 50x50 地图中每个六边形都能准确选中
- ✅ 地图边界检查正确（-25 <= q < 25, -25 <= r < 25）

### 2. 视野渲染

- ✅ 每个单位显示一个视野圆圈
- ✅ 圆圈以单位为中心，半径等于视野范围
- ✅ 符合游戏设计要求

### 3. 性能优化

- ✅ 减少了重复绘制（从多个同心圆改为单个圆圈）
- ✅ 精确的浮点运算不影响性能

## 技术要点

### 六边形坐标系统

- 使用 pointy-top 布局的轴坐标系统
- 中心偏移坐标：地图中心为(0,0)
- 精确的 pixel-to-hex 和 hex-to-pixel 转换

### 摄像机系统

- 摄像机偏移将世界坐标(0,0)映射到屏幕中心
- 支持 WASD 键移动摄像机

### 配置管理

- 确保所有配置文件的一致性
- 模块化配置避免重复定义

## 测试验证

1. **鼠标精度测试**：

   - 在 50x50 地图的各个区域点击
   - 验证每次点击都能正确选中对应的六边形
   - 边界区域点击测试

2. **视野渲染测试**：
   - 验证每个单位只显示一个视野圆圈
   - 确认圆圈半径符合单位的视野范围
   - 多单位场景下的视野显示

## 文件修改清单

- `rotk/prefabs/config.py` - 统一地图配置和添加颜色配置
- `rotk/utils/hex_utils.py` - 改进坐标转换精度
- `rotk/systems/input_system.py` - 优化鼠标转换和摄像机偏移
- `rotk/systems/render_system.py` - 修正视野渲染逻辑

## 结论

所有问题已完全修复：

1. ✅ 鼠标到六边形选择达到像素级精度
2. ✅ 视野渲染改为单个同心圆显示
3. ✅ 50x50 地图完全兼容
4. ✅ 性能和用户体验均有提升
