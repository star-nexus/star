# 三国策略游戏 (Romance of the Three Kingdoms Strategy Game)

基于 framework ECS 架构的六边形回合制策略游戏。

## 游戏特色

### 🎮 双模式支持

- **回合制模式**: 经典的回合制策略玩法
- **实时模式**: 动态实时战斗体验

### 🗺️ 六边形地图系统

- 基于数学精确的六边形坐标系
- 支持复杂的地形和移动路径
- 优化的 A\*寻路算法

### 🏔️ 多样化地形系统(本功能暂时关闭)

- **平原**: 无特殊效果，标准移动和战斗
- **森林**: 提供隐蔽和防御加成，降低移动速度
- **山地**: 攻击和防御加成，视野加成，移动困难
- **丘陵**: 适中的攻防加成和视野加成
- **水域**: 严重影响移动和战斗能力
- **城池**: 强大的防御加成

### 👁️ 战争迷雾系统

- 每个单位有独立的视野范围
- 同阵营共享视野信息
- 地形影响视野范围和视线阻挡
- 区分"可见"和"探索过"的区域

### 🤖 智能 AI 系统

- 多层次的 AI 决策逻辑
- 战术级 AI：攻击、移动、防御选择
- 战略级 AI：地形利用、单位协调
- 可配置的 AI 难度等级

### 📊 详细统计系统

- 实时战斗统计
- 阵营对比分析
- 历史战斗记录
- 单位效率统计

## 游戏单位

### 步兵 (Infantry)
- 特点: 平衡的属性，适合占领和防守

### 骑兵 (Cavalry)
- 特点: 高机动性，适合快速突击

### 弓兵 (Archer)
- 特点: 远程攻击能力，需要保护

### 攻城器械 (Siege)（TO DO）
- 特点: 强大的攻击力，移动缓慢

## 三大阵营

### 魏 (Wei) - 蓝色

- 代表北方势力
- 通常配置为人类玩家
- 出生点位于地图北部

### 蜀 (Shu) - 红色

- 代表西南势力
- 默认 AI 控制
- 出生点位于地图南部

### 吴 (Wu) - 绿色

- 代表东南势力
- 三国模式中可用
- 出生点位于地图东部

## 控制说明

### 基本操作

- **鼠标左键**: 选择单位/移动/攻击
- **鼠标右键**: 取消选择
- **WASD/方向键**: 移动摄像机
- **空格键**: 结束回合

### 界面控制

- **Tab 键**: 显示/隐藏统计面板
- **F1 键**: 显示/隐藏帮助信息
- **ESC 键**: 取消当前选择

### 游戏操作

1. 选择己方单位（左键点击）
2. 查看移动范围（蓝色高亮）
3. 查看攻击范围（红色圆圈标记敌人）
4. 左键点击目标位置移动或攻击
5. 空格键结束回合

## 安装和运行

### 环境要求

- Python 3.13
- pygame 2.0+
- framework (项目自带)

### 安装依赖

```bash
pip install pygame
```

### 运行游戏

```bash
# 基本运行
uv run rotk/main.py

# 指定游戏模式
uv run rotk/main.py --mode turn_based

# AI对战模式（跳过开始界面，直接开局）
uv run rotk_env/main.py --skip-start --players ai_vs_ai

# 三国鼎立全 AI（评测；headless 走 dummy 显示）
uv run rotk_env/main.py --headless --players three_kingdoms

# 人打两 BOT
uv run rotk_env/main.py --skip-start --players human_vs_two_ai

# 赤壁之战（长江 + 北岸乌林/曹营 + 南岸赤壁）
uv run rotk_env/main.py --skip-start --scenario chibi
```

从真三国无双赤壁图生成格子：把截图放到任意路径，用六边形网罩住并按格内像素分类地形：

```bash
uv run python -m rotk_env.maps.hex_sample path/to/chibi_source.png \
  --out rotk_env/maps/chibi.map \
  --overlay /tmp/chibi_hex_overlay.png
```

分类不准的格子直接改 `rotk_env/maps/chibi.map`（`.` 平原 `~` 水 `F` 林 `H` 丘 `M` 山 `C` 城）。

### 命令行选项

- `--mode [turn_based|real_time]`: 游戏模式
- `--players [human_vs_ai|ai_vs_ai|three_kingdoms|human_vs_two_ai]`: 玩家配置。需配合 `--skip-start` 或 `--headless` 才会生效；否则仍进开始界面手动选。`three_kingdoms` 为魏/蜀/吴全 AI（评测）；人打两 BOT 用 `human_vs_two_ai`。
- `--skip-start`: 跳过开始界面，用命令行的 `--players` / `--mode` / `--scenario` 直接进对局（保留窗口）
- `--headless`: 同 `--skip-start`，但 dummy 显示、对局结束自动退出（评测 / CI）
- `--scenario [default|chibi|three_kingdoms]`: `chibi` 加载 `rotk_env/maps/chibi.map`；`three_kingdoms` 目前仍用默认河界图，只改变玩家阵营数
- `--help`: 显示帮助信息

## 获胜条件

胜负由 `GameOverPolicy` 统一判定，回合制与实时制共用：

1. **胜利**: 全歼对手（场上只剩己方有存活单位）
2. **失败**: 被全歼（与胜利相反）
3. **平局**:
   - 双方存活单位同时归零
   - 超时：回合制 `turn_number` 超过 100；实时制 `GameTime` 已过 3600 秒。超时一律平局，不按剩余兵力判胜负

没有积分胜利，也没有半歼。

### BOT baseline

`MockLLMAISystem` 是规则 BOT：通过 `LLMActionHandler` 下达 move/attack。只控制带 `AIControlled` 且**尚未注册 LLM agent** 的阵营，因此 `auto_test` 的 LLM vs LLM 对局不会被 BOT 抢操作。人机或 LLM vs BOT 时，未挂 agent 的 AI 阵营由 BOT 接手。

### LLM 动作目录

`rotk_env/prefabs/action_catalog.py` 是 agent `perform_action` 的 enum 和 ENV `get_action_list` 的同一份名单。单位动词必须等于 `ActionType.value`；查询 / meta / 观测是 LLM 网关名，不是额外的 ECS 动作。

| Profile | 内容 |
| :--- | :--- |
| `bench`（默认） | `move` / `attack` / `get_faction_state`。评测 agent 的 schema 就是这三项，不必先调 `get_action_list`。 |
| `full` | occupy / skill / 观测 / `get_action_list` / `end_turn` 等 |
| `debug` | 另含 `godview_observation`（只出现在 debug 名单；ENV 公开入口仍按 `full` 拒绝） |

`get_action_list` 默认返回 `bench`；传 `profile=full` 看完整文档。未知动作失败关闭（error 2010），不再用 `get_*` / `*_observation` 前缀猜测。

回合制里模型要结束回合，必须走独立 tool `end_turn`（agent 注册，不经过 `perform_action`）。ENV 协议名仍是 `end_turn`，catalog 的 `full` 里有这条；实时模式没有该 tool。

### 可复现性与实时

`--seed`（其次 `$STAR_SEED`、配置）锁的是**地图生成和战斗掷骰**（`RngService`），不是整局逐帧回放。

- **回合制**：世界只在行动 / `end_turn` 时变。LLM 想多久不影响棋盘。这是可复现 bench。
- **实时**：模型思考时主循环仍在跑，AP/MP 按模拟时间回复，对手可以行动。思考耗时进入战局，这是评测定义，不是 bug。同一 seed 换模型或换推理延迟，对局可以不同。

主循环锁定 **60 FPS**，每帧模拟步长固定为 `1/60` 秒（不是墙钟帧间隔）。因此实时 AP 约为每秒 1 点、MP 约每 3 秒回满；不要改成 30 FPS，否则同样墙钟下回复会减半。观测缓存按 `World.revision` 失效，单位刚移动后不会在 1 秒内读到旧坐标。

## 技术架构

### ECS 架构

基于 Entity-Component-System 模式构建：

- **Entity**: 游戏中的实体对象
- **Component**: 数据容器（位置、生命值、单位类型等）
- **System**: 逻辑处理器（移动、战斗、AI 等）

### 核心系统

1. **MapSystem**: 地图生成和管理
2. **TurnSystem**: 回合制逻辑控制
3. **MovementSystem**: 单位移动和寻路
4. **CombatSystem**: 战斗计算和处理
5. **VisionSystem**: 视野和战争迷雾
6. **MockLLMAISystem**: 规则 BOT baseline（`AISystem` 仍保留源码，当前未挂入对局）
7. **InputHandlingSystem**: 输入处理
8. **RenderSystem**: 图形渲染

### 六边形数学

使用立方坐标系统实现精确的六边形计算：

- 距离计算
- 邻居查找
- 路径规划
- 视野计算

## 开发计划

### 已完成功能 ✅

- [x] 基础 ECS 架构
- [x] 六边形地图系统
- [x] 回合制游戏逻辑
- [x] 单位移动和战斗
- [x] 战争迷雾系统
- [x] AI 对手
- [x] 游戏统计界面
- [x] 多种地形效果
- [x] 图形用户界面
- [x] 实时模式支持
- [x] 小地图
- [x] 更多单位类型
- [x] 多人网络对战

### 计划中功能 🚧

- [ ] 技能和特殊能力
- [ ] 地图编辑器
- [ ] 战役模式
- [ ] 音效和音乐
- [ ] 动画效果优化

## 贡献指南

欢迎提交问题报告和功能建议！

### 开发环境设置

1. 克隆项目
2. 安装依赖：`uv pip install pygame`
3. 运行测试：`uv run rotk/main.py`

### 代码结构

```
rotk/
├── __init__.py          # 模块初始化
├── config.py            # 游戏配置和常量
├── components.py        # ECS组件定义
├── systems.py           # 核心游戏系统
├── vision_ai_systems.py # 视野和AI系统
├── input_render_systems.py # 输入和渲染系统
├── hex_utils.py         # 六边形数学工具
├── events.py            # 游戏事件定义
├── game.py              # 主游戏类
├── main.py              # 启动入口
└── README.md            # 文档
```

## 致谢

本项目基于 framework ECS 框架开发，感谢所有贡献者的努力！

