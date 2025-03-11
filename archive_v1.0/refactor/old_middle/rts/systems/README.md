# 系统模块 (Systems)

系统模块包含RTS游戏的核心逻辑，基于实体-组件-系统(ECS)架构，负责处理游戏中的各种功能和机制。

## 模块概述

系统负责处理和更新拥有特定组件的实体，实现游戏的核心逻辑。每个系统专注于一个特定的游戏功能，如资源管理、战斗、单位控制等。

## 主要系统

### 阵营系统 (FactionSystem)

管理游戏中的所有阵营，处理阵营间的交互：
- 初始化和维护各个阵营
- 跟踪阵营的生存状态
- 提供阵营实体和单位的访问接口

### 资源系统 (ResourceSystem)

管理资源的收集、消耗和分配：
- 处理资源产出和消耗
- 管理资源节点
- 处理资源转移和存储

### 单位系统 (UnitSystem)

处理单位的移动、寻路和行动：
- 更新单位位置和状态
- 计算地形对单位的影响
- 管理单位的攻击冷却

### 建筑系统 (BuildingSystem)

管理建筑的建造、生产和功能：
- 处理建筑建造进度
- 管理建筑的生产队列
- 更新建筑的资源生成

### 战斗系统 (CombatSystem)

处理单位间的战斗、伤害计算和战斗结果：
- 检测攻击范围和目标
- 计算伤害和防御
- 处理单位死亡

### 单位控制系统 (UnitControlSystem)

处理单位的选择、命令和移动逻辑：
- 管理单位选择和编组
- 处理移动和攻击命令
- 实现单位的队形移动

### 胜利条件系统 (VictoryConditionSystem)

检查游戏胜利条件和结束状态：
- 支持多种胜利条件
- 检测游戏结束条件
- 发送游戏结束事件

## 胜利条件

游戏支持多种胜利条件：

1. **消灭敌人 (EliminationVictoryCondition)**：
   - 消灭所有敌方单位和建筑

2. **资源胜利 (ResourceVictoryCondition)**：
   - 达到特定资源数量（如10000金币）

3. **主基地胜利 (MainBaseVictoryCondition)**：
   - 摧毁敌方主基地或保护自己的主基地

## 使用示例

```python
# 初始化系统
faction_system = FactionSystem()
resource_system = ResourceSystem()
unit_system = UnitSystem()

# 注册系统到游戏世界
world.register_system(faction_system)
world.register_system(resource_system)
world.register_system(unit_system)

# 配置胜利条件
victory_system = VictoryConditionSystem()
victory_system.add_victory_condition(EliminationVictoryCondition())
victory_system.add_victory_condition(ResourceVictoryCondition(10000))
world.register_system(victory_system)
```

## 系统更新顺序

系统的更新顺序对游戏逻辑非常重要：

1. 输入处理（玩家命令）
2. 单位控制系统（处理命令）
3. 单位系统（移动和状态）
4. 战斗系统（攻击和伤害）
5. 建筑系统（建造和生产）
6. 资源系统（收集和消耗）
7. 胜利条件系统（检查游戏状态）
