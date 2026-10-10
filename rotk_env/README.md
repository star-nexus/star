# rotk_env

STAR 的 **ENV** 层：六边形 ECS 战场、动作网关、观测与结算。评测怎么起 Hub、起 Agent、配 API key，以仓库根目录 [README.md](../README.md) 为准，这里不重复。

四层分工：**ECS Framework、star-protocol、STARBench ENV、Agent**。GameServer 路由现有协议；不同 ENV 和 Agent 继续通过 `env_id` / `agent_id` 通信。Rust 只替换本目录 ENV 的权威执行，不要求更改 Hub、协议或参与者 Agent。

## 入口

先启动现有 Hub（见根 README），Rust 工具链与 Python 3.13 需要可用：

```bash
# 默认 Rust：窗口菜单，选择 External Agent / Hub 后开始
uv run --extra native rotk_env/main.py

# 跳过菜单：联网三阵营评测
uv run --extra native rotk_env/main.py --skip-start --players three_kingdoms --mode real_time

# 无窗口联网评测；auto_test.py 也默认 Rust
./run_headless_env.sh --players three_kingdoms --mode real_time

# 明确离线（静态 AI 槽没有控制器）
uv run --extra native rotk_env/main.py --headless --no-hub --players ai_vs_ai

# Python 对照 / 回退；本地规则 BOT 暂只在 Python 下可用
uv run rotk_env/main.py --backend python --skip-start --no-hub --mock-ai --players human_vs_two_ai
```

`--headless` 只关窗口；`--no-hub` 才关闭联网。Hub 地址继续采用 `--hub-url`、`$STAR_HUB_URL`、`ws://localhost:8000/ws/metaverse` 的原有优先顺序。Rust 扩展缺失、oracle/API 或宿主能力不匹配会明确报错，不自动换成 Python。

| 参数 | 作用 |
| :--- | :--- |
| `--backend rust\|python` | 默认 Rust；显式 Python 对照 |
| `--native-threads 1\|2\|4` | 默认 1；仅 ENV 内部配置 |
| `--native-scheduling threaded\|serial` | 默认独立权威时钟；serial 为帧驱动回退，联网仍使用单一权威执行器 |
| `--mode turn_based\|real_time` | 回合制或实时 |
| `--players` | 槽位拓扑，独立于控制器选择 |
| `--scenario` / `--seed` | 地图及 RNG 种子；不锁定网络到达顺序 |
| `--env-id` / `--hub-url` | 现有 Hub 身份及地址 |
| `--no-hub` | 明确离线 |
| `--runtime-manifest PATH` | 本地运行清单；不增加协议字段 |

快捷键：`1` 步兵、`2` 骑兵、`3/4/5` 三名弓兵；`M/A` 移动/攻击；`W/G/C/F` 等待/驻防/占领/筑垒；方向键及 `+/-` 镜头；`Shift+1` 迷雾，`Shift+2/3/4` 阵营视角；F1 帮助，Esc 先取消目标再取消选择。

实现与有限联网验收见 [Rust ENV 宿主](../docs/native-hub-host.md)。

## 规则以代码为准

数字在 `rotk_env/prefabs/config.py` 的 `GameConfig`。模拟真正用到的地形字段：

| 字段 | 谁用 |
| :--- | :--- |
| `movement_cost` | `MovementSystem`（水为 999，且水格是障碍） |
| `attack_bonus` / `defense_bonus` | `CombatSystem`，再乘 `TERRAIN_COEFFICIENTS` |
| `vision_bonus` | `VisionSystem`：站在该格时加到单位 `vision.range`。丘陵 +1，山地 +2。山地还挡视线 |

没有命中率、射程削减、围城回血、船只兵种。兵种属性是 `UNIT_BASE_STATS`（步/弓/骑）。胜负由 `GameOverPolicy` 判定：全歼胜，被全歼负，同时死光或超时（回合制 100 回合 / 实时 3600 秒）平局。

## LLM 网关

棋盘动作分两层：ENV **主表**（`prefabs/action_catalog.py` 里所有已实现动词）和 **本局子集**（`MatchRules.game_actions`）。Agent 永远看不到主表。

默认遭遇战（当前 default / chibi / three_kingdoms 同一套玩法）：

- 实时：`move` / `attack` / `get_faction_state`
- 回合制：以上三项，加上 `end_turn`

`get_action_list` 是系统动作，返回本局子集，没有 `profile=full` 升级。未知名字 **2010**；主表里有但本局没有 **2003**。`defend` / `scout` / `retreat` 不在主表上。回合制结束回合走独立 tool `end_turn`，不进 `perform_action`。`move` 只经过 `MovementSystem.move_unit`，按路径耗 MP，不耗 AP。

入局 `register_agent_info` 同时返回 `map.home_bases` 和 `game_actions`（本局名单与文档）。Agent 写进 system prompt，不把主表当允许列表。第三方 Agent 的接线合同是仓库根目录 [`docs/agent-protocol.md`](../docs/agent-protocol.md)，不是本目录的 LLM handler 内部文档。

`get_faction_state` 的 `faction` 必须是调用方自己的阵营（否则 2005）。返回的是 **observation + 当前动作掩码**：己方全量单位（每条带 `owner` / `commandable`，以及 `reachable` / `attackable`），当前视野内的敌军（`visible_enemy_units`：编号、兵种、位置、人数，不带掩码），以及 `visible_terrain`。`reachable` 是此刻 `move` 会接受的格子，不是 MP 半径；`attackable` 是此刻 `attack` 会接受的 `target_id`。敌方单位不给这两项。合同见 [`docs/observation-affordance.md`](../docs/observation-affordance.md)。迷雾打开时，可见区域是己方所有单位视野的并集；按 `Shift+1` 关闭迷雾后，可见区域是整张地图。人、BOT、Agent 共用这一条开关。各阵营基地坐标在入局 `register_agent_info` 的 `map.home_bases` 里（开局布阵中心，带 `home_bases_meaning`）。Agent 把它们写进 system prompt 的地图章节，不进 `get_faction_state`。同阵营已认领单位只有主人能下令。

## BOT

`MockLLMAISystem` 通过 `LLMActionHandler` 下 move/attack。只控制带 `AIControlled` 且**尚未注册 LLM agent** 的阵营，所以 LLM vs LLM 不会被 BOT 抢操作。

## 可复现性与实时

`--seed` 锁的是地图和掷骰，不锁 Hub 延迟或模型思考时间。回合制下 LLM 思考不推演棋盘。实时下思考时世界仍按帧跑：`GameTime.game_elapsed_time` 每帧加上 `dt * time_scale`（暂停不加）。AP / MP / 攻击次数 / 技能 CD 都读这本棋盘秒，不另累一份引擎 `delta_time`。人和 Agent 走墙钟，想得久就会在实时局里吃亏。观测缓存跟 `World.revision`。细节见根 README。

## 赤壁图采样

```bash
uv run python -m rotk_env.maps.hex_sample path/to/chibi_source.png \
  --out rotk_env/maps/chibi.json \
  --overlay /tmp/chibi_hex_overlay.png
```

格子：`.` 平原 `~` 水 `F` 林 `H` 丘 `M` 山 `C` 城。
