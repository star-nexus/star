# StarBench 自托管 MCP：统一部署设计

状态：设计方案，尚未实施本页新增的配置与部署能力。现有可运行命令仍以 [MCP 上手指南](arena.md) 为准。

## 1. 产品目标

同一个开源 StarBench 服务既能在个人电脑运行，也能在 VPS 运行。官服和社区服务器的区别是运营者、域名、参赛规则和数据归属，不是服务器硬件或一套不同的软件。

所有部署遵循同一条应用链路：

```text
ChatGPT / 其他 MCP 客户端 → StarBench MCP → 私有 HUB → Rust ENV
原生 Agent Harness      → StarBench 协议入口 ──────┘
```

玩家在客户端中连接自己的目标服务器、登录、参赛；不需要读取源码或执行终端脚本来发现游戏工具。服务端不调用模型 API 来替代 ChatGPT 网页选手。

服务器自行提供 HTTPS 与 OAuth，不把 Desktop Commander、商业隧道、StarBench 官方转发平台作为运行依赖。开源基础设施可作为部署组件，但其服务实例由服务器运营者管理。

## 2. 将三个选择分开

| 选择 | 选项 | 影响 |
|---|---|---|
| 运行位置 | Mac/Linux 主机、VPS | 进程和计算资源在哪里 |
| ENV 生命周期 | attach / managed | 使用已启动的 ENV，或由 Arena 创建和管理比赛 Worker |
| 网络入口 | direct / self-hosted relay | 主机直接接受公网 HTTPS，或经自有入口到达主机 |

身份认证、工具语义、动作合法性与上述选择无关。自托管电脑也能启用正式比赛、匹配、榜单；这些能力通过 managed 模式提供。attach 模式保留人工启动和调试场景，默认不计分，不额外替 ENV 定义比赛时限。

当前的 `starbench_arena.local` 是固定阵营令牌的离线接入便捷入口。继续保留兼容性，但不把它当作联网自托管的认证基础。自托管服务器应使用与 VPS 相同的 OAuth 流程。

## 3. 统一的服务组成

- **Caddy：** HTTPS、证书和公网路由。客户端入口稳定为 `https://<arena-domain>/mcp`；原生 Harness 使用同域名 WSS。
- **StarBench Arena：** MCP、原生协议入口、账号与席位授权、比赛管理、事件和结果存储。沿用现有实现，不增加一层通用工具执行服务。
- **Keycloak：** 自托管 OAuth/OIDC，默认对接 GitHub。社区服可自行配置本地账号或其他登录方式，不能要求所有社区服依赖官服账号中心。
- **GameServer HUB：** 私有消息路由。保留独立项目边界，不直接向互联网开放研究用途的无认证入口。
- **Rust ENV：** 动作目录、观测和执行。Three.js/pygame 是独立展示选择。
- **PostgreSQL：** 推荐用于联网赛事及认证。现有 SQLite 本机实验路径继续保留；它不是对私服能力的限制。

OAuth 登录/刷新不应逐动作查询 GitHub。Arena 根据令牌与缓存的签名公钥验证身份，再检查比赛、阵营和 Agent 所有权。Keycloak、GitHub 不作为游戏动作消息中转服务。

首版每台部署只有一个 Arena 网关实例，沿用数据库租约约束，不直接增加 Uvicorn workers。

## 4. 公网可达性：由网络条件决定

### 4.1 直接入口（优先）

```text
ChatGPT → 主机上的 Caddy → Arena → HUB → ENV
```

适用于 VPS，也适用于有可用公网地址的家庭主机。家庭网络按情况配置端口映射、防火墙和动态 DNS。IPv6-only 路径需要从目标客户端的网络验证可达性，不能只凭本机有 IPv6 地址判定成功。

这种方式不需要任何转发 VPS。HTTPS 的服务器证书必须受客户端信任，域名、OAuth issuer、回调与资源地址必须一致。

### 4.2 自有入口（主机不能直接入站时）

```text
ChatGPT → 自有 VPS 上的 Caddy
                    │ 加密隧道
                    ▼
               Mac 上的 Arena → HUB → ENV
```

第一版采用成熟的 OpenSSH 反向端口转发和进程守护，不自研 NAT 穿透协议。Mac 主动连接运营者自己的 SSH 主机，VPS 上的转发监听只绑定回环地址，由 Caddy 对外发布 HTTPS。认证域名也必须能到达 Keycloak，可一并转发；不能只接通 `/mcp` 而让登录回调留在 localhost。

该路径只转发网络请求，不增加模型工具调用、不创建另一套 Agent 身份、不重新定义 operation_id。HUB 仍只在服务器侧私有网络使用。连接中断应返回明确不可用状态；重连不自动重放未知结果的动作。

自有入口引入真实网络跳数与可用性依赖，应记录实际部署路径和时延。它没有商业中转平台的按工具次数配额，但不能宣称零延迟或无限容量。

### 4.3 没有任何公网入口时

如果本机无法从公网访问，也没有任何可用的自有入口，则本机 MCP 客户端可用，ChatGPT 网页端直连尚不具备条件。应用代码无法凭空绕过运营商 CGNAT、防火墙或入站限制。

首次设置的网络诊断必须区分：本机服务存活、局域网可达、公共 DNS/TLS 正确、外部网络可达、ChatGPT 成功调用。不能用一次 localhost 健康检查替代公网验收。

## 5. 账号、席位与社区服独立性

公网采用授权码 + PKCE，沿用资源身份校验、过期校验与 `arena:play` scope。优先复用当前 Keycloak 配置；按真实 ChatGPT 客户端支持方式验证客户端注册、回调和令牌续期。不要重新手写一套 OAuth 服务。

- 每个部署有自己的稳定 server_id、认证 issuer、域名与数据库。
- managed：OAuth 账号注册 Harness 版本，比赛匹配分配席位，继续使用现有规则。
- attach：管理员显式将 OAuth 账号授权给某场现有 ENV 的某个阵营。登录不等于自动获得控制权，客户端不能填写任意 faction 接管别人席位。
- 旧的 `local:wei` / `local:shu` 记录不能自动迁移成任意 GitHub 账号；在配置停机窗口显式迁移，或新建一场验证局，保留旧局记录。
- 其他 AI 客户端通过同一 MCP 协议接入，能否使用还取决于该客户端支持的传输、认证和工具版本。
- 私服榜单独立。社区服自行报告的胜负不直接进入官服排名；若未来要联赛，再设计可信比赛来源规则。

## 6. 管理员与玩家的操作体验

### 管理员

统一提供设置、检查、启动、停止、查看状态、日志、备份和恢复操作，复用现有部署脚本能力。设置时只要求作出以下决定：

1. 运行主机和域名。
2. direct 或 self-hosted relay 网络入口。
3. GitHub/OIDC 配置及邀请名单。
4. attach 或 managed；attach 时填写 HUB、env_id、模式和账号席位映射。

工具只在全部必要配置通过后输出“可连接”。输出面向用户的 MCP URL、认证方式、健康检查结果和客户端操作步骤，不输出 token、client secret 或管理密码到普通日志。

实际 CLI 命令在实施时确定。本页不提供尚不存在的一键命令供用户复制。

### 玩家

在 ChatGPT 添加自定义 MCP 服务，填写目标服务器 HTTPS URL，按 OAuth 登录并安装连接。在聊天中选择 StarBench，调用 get_profile/list_matches 确认身份和比赛，然后直接使用观测与动作工具。社区服可以提供自己的连接地址，无需先成为官服的子节点。

公开插件目录发布是后续发现/分发渠道；自托管和自定义连接不要求项目先完成公开上架。不同服务域名的连接和 OAuth 身份独立维护。

## 7. Mac 与 VPS 使用同一套配置模型

Mac 首先支持 host-native 运行：Arena/HUB/Rust ENV 在主机进程运行，认证、数据库等基础设施可以由容器管理；公开域名与内部监听地址分开配置。这样复用现有 macOS Rust 运行路径。

Linux VPS 使用现有 Compose 方案管理所有组件。两种打包方式共用服务代码、配置校验、身份规则、工具 schema 和验收脚本；区别是进程启动方式、卷路径和内部地址。

从 Mac 迁往 VPS：停止创建新局、等对局结束、备份和恢复数据与认证状态、切换域名路由、验证 OAuth/工具调用。不得承诺搬迁运行中 Rust 世界或跨崩溃重放动作。保持域名与 issuer 有助于保留连接，但仍须验证令牌、证书和客户端缓存。

## 8. 对现有代码的具体改造

| 位置 | 改造 |
|---|---|
| `starbench_arena/config.py` | 将公网地址、内部监听地址、认证模式、ENV 生命周期和入口类型分开校验 |
| `starbench_arena/local.py` | 提取 attach 运行能力，与 LocalAuth/固定本地账号解耦；保留旧命令 |
| `starbench_arena/auth.py` / `service.py` | 复用生产 OAuth；新增 attach 账号席位授权与显式迁移策略 |
| `starbench_arena/app.py` | 共用服务装配；工具暴露由比赛生命周期能力决定，不由 Mac/VPS 决定 |
| `deploy/arena/` | 提供 host-native 和 Compose 配置生成、Caddy、Keycloak、自管隧道选项及诊断 |
| `docs/arena.md` | 对外只讲“搭建自己的服务器”和“连接已有服务器”，部署位置作为安装选择 |

不改游戏机制、Rust ECS、动作目录和战场渲染；不引入默认的命令执行、读文件或远程桌面工具。身份授权层不越过 ENV 的动作合法性检查。

## 9. Desktop Commander 的借鉴范围

已查看的开源仓库采用 MIT 许可证：复用源码时保留版权与许可声明，并记录来源、固定提交和本地修改。此方案阶段尚未复制其代码。

设备端代码包含有价值的运行经验：区分进程存活与可实际处理请求、持久化凭据、防止撤销后自动重新注册、断线退避与抖动、有限的重复投递检测、优雅退出。

但 `device.ts` 默认连接 `mcp.desktopcommander.app` 并请求 `/api/mcp-info`，`remote-channel.ts` 使用 Supabase 客户端；因此复制设备端不能替代公网服务、数据库、授权和网络入口部署。本次检查不宣称其整个商业后台都已开源。

StarBench 已经有 MCP SDK、Agent 身份和动作去重。优先复用现有能力并采用标准网络组件；不为引入它的设备代码而额外增加 Node/Supabase 运行架构，也不把设备端短期去重缓存当作 ENV 动作幂等保证。

源码与依据：

- [Desktop Commander LICENSE](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/LICENSE)
- [Remote Device 说明](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/README.md)
- [device.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/device.ts)
- [remote-channel.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/remote-channel.ts)
- [OpenAI：连接和测试 MCP](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [OpenAI：OAuth 认证](https://developers.openai.com/plugins/build/auth)

## 10. 实施与验收顺序

1. **统一自托管配置与 OAuth attach。** 先保留手动启动的 Mac ENV，验证不同账号只能使用被分配的阵营，重连不会重置比赛，旧本地令牌不能绕过公网认证。
2. **完成 Mac 的真实公网接入。** 根据网络诊断使用 direct 或自有入口。ChatGPT 原生工具列表中出现 StarBench 工具；不启用 Desktop Commander。登录、注册、认领、移动一次、轮询观测确认抵达、结束回合，两种模式分别验证。
3. **验证自托管 managed。** 在同一台 Mac 验证匹配、准备、超时、正常终局、两张榜单和 Worker 故障路径；不要求迁到 VPS 才能测试完整赛事。
4. **打包和 VPS 迁移演练。** 在干净 Linux 主机按文档部署，完成 GitHub OAuth 和相同客户端验收，再验证备份恢复。
5. **社区试运行。** 第二位运营者在独立设备部署，使用自己的域名、账号体系和数据；确认没有运行期访问 Desktop Commander 或官服中转入口的必要依赖。

已有能力：Rust ENV、HUB、MCP 工具、重试保护、本机 attach、生产 OAuth 校验及 Compose 配置生成。待完成能力：统一自托管配置、OAuth attach、Mac 网络入口打包/诊断、真实 ChatGPT OAuth 直连与 VPS 组合验收。
