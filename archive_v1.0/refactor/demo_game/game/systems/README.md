# 系统设计文档

## ECS系统设计原则
在ECS (Entity-Component-System) 架构中，系统应当：
1. 只关注行为逻辑，不存储状态
2. 每个系统只处理特定的组件组合
3. 系统之间应该尽量解耦
4. 系统不应该直接引用世界状态，而应该通过传入的world参数操作

## 系统分类

### 核心游戏逻辑系统
- `MovementSystem`: 处理实体移动
- `PlayerControlSystem`: 处理玩家输入控制
- `EnemyAISystem`: 处理敌人AI行为
- `CollisionSystem`: 检测和处理碰撞

### 地图系统
- `MapGenerationSystem`: 地图生成
- `MapRenderSystem`: 地图渲染
- `TerrainEffectSystem`: 地形效果处理

### 渲染系统
- `RenderSystem`: 实体渲染
- `GlowSystem`: 发光效果处理

## 当前系统设计问题

### 需要改进的问题
1. **系统状态存储**:
   - `GlowSystem`直接持有world引用并在初始化时订阅事件，违反了ECS原则
   - 系统应该是无状态的，只依赖传入的world参数

2. **职责混合**:
   - `TerrainEffectSystem`同时处理地形效果和碰撞检测
   - `CollisionSystem`同时处理碰撞检测和反弹逻辑

3. **命名一致性**:
   - 确保系统命名反映其实际功能

## 系统间通信方式
- 使用事件系统进行系统间松耦合通信
- 不同系统可以订阅和发布事件
- 避免系统之间的直接依赖
