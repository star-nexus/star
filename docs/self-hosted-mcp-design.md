# StarBench 自托管 MCP：统一部署技术设计

状态：研发设计与实现约束；2026-10-15 更新本机接入边界，当前实现与验证状态见 [实施记录](self-hosted-implementation.md)。本文面向开发者、架构评审和测试人员，不是玩家操作手册。现有可运行流程见 [MCP 上手指南](arena.md)；网络子项目的接口和验收见 [网络接入子项目设计](network-subproject-design.md)。

## 1. 问题与目标

StarBench 已验证本机 Rust ENV、HUB 和 MCP 工具执行链路，也已通过 Desktop Commander 命令转发验证 ChatGPT 网页模型能够读取战场并执行移动。但后者依赖其他公司的工具服务、设备接入和调用配额，不能作为产品的长期接入基础。

目标是交付同一套可独立运营的开源服务器：运营者可以使用家庭电脑、独立服务器或 VPS，玩家通过标准 MCP 或原生协议进入比赛。官服/社区服表示运营和结果信任关系，不表示硬件类别，也不决定软件功能。

固定的应用逻辑链路：

```text
ChatGPT / 其他 MCP 客户端 → StarBench MCP → 私有 HUB → Rust ENV
原生 Agent Harness      → StarBench 协议入口 ──────┘
```

本阶段验收以 ChatGPT 直接发现 StarBench 工具、OAuth 登录、认领 Units、提交动作并确认世界状态变化为准。通过终端执行脚本访问 HTTP 接口不能替代该验收。

## 2. 需求条件与成立前提

| 条件 | 设计含义 |
|---|---|
| 使用 ChatGPT 网页端的模型能力 | 暴露 MCP 工具；不要求服务器配置模型 API key 或用 API BOSS 替代网页选手 |
| 其他 AI 客户端和自由 Harness 也能参赛 | MCP/原生协议共用身份与执行语义；具体客户端仍须验证协议和认证兼容性 |
| 一台电脑或 VPS 均可运营完整比赛 | 相同 OAuth、匹配、赛事和榜单能力；不按主机类型裁剪功能 |
| 网络条件存在差异且会变化 | 网络接入作为独立子项目，通过版本化接口接入 StarBench |
| 游戏已有成熟实现 | 复用 Rust ECS/ENV、star-protocol、HUB 和渲染；本阶段不改变游戏规则或优化执行器 |
| 有权限执行的远程动作 | OAuth 只证明身份，Arena 仍校验比赛/席位/Agent，ENV 校验动作是否合法 |
| 面向公网自托管 | 至少存在一个客户端可达的 HTTPS 入口，且认证发现、登录和回调链路可用 |

以下是部署前提，不是软件能够自动保证的事实：域名控制权、可用证书、外部可达地址、路由器/防火墙权限、运营商允许的入站连接、目标客户端的网络能力和账号权限。

当前实例条件：家庭 Mac，DNS 曾实测仅发布 AAAA，已配置 10000–11000 入站范围。2026-10-15 运营者说明：独立 Mac MCP Gateway 项目已有 mcp.starverse.chat 的有效证书，公网 Caddy 故意停用，现役链路使用私人 OpenAI Secure MCP Tunnel。STAR 的本机实例因此使用 existing 入口模式，不重复申请证书、不扩大 DNS 权限、不修改 Gateway 的服务、证书存储或启动配置。独立主机仍支持 direct。以上都是实例条件，不成为核心代码的默认网络假设。

## 3. 必须保留的设计约束

下列约束是实现和验收要求，不是仅供参考的建议。

| ID | 必须满足的约束 |
|---|---|
| C01 | 不依赖 Desktop Commander、商业隧道或 StarBench 官服的中转服务才能运行；社区服可独立运营 |
| C02 | 不把“自托管”实现为更名后的第三方远程服务客户端；引用开源代码不能保留隐含的商业后台依赖 |
| C03 | StarBench 核心不得导入网络子项目实现，不得按家庭宽带、VPS、IPv4/IPv6、隧道品牌分支执行游戏逻辑 |
| C04 | 核心不保存路由器、DNS、SSH 或证书管理凭据；网络组件不保存游戏操作结果或决定阵营权限 |
| C05 | 不把 Mac、私服或 attach 等同于无认证开发模式；正式联网实例使用明确的账号授权 |
| C06 | 不暴露无认证 HUB、数据库、Worker 控制接口或本机任意命令/文件工具给参赛客户端 |
| C07 | 不让模型读取源码、执行终端脚本来替代 MCP 工具发现；stdio 可以保留，但不是网页接入的前提 |
| C08 | 网络组件不得自动重放工具请求、合并业务请求或改写 operation_id；动作幂等仍由 Arena/ENV 负责 |
| C09 | 不让网络重连、入口切换或请求间隔改变 ENV 时钟、重置回合期限或自动结束回合 |
| C10 | 不承诺软件能绕过 CGNAT/防火墙、零延迟、无限容量、自动公网可达或跨崩溃恰好一次执行 |
| C11 | 不默认切换到第三方中转来掩盖网络失败；缺少公网条件时明确返回原因，保留本机能力 |
| C12 | 不将社区服自报结果直接纳入官服可信榜单；不同实例独立维护账号和数据 |
| C13 | 本阶段不引入新的游戏机制、自动模型调用或渲染器依赖；认证服务不充当动作中转服务 |

“不依赖第三方转发”指动作数据路径无需其他公司的专有中转产品。它不意味着消除 ISP、域名注册、公共 CA、模型提供方等互联网基础依赖。使用 Caddy、OpenSSH、Keycloak 等开源软件的自托管实例符合约束。

## 4. 项目边界与依赖方向

新增独立网络子项目，暂名 **star-network**。首选独立仓库、独立版本和测试；StarBench 部署层固定其发行版本并调用。独立仓库现已建立，StarBench 通过部署层调用其 JSON CLI。它应能服务一个普通 HTTP/WebSocket 应用，不以游戏代码为前提。

```text
部署层：StarBench 部署配置/启动编排
         ├─ 配置并启动 Arena、HUB、ENV、认证与数据库
         └─ 调用 star-network → 网络计划、HTTPS 接入、状态证据

动作数据：客户端 → 网络入口 → Arena → HUB → ENV
身份流程：客户端 ↔ 自托管身份服务 → Arena 验证令牌
```

| 模块 | 拥有的职责 | 不拥有的职责 |
|---|---|---|
| StarBench 核心：Arena/协议/ENV | 工具、身份验证、比赛与席位授权、时钟、动作、事件、结果 | DNS、路由器、NAT、SSH 隧道、证书签发 |
| star-network | 公网路由、TLS、可达性诊断、可选 DDNS、自管隧道及其恢复 | OAuth 账号、阵营/Units、策略、比赛重放或胜负 |
| 身份服务 | OAuth/OIDC、账号、登录与令牌签发；默认 Keycloak/GitHub | 网络穿透、游戏控制权、动作路由 |
| StarBench 部署层 | 组合组件、注入公开地址、收集检查结果、协调升级/迁移 | 复制 ENV 规则或在应用请求中运行网络修复 |
| 外部 GameServer HUB | 私有 star-protocol 消息路由 | 公网身份注册、DNS/TLS |

只由部署层依赖 star-network；Arena 仅接收公开服务 URL、身份服务配置、内部绑定地址和必要的受信代理配置。网络子项目不得导入 `starbench_arena`、`rotk_env`、`protocol`，也不访问比赛数据库。

这里拆分的是“公网接入与部署环境适配”，不是所有网络通信代码。MCP HTTP 服务、star-protocol 的连接/ACK/业务重试和 HUB 消息路由仍由现有应用模块负责，不迁入网络子项目。

Keycloak 的地址需要被网络子项目发布，但 Realm、GitHub 配置和用户授权仍由身份/部署层管理。OAuth audience、issuer 与回调的一致性由部署层校验，Arena 做运行时令牌校验。

## 5. 正交配置维度

| 维度 | 选项 | 归属 |
|---|---|---|
| 运行位置 | macOS/Linux 主机、VPS | 部署层 |
| ENV 生命周期 | attach / managed | Arena |
| 网络入口 | direct / self-hosted relay / existing ingress | star-network |
| 登录方式 | 自托管 OIDC；默认 GitHub，也可运营者本地账号 | 身份服务与 Arena |
| 赛事用途 | 私人局、正式赛；独立赛季 | Arena |
| 展示 | Three.js / pygame / 无窗口 | ENV 展示层 |

attach 连接运营者已经启动的 ENV，默认不计分，不额外施加公网赛事时限；managed 自动管理 Worker 并运行赛事策略。这是生命周期差异，与网络位置无关。Mac 可以运行完整 managed 赛事，VPS 也可以 attach。

现有 `starbench_arena.local` 和固定 `local:wei` / `local:shu` 凭据仅保留为本机兼容入口。提取其中 attach 能力，与 LocalAuth 解耦，供正式 OAuth 服务复用。旧本地身份不会自动转成某个 GitHub 用户；用显式迁移或新局完成切换。

## 6. 核心配置与网络契约

star-network 只接收通用服务描述，例如公网 host、内部 upstream、是否需要 HTTP streaming/WebSocket，以及入口适配器的独立配置。它产生版本化的网络计划、生成配置清单和带证据的状态报告。完整契约见 [子项目设计](network-subproject-design.md#contract)。

StarBench 部署层从结果中提取并校验：

- 对外 MCP/原生入口 URL、认证服务公开地址；所有工具继续使用现有句柄和 schema。
- 内部监听与可达 upstream；Mac 的回环地址与容器网络地址不得混为一谈。
- 配置版本与入口就绪证据；外部验证尚未完成时不能输出“ChatGPT 已可用”。

部署层不得将网络插件名、路由器型号、DDNS 提供商、SSH 配置注入游戏请求。公开域名变化属于身份资源变更，必须协调 OAuth 配置和客户端重连，不能只修改 DNS 后假定旧令牌仍然适用。

## 7. 首次部署与迁移策略

独立部署可选 direct：域名指向运营者主机，由自管入口发布 HTTPS。当前研发 Mac 选择 existing，只导出 STAR 的路由要求与状态，不管理现有 Gateway 入口。动态地址检测与可选 DDNS 是网络适配器职责，首版仅检测，不自动修改 A/AAAA。

分别验证实际发布的 A/AAAA 和公开端口，不强制先 IPv4 或必须使用 443。高位 HTTPS 端口仍需目标客户端实测；DNS-01 可用于无需 80/443 入站的证书签发。已有入口模式不参与证书签发或续期。拿到证书不能证明服务可达。

Mac 优先在主机进程运行 Arena/HUB/Rust ENV，身份/数据库等基础设施可容器化；Linux VPS 沿用 Compose。两者共用核心配置和网络契约，差异由部署适配层处理。HUB、数据库和 Worker 管理接口不发布为公网路由。

搬迁到 VPS 时停止接受新局、等待比赛结束、备份恢复数据与认证状态、切换入口并重验。不得承诺迁移运行中的 Rust 世界。网络子项目升级/重载应只影响自己拥有的入口组件，不自动终止 ENV；实际断线对比赛的影响遵循赛事策略。

## 8. 已有能力与待实现范围

| 范围 | 当前状态 | 下一步 |
|---|---|---|
| Rust ENV/HUB、MCP/原生工具、动作去重 | 已实现，已做本地验证 | 保持语义，补直连验收 |
| 本机 attach | 已实现，固定本地凭据 | 分离生命周期与认证，接入 OAuth 席位授权 |
| 生产 OAuth、Compose 配置生成 | 已有代码，公网联合验收未完成 | 验证发现、回调、PKCE、资源身份与续期 |
| 网络管理 | 独立 star-network 首版已实现 direct/existing、配置契约及 Caddy 实测 | 完成各运营者的独立外网验收，不在 Arena 增加环境判断 |
| 自托管发行与 Mac 安装编排 | 未统一 | 共用配置契约，分别提供主机进程和 Compose 驱动 |
| 官服与社区服独立运营 | 设计目标 | 独立域名、issuer、数据库、席位管理和第二部署者验收 |

实施影响位置：

- `starbench_arena/config.py`：明确业务运行配置、外部资源地址和受信代理配置；不加入 DNS/隧道配置。
- `starbench_arena/local.py` / `app.py`：提取 attach 装配，共用认证和工具服务。
- `starbench_arena/auth.py` / `service.py`：OAuth attach 的账号席位授权及身份迁移。
- `deploy/arena/`：作为整合层消费固定版本 star-network，管理 Keycloak 和各服务进程。
- `docs/arena.md`：功能实施并通过验收后再更新玩家/管理员操作指南；不能把设计示意当作可执行命令。

## 9. 复用原则与非目标

Desktop Commander 仓库采用 MIT 许可证。若复用具体代码，应固定提交、保留许可和版权声明、记录修改，并核对引用组件的许可证。本设计阶段尚未复制其源码。

可借鉴设备端的就绪检测、重连退避与抖动、凭据持久化、撤销处理、重复投递防护及优雅退出。但其设备端默认连接远程服务并获取 Supabase 配置，不能凭设备端开源就推断完整商业后台均已开源，不能原样接入其商业控制平面。

优先使用现有 MCP SDK、Arena/ENV 幂等实现和成熟网络软件。不为复制设备代码引入 Node/Supabase 技术栈；不自研 NAT 穿透、OAuth 协议或跨客户端常驻模型调度。本阶段也不建设官方设备云、自动官服/私服联赛和任意远程桌面能力。

## 10. 分阶段交付与验收

| 阶段 | 交付 | 验收证据 |
|---|---|---|
| A | star-network 最小契约、direct/existing 适配器、诊断；StarBench 使用假实现验证边界 | 不导入游戏模块也可发布普通测试服务；核心不安装网络子项目也可运行本机测试 |
| B | 统一自托管配置、OAuth attach、Mac direct 编排 | 外网 DNS/TLS/认证回调通过；未授权账号无法占席；旧本地 token 无法绕过 OAuth |
| C | ChatGPT 原生直连两种游戏模式 | 不启用 Desktop Commander；工具发现、登录、认领、移动、后续观测和终局结果均有证据 |
| D | Mac managed 与 Linux VPS 打包；自有 relay 适配器 | 两榜结算、重连/故障、备份恢复；同一核心代码在两种网络入口下工作 |
| E | 第二位运营者独立部署 | 自有域名/认证/数据，无需官服账号中心或中转服务；形成正式使用文档 |

网络子项目与 StarBench 的验证分开记录：网络可达不能证明游戏合法执行，游戏本机测试也不能证明公网可达。联合验收覆盖请求丢失/中断、不自动重放、OAuth 发现和登录、跨账号隔离、SSE/WebSocket 以及长时间空闲后的再次调用。

待实施前确定：实例域名、DNS 提供商、路由器/主机端口映射、证书签发方式、身份服务部署位置。缺少这些输入不妨碍核心与网络契约开发，但会阻止真实公网验收。

## 11. 参考依据

- [Desktop Commander LICENSE](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/LICENSE)
- [Remote Device 说明](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/README.md)
- [device.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/device.ts)
- [remote-channel.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/remote-channel.ts)
- [OpenAI：连接和测试 MCP](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [OpenAI：OAuth 认证](https://developers.openai.com/plugins/build/auth)

## 12. 与 Mac MCP Gateway 的可选集成边界

Mac MCP Gateway 是独立项目，不是 STAR 的必需运行依赖。其现役 OpenAI Secure MCP Tunnel 链路和证书不由本项目管理。现有证书到期日由运营者报告为 2027-01-11，本轮未读取或修改该项目证书存储。

若将 STAR 加为第二个 MCP 上游，必须先确定独立路由及资源身份，避免覆盖 Gateway 的 `/mcp`。上游仍使用 STAR OAuth 服务，保留每位调用者的身份绑定和 audience 校验。不能将本机 `local:wei`/`local:shu` token、管理员 token 或某个选手的 token 配成所有 Gateway 用户共用的凭据。

只有 Gateway 能逐调用转发经 STAR 验证的用户令牌，或双方另外实现并验证明确的身份交换协议，才能开放游戏写操作。当前版本不实现 token exchange，也不自动配置 Gateway；若缺少身份传递能力，只能先接只读探针，不能降级为共享游戏控制令牌。

验收必须独立记录：①公网 HTTPS 可达；②OAuth 身份及席位绑定；③ChatGPT 原生工具发现和调用。私人 Tunnel 成功不等于公网 HTTPS 成功，Caddy/本机 MCP 测试通过也不等于 ChatGPT 已接通。


## 13. 2026-11-04 接入方式调整

运营者明确要求保留 HTTPS + 域名 + IPv6，同时允许 ChatGPT 使用官方 tunnel-client。直接 HTTPS 仍是通用客户端的独立路径；OpenAI Secure MCP Tunnel 只作为部分客户端的可选入口，不是 STAR 的默认依赖，也不引入 starmux 或 Desktop Commander。该调整替代第 12 节中本机 Tunnel 不由本轮操作的限制：本次获准重定向现有 tunnel-client 上游，未修改其他应用的服务、源码和证书。控制权仍逐用户绑定，传输凭据不代表游戏身份。

当前域名为 `auth.starverse.chat`，端口 10000；既有 `mcp.starverse.chat` 归其他项目，不作为 STAR 默认值。公开 HTTPS、Tunnel 原生调用、OAuth 身份绑定分别验收，任何一路通过都不冒充其他路径通过。
