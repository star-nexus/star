# rotk_env

STAR 的 **ENV** 层：六边形 ECS 战场、动作网关、观测与结算。评测怎么起 Hub、起 Agent、配 API key，以仓库根目录 [README.md](../README.md) 为准，这里不重复。

四层分工：`rotk_agent`（模型侧）→ GameServer（Hub）→ **`rotk_env`（本目录）** → `framework`（引擎 / ECS）。本目录的入口是 `rotk_env/main.py`，不是独立发行的三国小游戏。

## 入口

需要先有本地 Hub（见根 README）。常见命令：

```bash
# 跳过开始界面，窗口开一局 BOT 对 BOT（仍会连本地 Hub）
uv run rotk_env/main.py --skip-start --players ai_vs_ai

# 评测 / CI：dummy 显示，结束自动退。仍然连 Hub，所以 auto_test 要先起 GameServer
uv run rotk_env/main.py --headless --players three_kingdoms

# 无窗口、也不连 Hub：规则 BOT 对打，不需要 GameServer
uv run rotk_env/main.py --headless --no-hub --players ai_vs_ai

# 人打两 BOT
uv run rotk_env/main.py --skip-start --players human_vs_two_ai

# 赤壁图
uv run rotk_env/main.py --skip-start --scenario chibi
```

`--headless` 只关窗口（dummy 显示）。连不连 Hub 是另一件事：默认连 `ws://localhost:8000/ws/metaverse`，`--hub-url` 可改地址，`--no-hub` 完全不打开 websocket。

| 参数 | 作用 |
| :--- | :--- |
| `--mode turn_based\|real_time` | 回合制或实时 |
| `--players` | `human_vs_ai` / `ai_vs_ai` / `three_kingdoms` / `human_vs_two_ai`。不带 `--skip-start` / `--headless` 时仍进开始界面 |
| `--scenario` | `default` / `chibi`（`rotk_env/maps/*.json`）/ `three_kingdoms`（仍用 `river_split.json`，只改阵营数） |
| `--seed` | 锁地图生成和战斗掷骰，不是整局逐帧回放。优先级：`--seed` > `$STAR_SEED` > `.configs.toml` |
| `--env-id` | Hub 上的环境 id |
| `--hub-url` | Hub websocket。省略时用 `$STAR_HUB_URL`，再没有就用本地默认地址 |
| `--no-hub` | 不连 Hub。规则测试和离线 BOT 用这个 |

本地操作（人机窗口）：左键选/移动/攻击，右键取消，WASD 移镜头，空格结束回合，Tab 统计，F1 帮助，Esc 取消选择。

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

入局 `register_agent_info` 同时返回 `map.home_bases` 和 `game_actions`（本局名单与文档）。Agent 写进 system prompt，不把主表当允许列表。

`get_faction_state` 的 `faction` 必须是调用方自己的阵营（否则 2005）。返回己方全量单位（每条带 `owner` / `commandable`），以及当前视野内的敌军（`visible_enemy_units`：编号、兵种、位置、人数）。迷雾打开时，可见区域是己方所有单位视野的并集；按 `1` 关闭迷雾后，可见区域是整张地图。人、BOT、Agent 共用这一条开关。各阵营基地坐标在入局 `register_agent_info` 的 `map.home_bases` 里（开局布阵中心，带 `home_bases_meaning`）。Agent 把它们写进 system prompt 的地图章节，不进 `get_faction_state`。同阵营已认领单位只有主人能下令。

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
