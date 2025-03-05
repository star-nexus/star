# 组件设计文档

## 游戏描述
{RoTK游戏}是一个以{结合感知的信息分析推理，优化决策方案来完成任务}为核心的{即时策略}游戏，玩家需要在复杂的局势中做出决策。游戏的目标是通过合理的策略击败对手并获取胜利。

考察玩家的推理能力和决策能力，让玩家在游戏中体验到不同环境下，因为约束条件不同，对任务分析处理方式的不同，以及对任务处理结果的不同。

游戏元素大概有，地图，阵营，兵种单位，建筑等。

## ECS组件设计原则
在ECS (Entity-Component-System) 架构中，组件应当：
1. 仅包含数据，不包含行为逻辑
2. 每个组件应该只负责一个明确的数据领域
3. 组件应该是可组合的，可以自由地附加到任何实体上

## 组件分类
### 基础组件

#### TransfromComponent

worldPos: 三维坐标

rotation: 朝向角度

#### CollisionComponent

collisionShape: 碰撞形状

collisionMask: 碰撞掩码

#### FactionComponent

faction: 所属阵营

controlType: 控制权类型（玩家/AI）

### 战略决策相关组件
#### VisionComponent

visibilityRange: 视野范围

detectedEntities: 当前可见的实体列表

fogOfWarState: 战争迷雾状态

#### StrategicAttributesComponent

strategicValue: 战略价值评分

threatLevel: 威胁等级评估

priorityTargets: 优先目标列表

### 单位类组件

#### AttackComponent

attackPower: 攻击力
attackRange: 攻击范围


#### DefenseComponent

defensePower: 防御力



#### MovementComponent

moveSpeed: 移动速度

pathfindingTarget: 当前路径目标

movementType: 移动类型（地面/飞行/水陆两栖）

#### UnitStateComponent

currentHealth: 当前生命值

energy: 体力值

statusEffects: 状态效果列表（中毒/眩晕等）

资源管理组件
ResourceStorageComponent

storageCapacity: 存储容量

storedResources: 各资源类型当前存储量

autoDistribution: 自动分配规则

ResourceCollectorComponent

collectionRate: 采集效率

collectionType: 可采集资源类型

currentCarrying: 当前携带量

建筑类组件
ProductionComponent

productionQueue: 生产队列

currentProgress: 当前生产进度

availableUnits: 可生产单位列表

DefenseComponent

turretSlots: 防御炮塔插槽

shieldCapacity: 护盾容量

autoRepairRate: 自动修复速率

环境交互组件
TerrainComponent

terrainType: 地形类型（平原/山地/河流）

movementModifier: 移动修正系数

defenseModifier: 防御修正系数

ResourceNodeComponent

resourceType: 资源类型

reserveAmount: 资源储量

regenerationRate: 资源再生速度

决策支持组件
DecisionContextComponent

availableOptions: 当前可用策略选项

decisionWeights: 各选项权重评估

lastDecisionTime: 上次决策时间戳

TaskComponent

currentTask: 当前任务类型

taskProgress: 任务进度

requiredResources: 任务所需资源

特殊效果组件
BuffComponent

activeBuffs: 生效的增益效果

buffExpiration: 效果过期时间

StealthComponent

stealthLevel: 隐身等级

detectionResistance: 反侦察能力

组合示例
士兵单位 = Identity + Position + Ownership + UnitCombat + UnitMovement + UnitState

资源矿场 = Identity + Position + Ownership + ResourceStorage + Production + Defense

战略要地 = Identity + Position + Terrain + StrategicAttributes

设计特点
数据驱动：所有决策参数都以数值形式存储，便于AI系统进行分析

灵活组合：通过增减组件快速创建新单位类型（如添加StealthComponent即成为侦察兵）

状态分离：将实时状态（UnitState）与基础属性（UnitCombat）分离，方便状态重置

决策支持：StrategicAttributes和DecisionContext为AI决策提供结构化数据

环境交互：通过Terrain和ResourceNode实现动态战场环境


## 命名规范
- 所有组件文件名应使用classname_component.py的格式 (e.g. position_component.py)
- 所有组件类名应使用PascalCase
- 文件名应与类名一致

## 组件设计评估
当前组件设计符合ECS原则：
- 所有组件只包含数据，没有方法逻辑
- 组件职责单一明确
- 使用了dataclass简化数据定义
