# ROTK 系统修复报告

## 修复日期

2025 年 6 月 6 日

## 修复内容

### 1. Camera 组件单例化

**问题**: `InputHandlingSystem`中的`camera_offset`作为系统内部属性存储，不符合 ECS 模式。

**解决方案**:

- 在`components/state.py`中创建了`Camera`单例组件
- 提供了完整的摄像机管理功能：
  - `get_offset()`: 获取摄像机偏移
  - `set_offset(x, y)`: 设置摄像机偏移
  - `move(dx, dy)`: 移动摄像机
  - 包含缩放和移动速度属性

**修改文件**:

- `rotk/components/state.py` - 新增 Camera 组件
- `rotk/components/__init__.py` - 导出 Camera 组件
- `rotk/systems/input_system.py` - 使用 Camera 组件替代内部 camera_offset
- `rotk/systems/render_system.py` - 使用 Camera 组件获取摄像机偏移

### 2. 系统标准化

**问题**: 需要确保所有系统都遵循标准的 ECS 系统结构。

**解决方案**: 验证了所有系统都实现了标准的三个方法：

- `initialize(world)`: 初始化系统，设置必要的组件和状态
- `subscribe_events()`: 订阅系统需要处理的事件
- `update(delta_time)`: 每帧更新系统逻辑

**验证的系统**:

- ✅ `InputHandlingSystem` - 完整实现
- ✅ `RenderSystem` - 完整实现
- ✅ `CombatSystem` - 完整实现
- ✅ `MovementSystem` - 完整实现
- ✅ `TurnSystem` - 完整实现
- ✅ `MapSystem` - 完整实现
- ✅ `VisionSystem` - 完整实现
- ✅ `AISystem` - 完整实现

## 代码改进

### Camera 组件特性

```python
@dataclass
class Camera(SingletonComponent):
    offset_x: float = 0.0  # 摄像机X偏移
    offset_y: float = 0.0  # 摄像机Y偏移
    zoom: float = 1.0      # 缩放级别
    speed: float = 200.0   # 移动速度(像素/秒)
```

### InputHandlingSystem 改进

- 移除了硬编码的`camera_offset`属性
- 在`initialize()`中创建 Camera 单例组件
- 在`_handle_keyboard()`中使用 Camera 组件的`move()`方法
- 在坐标转换方法中使用 Camera 组件

### RenderSystem 改进

- 移除了`_get_input_system()`方法
- 直接从世界获取 Camera 单例组件
- 简化了摄像机偏移获取逻辑

## 测试结果

所有修改都通过了基本测试：

- Camera 组件创建和操作正常
- 系统可以正确创建和初始化
- 没有编译错误或运行时错误

## 符合 ECS 原则

这些修复确保了项目严格遵循 ECS 模式：

1. **实体(Entity)**: 游戏对象的 ID
2. **组件(Component)**: 数据容器，如 Camera 组件
3. **系统(System)**: 处理逻辑，操作特定组件的实体

Camera 数据现在作为组件存储，任何系统都可以访问和修改，符合 ECS 的数据驱动设计。
