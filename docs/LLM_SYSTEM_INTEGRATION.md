# LLM 系统集成文档

## 概述

为 LLM 系统新增了两个核心组件：

1. **LLM Action Handler** - 提供单位可执行操作的统一接口
2. **LLM Observation System** - 提供不同级别的游戏观测信息收集

## LLM Action Handler (动作处理器)

### 支持的动作类型

#### 单位动作

| 动作类型      | 参数                         | 描述               |
| ------------- | ---------------------------- | ------------------ |
| `move`        | `unit_id`, `target_position` | 移动单位到指定位置 |
| `attack`      | `attacker_id`, `target_id`   | 执行攻击动作       |
| `defend`      | `unit_id`                    | 设置防御状态       |
| `scout`       | `unit_id`, `target_area`     | 执行侦察动作       |
| `retreat`     | `unit_id`, `direction`       | 撤退到指定方向     |
| `fortify`     | `unit_id`                    | 设置驻防状态       |
| `patrol`      | `unit_id`, `patrol_points`   | 设置巡逻路径       |
| `end_turn`    | `faction`                    | 结束当前阵营回合   |
| `select_unit` | `unit_id`                    | 选择指定单位       |
| `formation`   | `unit_ids`, `formation_type` | 设置军队阵型       |

#### 观测动作

| 动作类型               | 参数                                   | 描述                 |
| ---------------------- | -------------------------------------- | -------------------- |
| `unit_observation`     | `unit_id`                              | 获取单位详细观测信息 |
| `faction_observation`  | `faction`, `include_hidden`            | 获取阵营观测信息     |
| `godview_observation`  | 无                                     | 获取上帝视角观测信息 |
| `limited_observation`  | `faction`                              | 获取受限观测信息     |
| `tactical_observation` | `center_position`, `radius`, `faction` | 获取战术区域观测信息 |

#### 状态查询动作

| 动作类型                | 参数                                       | 描述                 |
| ----------------------- | ------------------------------------------ | -------------------- |
| `get_unit_list`         | `faction`, `unit_type`, `status`           | 获取单位列表         |
| `get_unit_info`         | `unit_id`                                  | 获取指定单位详细信息 |
| `get_faction_units`     | `faction`                                  | 获取阵营所有单位     |
| `get_game_state`        | 无                                         | 获取游戏状态信息     |
| `get_map_info`          | `include_terrain`, `include_units`, `area` | 获取地图信息         |
| `get_battle_status`     | `faction`                                  | 获取战斗状态信息     |
| `get_available_actions` | `unit_id`                                  | 获取可用动作列表     |
| `get_unit_capabilities` | `unit_id`                                  | 获取单位能力信息     |
| `get_visibility_info`   | `unit_id` 或 `faction`                     | 获取视野信息         |
| `get_strategic_summary` | `faction`                                  | 获取战略摘要         |

### 使用示例

#### 单位动作示例

```python
# 移动单位
params = {
    "unit_id": 123,
    "target_position": [5, 8]  # (col, row)
}
result = llm_system.handle_move(params)

# 攻击目标
params = {
    "attacker_id": 123,
    "target_id": 456
}
result = llm_system.handle_attack(params)

# 设置防御
params = {
    "unit_id": 123
}
result = llm_system.handle_defend(params)
```

#### 观测动作示例

```python
# 获取单位观测信息
params = {
    "unit_id": 123
}
result = action_handler.execute_action("unit_observation", params)

# 获取阵营观测信息
params = {
    "faction": "WEI",
    "include_hidden": false
}
result = action_handler.execute_action("faction_observation", params)

# 获取战术区域信息
params = {
    "center_position": [5, 8],
    "radius": 3,
    "faction": "SHU"
}
result = action_handler.execute_action("tactical_observation", params)
```

#### 状态查询示例

```python
# 获取单位列表（过滤条件）
params = {
    "faction": "WEI",
    "status": "ready"  # "alive", "wounded", "ready"
}
result = action_handler.execute_action("get_unit_list", params)

# 获取单位详细信息
params = {
    "unit_id": 123
}
result = action_handler.execute_action("get_unit_info", params)

# 获取地图信息
params = {
    "include_terrain": true,
    "include_units": true,
    "area": {"min_col": 0, "max_col": 10, "min_row": 0, "max_row": 10}
}
result = action_handler.execute_action("get_map_info", params)

# 获取可用动作
params = {
    "unit_id": 123
}
result = action_handler.execute_action("get_available_actions", params)

# 获取视野信息
params = {
    "faction": "SHU"
}
result = action_handler.execute_action("get_visibility_info", params)

# 获取战略摘要
params = {
    "faction": "SHU"
}
result = action_handler.execute_action("get_strategic_summary", params)
```

### 返回格式

成功时：

```json
{
  "success": true,
  "message": "Unit 123 moved to [5, 8]",
  "unit_id": 123,
  "new_position": [5, 8]
}
```

失败时：

```json
{
  "success": false,
  "error": "Movement failed - check path, movement points, or obstacles",
  "unit_id": 123,
  "target_position": [5, 8]
}
```

## LLM Observation System (观测系统)

### 观测级别

| 级别      | 描述         | 权限                               |
| --------- | ------------ | ---------------------------------- |
| `unit`    | 单个单位视角 | 该单位的详细信息和视野范围内的信息 |
| `faction` | 阵营视角     | 己方所有单位 + 视野内的敌方单位    |
| `godview` | 上帝视角     | 全部信息（调试用）                 |
| `limited` | 受限视角     | 基于雾战系统的有限信息             |

### 使用示例

#### 1. 单位观测

```python
params = {
    "observation_level": "unit",
    "unit_id": 123
}
result = llm_system.handle_observation(params)
```

返回信息包含：

- 单位自身详细信息（血量、移动力、攻击力等）
- 可见区域内的其他单位
- 可见区域内的地形信息
- 可执行的动作选项

#### 2. 阵营观测

```python
params = {
    "observation_level": "faction",
    "faction": "WEI",
    "include_hidden": false
}
result = llm_system.handle_faction_observation(params)
```

返回信息包含：

- 己方所有单位的状态
- 已知的敌方单位信息
- 战略信息（总单位数、伤亡情况等）
- 领土控制情况
- 阵营资源状态

#### 3. 上帝视角观测

```python
params = {
    "observation_level": "godview"
}
result = llm_system.handle_godview_observation(params)
```

返回信息包含：

- 所有单位的完整信息
- 按阵营分组的单位列表
- 完整地图信息
- 全局统计数据
- 战斗历史记录

### 观测数据结构示例

#### 单位观测返回数据

```json
{
  "unit": {
    "id": 123,
    "name": "关羽",
    "faction": "SHU",
    "type": "CAVALRY",
    "position": { "col": 5, "row": 8 },
    "health": { "current": 80, "max": 100, "percentage": 0.8 },
    "movement": { "current": 3, "max": 4, "has_moved": false },
    "combat": { "attack": 15, "defense": 12, "range": 1, "has_attacked": false }
  },
  "visible_area": [
    [4, 7],
    [5, 7],
    [6, 7],
    [4, 8],
    [5, 8],
    [6, 8],
    [4, 9],
    [5, 9],
    [6, 9]
  ],
  "visible_units": [
    {
      "id": 456,
      "name": "曹操",
      "faction": "WEI",
      "position": { "col": 6, "row": 9 }
    }
  ],
  "visible_terrain": [
    {
      "position": { "col": 5, "row": 8 },
      "type": "PLAINS",
      "movement_cost": 1,
      "defense_bonus": 0
    }
  ],
  "action_options": ["move", "attack", "defend", "scout"]
}
```

## WebSocket 消息格式

### 动作请求

```json
{
  "instruction": "message",
  "data": {
    "id": "action_001",
    "action": "move",
    "parameters": {
      "unit_id": 123,
      "target_position": [5, 8]
    }
  },
  "msg_from": {
    "role_type": "agent",
    "env_id": 1,
    "agent_id": "player_1"
  }
}
```

### 观测请求

```json
{
  "instruction": "message",
  "data": {
    "id": "obs_001",
    "action": "faction_observation",
    "parameters": {
      "faction": "WEI",
      "include_hidden": false
    }
  },
  "msg_from": {
    "role_type": "agent",
    "env_id": 1,
    "agent_id": "player_1"
  }
}
```

## 集成到游戏中

### 1. 添加到游戏系统

```python
from rotk.systems import LLMSystem

# 在游戏初始化时添加LLM系统
llm_system = LLMSystem()
world.add_system(llm_system)
```

### 2. 配置 WebSocket 连接

LLM 系统会自动连接到指定的 WebSocket 服务器：

- 默认地址：`ws://localhost:8000/ws/metaverse`
- 环境 ID：1

### 3. 扩展功能

- 在`LLMActionHandler`中添加新的动作类型
- 在`LLMObservationSystem`中添加新的观测级别
- 自定义观测数据格式和缓存策略

## 注意事项

1. **权限控制**：不同观测级别有不同的信息访问权限
2. **缓存机制**：观测系统有 1 秒的缓存时间，避免频繁重复计算
3. **错误处理**：所有动作和观测请求都有完整的错误处理和反馈
4. **异步支持**：通过 WebSocket 实现异步通信，不阻塞游戏主循环
5. **扩展性**：模块化设计，易于添加新的动作类型和观测级别

## 开发建议

1. **测试动作**：先使用简单的 move 和 attack 动作测试基本功能
2. **观测调试**：使用 godview 级别观测来调试和验证游戏状态
3. **性能优化**：根据实际需求调整观测缓存时间和数据粒度
4. **权限管理**：在生产环境中严格控制 godview 级别的访问权限
