# 六边形方向切换功能

## 概述

系统现在支持两种六边形方向：

- **Pointy Top (尖顶向上)**: 传统的六边形布局，尖顶朝上
- **Flat Top (平顶向上)**: 旋转 90 度的六边形布局，平顶朝上

## 配置

在 `rotk_env/prefabs/config.py` 中设置默认的六边形方向：

```python
class GameConfig:
    # 地图配置
    HEX_ORIENTATION = HexOrientation.POINTY_TOP  # 或 HexOrientation.FLAT_TOP
```

## 运行时切换

在游戏运行时，可以使用以下方式切换六边形方向：

### 键盘快捷键

- 按 **H** 键切换六边形方向

### 编程方式

```python
# 通过地图渲染系统切换
map_render_system.toggle_hex_orientation()

# 或者设置特定方向
map_render_system.set_hex_orientation(HexOrientation.FLAT_TOP)
```

## 技术实现

### 数学转换

系统使用不同的数学公式来处理两种六边形方向：

**Pointy Top (尖顶向上)**:

```
x = size * (√3 * q + √3/2 * r)
y = size * (3/2 * r)
```

**Flat Top (平顶向上)**:

```
x = size * (3/2 * q)
y = size * (√3/2 * q + √3 * r)
```

### 组件更新

切换六边形方向时，系统会：

1. 更新所有使用 `HexConverter` 的系统
2. 清除地形贴图缓存
3. 重新计算六边形顶点坐标

## 影响的系统

以下系统会自动适应六边形方向的变化：

- 地图渲染系统 (`MapRenderSystem`)
- 单位渲染系统 (`UnitRenderSystem`)
- 输入处理系统 (`InputHandlingSystem`)
- 战斗系统 (`CombatSystem`)
- 小地图系统 (`MinimapSystem`)
- 效果渲染系统 (`EffectRenderSystem`)
- 动画系统 (`AnimationSystem`)

## 注意事项

1. 六边形方向的切换是即时生效的
2. 地形贴图缓存会被清除以适应新的六边形形状
3. 所有坐标转换都会使用新的数学公式
4. 视觉效果和游戏逻辑都会保持一致
