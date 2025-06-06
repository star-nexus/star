# Framework Examples

这个目录包含了使用 framework 的各种示例，帮助开发者快速了解和使用 ECS 架构。

## 示例列表

1. **basic_ecs** - ECS 基础用法示例

   - 展示组件、实体、系统的基本概念
   - 包含状态显示、经验系统、战斗模拟
   - 适合初学者理解 ECS 架构

2. **movement_demo** - 移动系统示例

   - 2D 空间中的移动和碰撞检测
   - AI 自动寻路和边界反弹
   - 展示物理系统的实现

3. **event_demo** - 事件系统示例

   - 事件驱动的系统间通信
   - 发布-订阅模式的使用
   - 复杂的事件链反应

4. **complete_game** - 完整游戏示例
   - 三国策略小游戏
   - 使用完整的游戏引擎功能
   - 图形界面和用户交互
   - **需要 pygame 库**

## 快速运行

### 方法 1: 使用运行脚本（推荐）

```bash
cd examples
python run_examples.py
```

### 方法 2: 直接运行示例

```bash
cd examples
python basic_ecs/main.py
python movement_demo/main.py
python event_demo/main.py
python complete_game/main.py  # 需要先安装pygame
```

## 依赖要求

- **Python 3.7+**
- **基础示例**: 无额外依赖
- **完整游戏示例**: 需要 pygame
  ```bash
  pip install pygame
  ```

## 学习路径

建议按以下顺序学习示例：

1. **basic_ecs** - 理解 ECS 基础概念
2. **movement_demo** - 学习系统协作和物理模拟
3. **event_demo** - 掌握事件驱动编程
4. **complete_game** - 综合应用和实际游戏开发

## 示例特点

每个示例都包含：

- 📁 独立的目录结构
- 📄 详细的 README 说明
- 💻 可直接运行的代码
- 📝 丰富的注释和文档
- 🎯 明确的学习目标

## 扩展建议

基于这些示例，你可以进一步开发：

- 更复杂的 AI 行为
- 网络多人游戏
- 3D 图形渲染
- 音效系统
- 存档系统
- 关卡编辑器

每个示例都是独立的学习模块，可以作为你自己项目的起点。
