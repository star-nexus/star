# LLM Action Handler API 接口文档

## 概述

LLM Action Handler 是为 LLM 系统提供的统一动作执行接口，支持单位操作、观测查询和状态管理等功能。该系统提供了标准化的 API 接口，使 LLM 能够通过结构化的方式与游戏世界进行交互。

## 目录 (Table of Contents)

- [概述](#概述)
- [核心接口](#核心接口)
  - [主要方法](#主要方法)
- [动作分类](#动作分类)
  - [1. 单位动作 (Unit Actions)](#1-单位动作-unit-actions)
    - [move - 移动单位](#move---移动单位)
    - [attack - 攻击目标](#attack---攻击目标)
    - [defend - 设置防御](#defend---设置防御)
    - [scout - 侦察区域](#scout---侦察区域)
    - [retreat - 单位撤退](#retreat---单位撤退)
    - [fortify - 构建防御](#fortify---构建防御)
    - [patrol - 巡逻任务](#patrol---巡逻任务)
    - [end_turn - 结束回合](#end_turn---结束回合)
    - [select_unit - 选择单位](#select_unit---选择单位)
    - [formation - 设置阵型](#formation---设置阵型)
  - [2. 观测动作 (Observation Actions)](#2-观测动作-observation-actions)
    - [unit_observation - 单位观测](#unit_observation---单位观测)
    - [faction_observation - 阵营观测](#faction_observation---阵营观测)
    - [godview_observation - 全局观测](#godview_observation---全局观测)
    - [limited_observation - 受限观测](#limited_observation---受限观测)
    - [tactical_observation - 战术观测](#tactical_observation---战术观测)
  - [3. 状态查询动作 (Query Actions)](#3-状态查询动作-query-actions)
    - [get_unit_list - 获取单位列表](#get_unit_list---获取单位列表)
    - [get_unit_info - 获取单位详情](#get_unit_info---获取单位详情)
    - [get_faction_units - 获取阵营单位](#get_faction_units---获取阵营单位)
    - [get_game_state - 获取游戏状态](#get_game_state---获取游戏状态)
    - [get_map_info - 获取地图信息](#get_map_info---获取地图信息)
    - [get_battle_status - 获取战斗状态](#get_battle_status---获取战斗状态)
    - [get_available_actions - 获取可用动作](#get_available_actions---获取可用动作)
    - [get_unit_capabilities - 获取单位能力](#get_unit_capabilities---获取单位能力)
    - [get_visibility_info - 获取视野信息](#get_visibility_info---获取视野信息)
    - [get_strategic_summary - 获取战略摘要](#get_strategic_summary---获取战略摘要)
- [错误处理](#错误处理)
  - [常见错误类型](#常见错误类型)
- [使用示例](#使用示例)
  - [基本单位操作序列](#基本单位操作序列)
  - [观测和情报收集](#观测和情报收集)
- [注意事项](#注意事项)
- [更新日志](#更新日志)

---

## 核心接口

### 主要方法

#### `execute_action(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]`

执行指定类型的动作。

**参数：**
- `action_type` (str): 动作类型名称
- `params` (Dict[str, Any]): 动作参数字典

**返回值：**
- `Dict[str, Any]`: 包含执行结果的字典
  - `success` (bool): 执行是否成功
  - `error` (str, 可选): 错误信息（失败时）
  - 其他字段根据具体动作类型而定

**示例：**
```python
# 移动单位
result = handler.execute_action("move", {
    "unit_id": 123,
    "target_position": [5, 3]
})
# 返回: {"success": True, "message": "Unit 123 moved to [5, 3]", "unit_id": 123, "new_position": [5, 3]}
```

#### `get_supported_actions() -> Dict[str, Dict[str, Any]]`

获取所有支持的动作类型及其详细信息。

**返回值：**
- `Dict[str, Dict[str, Any]]`: 支持的动作字典，键为动作名称，值为动作详细信息

## 动作分类

### 1. 单位动作 (Unit Actions)

#### move - 移动单位

**功能描述：** 将指定单位移动到目标位置

**输入参数：**
- `unit_id` (int, 必需): 要移动的单位 ID
- `target_position` (list[int], 必需): 目标位置坐标 [col, row]

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 moved to [5, 3]",
  "unit_id": 123,
  "new_position": [5, 3]
}
```

**失败示例：**
```json
{
  "success": false,
  "error": "Movement failed - check path, movement points, or obstacles",
  "unit_id": 123,
  "target_position": [5, 3]
}
```

#### attack - 攻击目标

**功能描述：** 使用指定单位攻击目标单位

**输入参数：**
- `unit_id` (int, 必需): 攻击方单位 ID
- `target_id` (int, 必需): 目标单位 ID

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 attacked unit 456",
  "attacker_id": 123,
  "target_id": 456,
  "target_remaining_health": 75
}
```

#### defend - 设置防御

**功能描述：** 设置单位为防御状态，提供防御加成

**输入参数：**
- `unit_id` (int, 必需): 要设置防御的单位 ID

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 is now defending",
  "unit_id": 123,
  "defense_bonus": 0.5
}
```

#### scout - 侦察区域

**功能描述：** 使用指定单位侦察目标区域，临时增加视野范围

**输入参数：**
- `unit_id` (int, 必需): 执行侦察的单位 ID
- `target_position` (list[int], 必需): 侦察目标位置 [col, row]

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 is scouting",
  "unit_id": 123,
  "enhanced_vision_range": 7,
  "original_vision_range": 5
}
```

#### retreat - 单位撤退

**功能描述：** 单位向指定方向撤退到安全位置

**输入参数：**
- `unit_id` (int, 必需): 要撤退的单位 ID
- `direction` (str, 可选): 撤退方向 ("north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest")

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 retreated to [4, 2]",
  "unit_id": 123,
  "retreat_position": [4, 2]
}
```

#### fortify - 构建防御

**功能描述：** 在当前位置构建防御工事，提供额外防御加成

**输入参数：**
- `unit_id` (int, 必需): 执行构建的单位 ID

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 is now fortified",
  "unit_id": 123,
  "fortification_bonus": 0.3
}
```

#### patrol - 巡逻任务

**功能描述：** 在指定区域执行巡逻任务

**输入参数：**
- `unit_id` (int, 必需): 执行巡逻的单位 ID
- `patrol_area` (list[list[int]], 必需): 巡逻区域的坐标列表

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 started patrolling",
  "unit_id": 123,
  "patrol_points": [[5, 3], [6, 4], [7, 3]]
}
```

#### end_turn - 结束回合

**功能描述：** 结束当前单位或阵营的回合

**输入参数：**
- `unit_id` (int, 可选): 要结束回合的单位 ID
- `faction` (str, 可选): 要结束回合的阵营

**返回结果：**
```json
{
  "success": true,
  "message": "Turn ended for faction WEI",
  "faction": "WEI"
}
```

#### select_unit - 选择单位

**功能描述：** 选择指定单位，清除其他单位的选择状态

**输入参数：**
- `unit_id` (int, 必需): 要选择的单位 ID

**返回结果：**
```json
{
  "success": true,
  "message": "Unit 123 selected",
  "unit_id": 123
}
```

#### formation - 设置阵型

**功能描述：** 设置单位阵型

**输入参数：**
- `unit_id` (int, 必需): 要设置阵型的单位 ID
- `formation_type` (str, 必需): 阵型类型 ("offensive", "defensive", "mobile")

**返回结果：**
```json
{
  "success": true,
  "message": "Formation defensive set for 1 units",
  "unit_ids": [123],
  "formation_type": "defensive"
}
```

### 2. 观测动作 (Observation Actions)

#### unit_observation - 单位观测

**功能描述：** 获取指定单位的详细观测信息

**输入参数：**
- `unit_id` (int, 必需): 要观测的单位 ID

**返回结果：**
```json
{
  "success": true,
  "observation": {
    "id": 123,
    "name": "张飞",
    "faction": "SHU",
    "type": "CAVALRY",
    "position": {"col": 5, "row": 3},
    "health": {"current": 100, "max": 100, "percentage": 1.0}
  }
}
```

#### faction_observation - 阵营观测

**功能描述：** 获取指定阵营的观测信息

**输入参数：**
- `faction` (str, 必需): 阵营名称 ("WEI", "SHU", "WU")
- `include_hidden` (bool, 可选): 是否包含隐藏信息

**返回结果：**
```json
{
  "success": true,
  "observation": {
    "faction": "SHU",
    "units": [
      {
        "id": 123,
        "name": "张飞",
        "type": "CAVALRY",
        "position": {"col": 5, "row": 3}
      }
    ],
    "unit_count": 1
  }
}
```

#### godview_observation - 全局观测

**功能描述：** 获取全局视角的观测信息（上帝视角）

**输入参数：** 无

**返回结果：**
```json
{
  "success": true,
  "observation": {
    "all_units": [
      {
        "id": 123,
        "name": "张飞",
        "faction": "SHU",
        "position": {"col": 5, "row": 3}
      },
      {
        "id": 456,
        "name": "曹操",
        "faction": "WEI", 
        "position": {"col": 8, "row": 6}
      }
    ],
    "total_unit_count": 2
  }
}
```

#### limited_observation - 受限观测

**功能描述：** 获取受限视角的观测信息（基于阵营视野）

**输入参数：**
- `faction` (str, 必需): 观测方阵营名称 ("WEI", "SHU", "WU")

**返回结果：**
```json
{
  "success": true,
  "observation": {
    "faction": "SHU",
    "units": [
      {
        "id": 123,
        "name": "张飞",
        "type": "CAVALRY",
        "position": {"col": 5, "row": 3}
      }
    ],
    "unit_count": 1
  }
}
```

#### tactical_observation - 战术观测

**功能描述：** 获取战术层面的观测信息

**输入参数：**
- `unit_id` (int, 可选): 观测中心的单位 ID
- `radius` (int, 可选): 观测半径，默认为 3

**返回结果：**
```json
{
  "success": true,
  "observation": {
    "center_position": {"col": 5, "row": 3},
    "radius": 3,
    "units_in_area": [
      {
        "id": 456,
        "name": "曹操",
        "faction": "WEI",
        "position": {"col": 7, "row": 4},
        "distance_from_center": 2
      }
    ],
    "unit_count": 1
  }
}
```

### 3. 状态查询动作 (Query Actions)

#### get_unit_list - 获取单位列表

**功能描述：** 获取所有单位的列表，支持按阵营、类型、状态过滤

**输入参数：**
- `faction` (str, 可选): 筛选指定阵营的单位
- `unit_type` (str, 可选): 筛选指定类型的单位
- `status` (str, 可选): 筛选指定状态的单位 ("alive", "wounded", "ready")

**返回结果：**
```json
{
  "success": true,
  "units": [
    {
      "id": 123,
      "name": "张飞",
      "faction": "SHU",
      "type": "CAVALRY",
      "position": {"col": 5, "row": 3},
      "health_percentage": 1.0
    }
  ],
  "total_count": 1,
  "filters_applied": {
    "faction": "SHU",
    "unit_type": null,
    "status": "alive"
  }
}
```

#### get_unit_info - 获取单位详情

**功能描述：** 获取指定单位的详细信息

**输入参数：**
- `unit_id` (int, 必需): 要查询的单位 ID

**返回结果：**
```json
{
  "success": true,
  "unit_info": {
    "id": 123,
    "name": "张飞",
    "faction": "SHU",
    "type": "CAVALRY",
    "position": {"col": 5, "row": 3},
    "health": {"current": 100, "max": 100, "percentage": 1.0},
    "movement": {"current": 3, "max": 3, "has_moved": false, "remaining_movement": 3},
    "combat": {"attack": 85, "defense": 70, "range": 1, "has_attacked": false},
    "vision": {"sight_range": 5},
    "status": {
      "current_status": "ready",
      "is_defending": false,
      "is_fortified": false,
      "is_moving": false,
      "is_patrolling": false,
      "is_scouting": false
    }
  }
}
```

#### get_faction_units - 获取阵营单位

**功能描述：** 获取指定阵营的所有单位

**输入参数：**
- `faction` (str, 必需): 阵营名称 ("WEI", "SHU", "WU")

**返回结果：**
```json
{
  "success": true,
  "faction": "SHU",
  "units": [
    {
      "id": 123,
      "name": "张飞",
      "faction": "SHU",
      "type": "CAVALRY",
      "position": {"col": 5, "row": 3}
    }
  ],
  "total_count": 1
}
```

#### get_game_state - 获取游戏状态

**功能描述：** 获取当前游戏状态信息

**输入参数：** 无

**返回结果：**
```json
{
  "success": true,
  "game_state": {
    "game_exists": true,
    "current_player": "SHU",
    "game_mode": "BATTLE",
    "turn_number": 5,
    "phase": "action",
    "time_limit": null,
    "victory_condition": "elimination"
  }
}
```

#### get_map_info - 获取地图信息

**功能描述：** 获取地图信息，包括地形和单位位置

**输入参数：**
- `position` (list[int], 可选): 查询特定位置的地图信息 [col, row]
- `area` (list[list[int]], 可选): 查询区域范围 [[min_col, min_row], [max_col, max_row]]
- `include_terrain` (bool, 可选): 是否包含地形信息，默认 true
- `include_units` (bool, 可选): 是否包含单位信息，默认 true

**返回结果：**
```json
{
  "success": true,
  "map_info": {
    "terrain": [
      {
        "position": {"col": 5, "row": 3},
        "passable": true,
        "type": "GRASSLAND",
        "movement_cost": 1,
        "defense_bonus": 0.0
      }
    ],
    "unit_positions": [
      {
        "unit_id": 123,
        "name": "张飞",
        "faction": "SHU",
        "position": {"col": 5, "row": 3}
      }
    ]
  }
}
```

#### get_battle_status - 获取战斗状态

**功能描述：** 获取当前战斗状态信息

**输入参数：**
- `battle_id` (int, 可选): 特定战斗 ID
- `faction` (str, 可选): 查询指定阵营的战斗状态

**返回结果：**
```json
{
  "success": true,
  "battle_status": {
    "active_battles": [],
    "recent_battles": [
      {
        "turn": 4,
        "attacker": "张飞",
        "defender": "曹操",
        "damage": 25,
        "result": "hit"
      }
    ],
    "casualties": {
      "total_units": 5,
      "wounded_units": 1,
      "dead_units": 0,
      "healthy_units": 4
    }
  }
}
```

#### get_available_actions - 获取可用动作

**功能描述：** 获取指定单位可执行的动作列表

**输入参数：**
- `unit_id` (int, 必需): 要查询的单位 ID

**返回结果：**
```json
{
  "success": true,
  "unit_id": 123,
  "available_actions": ["move", "attack", "defend", "fortify", "select_unit"]
}
```

#### get_unit_capabilities - 获取单位能力

**功能描述：** 获取指定单位的能力信息

**输入参数：**
- `unit_id` (int, 必需): 要查询的单位 ID

**返回结果：**
```json
{
  "success": true,
  "unit_id": 123,
  "capabilities": {
    "can_move": true,
    "can_attack": true,
    "has_vision": true,
    "movement_range": 3,
    "attack_range": 1,
    "attack_power": 85,
    "defense_power": 70,
    "sight_range": 5
  }
}
```

#### get_visibility_info - 获取视野信息

**功能描述：** 获取视野和可见性信息

**输入参数：**
- `unit_id` (int, 可选): 查询指定单位的视野信息
- `faction` (str, 可选): 查询指定阵营的视野信息

**返回结果（单位视野）：**
```json
{
  "success": true,
  "unit_id": 123,
  "visibility_info": {
    "sight_range": 5,
    "center_position": {"col": 5, "row": 3},
    "visible_area_size": 61,
    "visible_units": [
      {
        "id": 456,
        "name": "曹操",
        "faction": "WEI",
        "position": {"col": 7, "row": 4}
      }
    ],
    "visible_unit_count": 1
  }
}
```

**返回结果（阵营视野）：**
```json
{
  "success": true,
  "faction": "SHU",
  "visibility_info": {
    "faction": "SHU",
    "observing_units": 3,
    "total_visible_area": 150,
    "visible_enemy_units": [
      {
        "id": 456,
        "name": "曹操",
        "faction": "WEI",
        "position": {"col": 7, "row": 4}
      }
    ],
    "enemy_unit_count": 1
  }
}
```

#### get_strategic_summary - 获取战略摘要

**功能描述：** 获取战略层面的摘要信息

**输入参数：**
- `faction` (str, 可选): 查询指定阵营的战略摘要
- `detail_level` (str, 可选): 详细程度 ("basic", "detailed", "full")

**返回结果：**
```json
{
  "success": true,
  "strategic_summary": {
    "global_stats": {
      "total_units": 15,
      "active_factions": 3
    },
    "faction_stats": {
      "SHU": {
        "total_units": 5,
        "healthy_units": 4,
        "wounded_units": 1,
        "dead_units": 0,
        "ready_to_move": 3,
        "ready_to_attack": 4,
        "total_attack_power": 425,
        "total_defense_power": 350
      },
      "WEI": {
        "total_units": 5,
        "healthy_units": 5,
        "wounded_units": 0,
        "dead_units": 0,
        "ready_to_move": 5,
        "ready_to_attack": 5,
        "total_attack_power": 450,
        "total_defense_power": 375
      }
    },
    "target_faction": "SHU",
    "target_faction_details": {
      "total_units": 5,
      "healthy_units": 4,
      "wounded_units": 1,
      "dead_units": 0,
      "ready_to_move": 3,
      "ready_to_attack": 4,
      "total_attack_power": 425,
      "total_defense_power": 350
    }
  }
}
```

## 错误处理

### 常见错误类型

1. **参数错误**
```json
{
  "success": false,
  "error": "Missing unit_id parameter"
}
```

2. **实体不存在**
```json
{
  "success": false,
  "error": "Unit 123 does not exist"
}
```

3. **动作不支持**
```json
{
  "success": false,
  "error": "Unsupported action type: invalid_action",
  "supported_actions": ["move", "attack", "defend", ...]
}
```

4. **系统错误**
```json
{
  "success": false,
  "error": "Movement system not available"
}
```

5. **执行失败**
```json
{
  "success": false,
  "error": "Movement failed - check path, movement points, or obstacles",
  "unit_id": 123,
  "target_position": [5, 3]
}
```

## 使用示例

### 基本单位操作序列

```python
# 1. 获取可用单位列表
units = handler.execute_action("get_unit_list", {"faction": "SHU"})

# 2. 选择一个单位
handler.execute_action("select_unit", {"unit_id": 123})

# 3. 获取单位详细信息
unit_info = handler.execute_action("get_unit_info", {"unit_id": 123})

# 4. 检查可用动作
actions = handler.execute_action("get_available_actions", {"unit_id": 123})

# 5. 移动单位
result = handler.execute_action("move", {
    "unit_id": 123,
    "target_position": [6, 4]
})

# 6. 攻击敌方单位
attack_result = handler.execute_action("attack", {
    "unit_id": 123,
    "target_id": 456
})
```

### 观测和情报收集

```python
# 1. 全局观测
global_view = handler.execute_action("godview_observation", {})

# 2. 阵营观测
faction_view = handler.execute_action("faction_observation", {"faction": "WEI"})

# 3. 单位侦察
scout_result = handler.execute_action("scout", {
    "unit_id": 123,
    "target_position": [8, 6]
})

# 4. 获取视野信息
visibility = handler.execute_action("get_visibility_info", {"unit_id": 123})

# 5. 战略摘要
summary = handler.execute_action("get_strategic_summary", {"faction": "SHU"})
```

## 注意事项

1. **参数验证**: 所有必需参数都必须提供，缺少参数会导致错误
2. **实体存在性**: 操作前会验证单位/实体是否存在
3. **状态依赖**: 某些动作依赖于单位当前状态（如移动点数、行动点数）
4. **系统依赖**: 部分功能依赖于特定系统的存在（如移动系统、战斗系统）
5. **坐标系**: 使用六边形网格坐标系 (col, row)
6. **阵营名称**: 支持的阵营为 "WEI"（魏）、"SHU"（蜀）、"WU"（吴）

## 更新日志

- v1.0: 初始版本，包含基本单位操作、观测和查询功能
- 支持的动作类型: 移动、攻击、防御、侦察、撤退、加固、巡逻等
- 支持的观测类型: 单位观测、阵营观测、全局观测、受限观测、战术观测
- 支持的查询类型: 单位列表、单位信息、游戏状态、地图信息、战斗状态等
