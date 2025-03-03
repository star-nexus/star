# 组件模块 (Components)

组件模块是RTS游戏中实体-组件-系统(ECS)架构的核心部分，定义了游戏中各种实体的属性和行为特征。

## 模块概述

组件是纯数据容器，负责存储实体的各种属性，不包含复杂的游戏逻辑。系统通过读取和修改组件的数据来实现游戏功能。

## 主要组件

### 单位组件 (UnitComponent)

定义单位的基本属性和状态，包括：
- 单位类型（辎重、平原、山地、水面、远程、空中）
- 生命值、攻击力、防御力
- 移动和攻击状态
- 资源消耗

### 建筑组件 (BuildingComponent)

定义建筑物的属性和功能，包括：
- 建筑类型（主基地、补给点、战斗工事）
- 建造进度和状态
- 生产功能和资源生成

### 阵营组件 (FactionComponent)

标识实体所属的阵营，包括：
- 阵营ID和名称
- 阵营颜色
- 是否为玩家控制

### 资源组件 (ResourceComponent)

管理实体拥有的资源，包括：
- 四种基本资源：金币、武器、食物、辎重
- 资源生产和消耗率
- 最大资源存储量

### 位置组件 (PositionComponent)

管理实体在游戏世界中的位置：
- X坐标和Y坐标

### 移动组件 (MovementComponent)

定义实体的移动能力，包括：
- 在不同地形上的移动速度
- 路径和目标位置
- 特殊移动类型（穿越水面、山地，飞行）

### 攻击组件 (AttackComponent)

管理实体的攻击行为，包括：
- 攻击类型（近战、远程）
- 伤害值和攻击范围
- 攻击冷却和目标

### 防御组件 (DefenseComponent)

管理实体的防御属性，包括：
- 护甲值和生命值
- 对不同攻击类型的抗性
- 生命回复率

### 精灵组件 (SpriteComponent)

管理实体的视觉表示，包括：
- 图像资源名称
- 尺寸和可见性
- 渲染层级

### 资源节点组件 (ResourceNodeComponent)

表示地图上的资源点，包括：
- 节点类型（金矿、武器库、农场、补给仓库）
- 资源类型和数量
- 采集速率

## 使用示例

```python
# 创建一个单位实体
unit = world.create_entity()

# 添加位置组件
unit.add_component(PositionComponent(x=100, y=200))

# 添加单位组件
unit_comp = UnitComponent(UnitComponent.TYPE_PLAINS)
unit.add_component(unit_comp)

# 添加阵营组件
unit.add_component(FactionComponent("red"))
```

## 设计原则

1. **单一职责**：每个组件仅负责一种类型的数据
2. **纯数据**：组件主要存储数据，不实现复杂游戏逻辑
3. **可组合性**：通过不同组件的组合创建各种游戏实体
