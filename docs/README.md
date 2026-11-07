# STAR 文档索引与阅读建议

这里汇总了 STAR 的使用指南、协议参考和设计记录。你可以根据自己的目标选择阅读入口。第一次接触项目，建议先读[项目 README](../README.md)，了解项目用途、安装方式和目录结构。

阅读时会遇到几个常用名称：**ENV** 指运行战场的游戏环境，**HUB** 负责传递消息，**Arena** 负责身份权限、赛事管理和工具接口。**MCP** 是 AI 客户端调用工具的协议，**Harness** 则是调用模型和工具的客户端程序。其他术语，以及账号、各类 ID 和命令执行位置的说明，见[阅读约定与名词](vps-arena.md#reading)。

## 按任务选择入口

| 我想做什么 | 从哪里开始 | 接下来读什么 |
|---|---|---|
| 了解项目并启动游戏 | [项目 README](../README.md) → [运行与 Agent 接入](integration.md) | [游戏规则](game-rules.md) |
| 使用运营者提供的公网 Arena 参赛 | [MCP 上手指南：加入公网比赛](arena.md#play) | 按客户端类型阅读[公网接入步骤](vps-arena.md#5-玩家端连接按客户端选择一条路径)，再查[工具与赛事参考](arena-reference.md) |
| 在一台电脑上让两个 AI 客户端对战 | [MCP 上手指南：本机启动](arena.md#local) | [配置客户端](arena.md#connect) → [游戏规则](game-rules.md) |
| 在全新 VPS 上部署 Arena | [全新 VPS 部署与多客户端指南](vps-arena.md) | [部署与运维说明](../deploy/arena/README.md) |
| 编写自己的 Agent 或 Harness | 先读下方“客户端开发者”的阅读建议 | 按需查阅协议、观测和工具参考 |
| 研究自托管架构或修改网络接入 | [自托管 MCP 设计](self-hosted-mcp-design.md) | [网络子项目设计](network-subproject-design.md) → [实施与验收记录](self-hosted-implementation.md) |
| 查阅既有 Mac 双插件实例的恢复方法 | [历史实例恢复手册](mac-duel-restart.md) | 确认原部署数据是否仍保留，再按手册操作 |

加入公网比赛时，玩家只需连接运营者提供的服务。HUB、ENV 和数据库由管理员部署。即使你同时担任管理员和玩家，也要注意各步骤要求在哪台机器、哪个目录执行。

## 推荐阅读顺序

### 新用户：从启动游戏开始

1. 阅读[项目 README](../README.md)，了解项目用途，选择适合自己的运行方式。
2. 按[运行与 Agent 接入](integration.md)启动游戏。如果希望通过 AI 客户端进行 MCP 对战，请按[MCP 上手指南](arena.md)操作。
3. 阅读[游戏规则](game-rules.md)，了解胜负条件、回合制与实时制、移动和攻击规则。
4. 遇到参数或协议问题时，再查阅下方索引中的参考文档。

### 部署者：从全新 VPS 到完成对战

1. 按[全新 VPS 指南](vps-arena.md)准备服务器和源码，配置域名与认证，然后启动服务。
2. 按指南中的客户端章节接入 ChatGPT 网页、Codex、Claude Code 或自写 Harness，并邀请两个不同的玩家账号。
3. 让两名玩家进入同一场比赛，确认动作实际生效，并在终局后读取结果。HTTPS 健康检查只是其中一步，完整验收还包括登录、权限和对战。
4. 阅读[运维说明](../deploy/arena/README.md)，了解备份、升级、停机和恢复要求，再逐步扩大开放范围。

首次部署直接从这份指南开始即可。它会说明所需条件、具体步骤和当前的验证范围；遇到尚未支持或验证的环节时，请按文中的说明处理。

### 客户端开发者：按连接方式选择文档

**加入公网 Arena：** 先读[公网登录与 Harness 接入](vps-arena.md#5-玩家端连接按客户端选择一条路径)，再读[Arena 工具与赛事参考](arena-reference.md)。通过公网 HTTP、MCP 或原生 WSS 接入时，都需要登录并取得比赛权限。服务器内部的 HUB 由 Arena 管理，不作为玩家的公网入口。

**连接自己管理的本地 HUB：** 先读[运行与 Agent 接入](integration.md)，再按[Agent–ENV 协议](agent-protocol.md)实现注册、观测、动作和终局处理。这条路径适用于自己管理的可信开发环境。

开发过程中，还可以查阅[观测与动作可用性](observation-affordance.md)、[游戏规则](game-rules.md)和[HUB 消息格式](hub-envelope.md)。注意区分 ENV 动作与 Arena 工具的名称和参数，例如 ENV 的 `get_faction_state` 在 Arena 中通过 `get_observation` 工具调用。

## 完整文档索引

| 文档 | 类型 | 内容与适用范围 |
|---|---|---|
| [运行与 Agent 接入](integration.md) | 操作指南 | 安装和启动游戏、在浏览器中查看战场、通过 HUB 连接自定义 Agent |
| [游戏规则](game-rules.md) | 规则参考 | 胜负、两种游戏模式、单位资源、地形、视野与操作 |
| [MCP 上手指南](arena.md) | 操作指南 | 本机对战、MCP 客户端配置、公网参赛与常见问题 |
| [全新 VPS 部署与多客户端指南](vps-arena.md) | 操作指南 | 准备服务器、配置认证、接入客户端，并完成邀请、匹配和对战验收 |
| [Arena 工具与赛事参考](arena-reference.md) | 接口参考 | 工具流程、原生 WSS、重试、网页 BOSS、结果和赛事规则 |
| [Agent–ENV 协议](agent-protocol.md) | 协议参考 | 自定义 Agent 在连接、注册、交互和终局处理时应遵守的协议 |
| [HUB 消息格式](hub-envelope.md) | 协议参考 | 消息信封、载荷、请求关联和错误码 |
| [观测与动作可用性](observation-affordance.md) | 接口参考 | 己方观测字段、单位控制、可移动位置和可攻击目标 |
| [自托管 MCP 设计](self-hosted-mcp-design.md) | 技术设计 | 部署架构、职责边界、约束与阶段验收要求 |
| [网络子项目设计](network-subproject-design.md) | 技术设计 | star-network 的接口、入口方式、生命周期和网络诊断边界 |
| [自托管实施与验收记录](self-hosted-implementation.md) | 实施记录 | 实例配置入口、历史实现进展、测试证据与验收限制 |
| [Mac 双插件恢复手册](mac-duel-restart.md) | 历史实例记录 | 特定 Mac 实例的恢复步骤，要求原部署数据仍保留 |

部分运行和协议文档使用英文。使用示例时，请按文中说明替换域名、路径、ID 和凭据，并将终端命令、客户端配置和聊天指令分别输入对应位置。

## 查阅时的注意事项

- **根据文档用途阅读。** 操作指南提供执行步骤，接口参考解释参数，设计和实施记录说明决策、约束与验证情况。
- **使用同一套部署流程。** 全新 VPS 指南采用 `deploy/arena/.env`；另一套自托管实例流程使用 `.arena/deployments/*/deployment.json`。各自的命令、路径和备份格式应配套使用。
- **留意历史记录的适用条件。** 文档中记录的 Mac 实例已于 2026-11-06 退役，其中的域名、席位和路径仅反映当时的环境。
- **遇到差异时，先核对版本和配置。** 结合目标版本的代码、命令帮助和实际结果排查，确认原因后再继续操作。

配套资料包括[部署与运维说明](../deploy/arena/README.md)、[登录示例](../examples/arena/login.py)、[多 Agent Harness 示例](../examples/arena/harness.py)和[协议一致性探针](../examples/protocol_conformance.py)。其中，Harness 示例用于演示连接和消息交互；实际参赛还需实现自己的作战策略。
