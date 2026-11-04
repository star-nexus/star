# 自托管 MCP 实施与验收记录

面向研发与部署维护者。本文区分可执行的本地流程、已验证能力和尚未完成的外部验收，不替代社区快速上手指南。

## 2026-11-04 恢复开发

部署继续采用 STAR 自身的 HTTPS MCP、Keycloak、Arena、私有 HUB 与 Rust ENV，不引入 starmux、Desktop Commander 或 Gateway 依赖。网络子项目随源码部署包一起交付；维护者使用一个 STAR 部署入口。其他项目现役服务和证书保持独立。

- 源工作区沿用 `codex/self-hosted-mcp`，积压实现已提交为 `9890c3d`，没有增加 worktree。
- 新实例必须显式提供 `--public-url`，不再默认占用 `mcp.starverse.chat`。
- 运营者已将 `auth.starverse.chat` 专门分配给 STAR；本轮准备 `https://auth.starverse.chat:10000/mcp`，实例目录 `.arena/deployments/star-direct/`。只读探针不连接 HUB 或游戏数据库。
- STAR 使用自身存储为新域名申请的证书已成功签发，TLS 本机校验通过，到期时间为 2027-02-02 20:42:21 UTC。没有使用另一项目的证书。
- 运营者更新 AAAA 后，Google DNS-over-HTTPS 返回 `2408:8207:1901:c050::4`；本机常规解析仍一度返回旧 `::2`。两种证据分开记录，未改写系统 DNS 或代理配置。
- ChatGPT 经官方 Tunnel 原生调用 `connectivity_probe` 已返回回执，且与 STAR 服务端日志核对一致；证据保存在本实例 `probe-evidence.json`。此结果不代表直接 HTTPS 外网或 OAuth/游戏控制已经通过。

当前官方文档仍支持 HTTPS Streamable HTTP 和静态预注册 OAuth 客户端。实际接入时从管理页复制精确回调；生产 Realm 显式提供 `profile`、`email` 与 `arena:play` scope，避免客户端请求已公布的 OIDC scope 时登录失败。[ChatGPT 接入说明](https://developers.openai.com/api/docs/guides/custom-mcp-server)、[认证契约](https://developers.openai.com/plugins/build/auth)。

认证服务放在 VM 时，本轮观察到约 3 秒签发时钟差。Arena 只对 `iat` 的未来时间容许最多 5 秒；签名、issuer、audience、scope、`exp` 和 `nbf` 仍严格校验。该容差不改变 ENV 时钟或回合规则。

Linux 镜像已在本轮构建成功，Compose 启动、健康接口、认证拒绝和 MCP 资源元数据检查通过。`tests/arena/container_smoke.py` 在 Arena 容器内连接独立私有 HUB，实际运行两种模式的 Rust Worker，验证注册、多 Agent、动作目录、观测、消息消费去重、回合结束重试、投降结算和 Elo。测试 API 仅存在于进程内，不公开开发认证端口，也不使用生产游戏数据库；这不替代真实玩家完整对局或 VPS 外网验收。

发行包使用两个仓库的提交源码和版本标识；未跟踪的私人文件、媒体和运行配置不打包，已跟踪源码有未提交更改时拒绝打包。项目中新出现的 `.tmp/`、`prepared-media/` 和 `videos/` 未修改或删除。

### ChatGPT 可选 Tunnel（2026-11-04 运营者调整）

运营者说明当前 ChatGPT 网络条件只能使用 Tunnel，其他客户端仍需 HTTPS。因此两条入口并存：

- 通用客户端 → `https://auth.starverse.chat:10000/mcp` → STAR。
- ChatGPT → OpenAI Secure MCP Tunnel → 官方 `tunnel-client` → `http://127.0.0.1:8781/mcp` → STAR。

两条路径最终调用同一 MCP 服务，OAuth 与席位权限由 STAR 验证。Tunnel 运行凭据不是游戏控制令牌；没有安装固定 Bearer、共享阵营 token 或终端工具。上游仍是只读探针，正式游戏入口需后续 OAuth 验收。

本机只有一个已配置 Tunnel ID。经运营者明确授权，已保存原路由配置，再将原本面向 `18893/mcp` 的 tunnel-client 切到 `8781/mcp`。starmux 应用本身未停止、代码和启动配置未改动；但使用同一个 Tunnel 的旧插件现在会到达 STAR，必须刷新工具。原路由可恢复，独立长期运行建议为两套应用分配不同 Tunnel ID，不能让同一 ID 的两个客户端同时转发到不同应用。

网络子项目 0.1.1 提供可选 `python -m star_network.tunnel start/status/stop`。本实例配置、私密运行凭据和原路由保存在 `.arena/deployments/star-direct/`，均不进入 Git。直接 HTTPS 部署无需安装 tunnel-client。Tunnel 的 `healthz/readyz` 已通过，客户端原生工具回执已与日志核对。其他 AI 客户端的直接 HTTPS 调用仍待单独验收。

```sh
# 从 STAR 根目录运行；部署命令内部调用随包交付的网络组件。
uv run python -m deploy.arena.self_hosted tunnel-status \
  --config .arena/deployments/star-direct/deployment.json

# 如需恢复原 Tunnel 上游：先停止 STAR 转发，再启动保存的原路由。
PYTHONPATH=../star-network uv run python -m star_network.tunnel stop \
  --config .arena/deployments/star-direct/tunnel.json \
  --state-dir .arena/deployments/star-direct/tunnel
PYTHONPATH=../star-network uv run python -m star_network.tunnel start \
  --config .arena/deployments/star-direct/tunnel.previous.json \
  --state-dir .arena/deployments/star-direct/tunnel
```

OAuth discovery 可以走 Tunnel，但浏览器登录和授权服务并不会因此自动全部可达；登录、令牌兑换、刷新仍需实际验收。[官方 Tunnel 文档](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)。

本轮主要回归：55 项 STAR 测试通过（包含真实 Keycloak），7 项独立网络测试通过，Linux 容器内两种模式测试通过。证据分别属于本地功能、容器运行和网络传输，不等同于公网比赛通过。

## 上轮记录（2026-10-15）

2026-10-15：STAR 在源工作区的 `codex/self-hosted-mcp` 分支实施；网络项目位于相邻的 `star-network` 独立仓库。本机配置目录为 `.arena/deployments/mac-direct/`，历史目录名保留，但入口已切换为 **existing**。

本轮不操作 `/Users/liyang/Developer/Mac-MCP-Gateway`，不扩大阿里云权限，不申请或读取其证书，不启动其 Caddy。该项目已有证书及私人 Tunnel 的状态来自运营者说明，不能作为 STAR 的公网验收结果。STAR 当前实例复制的 DNS 凭据已移除，原始用户文件未修改。

## 已实现的接口

- `star-network`：schema v1、direct/existing、计划/应用/诊断/停止/回滚、Caddy HTTP/SSE/WS。独立于游戏代码；existing 无证书/代理管理副作用。
- `AttachedArena`：连接已启动 ENV 的公共生命周期；`LocalArena` 保留旧令牌行为，`OAuthAttachedArena` 使用生产 JWT 和显式席位授权。
- `issuer + subject → match_id + faction` 授权存储；撤销后的请求被拒绝，旧原生连接失效。席位不能转给另一个账号，防止继承旧 Agent 的控制权；需要换账号时使用新 ENV。
- 生产数据库绑定 issuer，拒绝直接换 issuer 后沿用同名 subject。`get_profile` 可在尚未获得席位时调用。
- 完整公开 URL 配置保留非默认端口和认证路径；MCP audience、issuer、OAuth discovery、回调均从同一配置生成。
- Mac 主机进程 + 独立 Colima/Compose；Linux Compose；入口、数据库、认证和应用分开管理。

网络程序不拥有任何游戏 token。可选 Gateway 集成仍必须向 STAR 传递每位用户可验证的身份；不能将 `starbench_arena.local stdio` 的固定阵营身份当作共享公网游戏权限。

## 配置与命令

下面命令从 STAR 仓库根目录执行。示例域名必须替换；它们不会配置另一个项目的现役入口。

```sh
uv sync --extra rust-runtime --extra arena
uv run python -m deploy.arena.self_hosted init \
  --config .arena/deployments/my-server/deployment.json \
  --public-url https://star.your-domain.tld \
  --platform macos --lifecycle attach --ingress existing
```

`init` 生成独立的 `deployment.json`、`network.json` 和权限为 0600 的 `secrets.json`，拒绝覆盖已有配置。existing 不生成 DNS 凭据文件。需要独立申请证书的其他主机可选择 `--ingress direct`；默认 AliDNS DNS-01，也可在网络配置中改用已提供的证书文件。

部署层只通过网络子项目 JSON CLI 工作。开发时 `network_source` 指向相邻仓库；发行包包含固定版本的两个源码目录；`deploy/arena/network.lock.json` 固定网络项目提交与 Python 发行文件校验值，打包时拒绝混入其他提交。网络组件需要 Go 1.26.2 构建主机 Caddy；existing 无需构建或运行 Caddy。

凭据模板中填写 GitHub OAuth App 的 `GITHUB_CLIENT_ID`、`GITHUB_CLIENT_SECRET`，以及 ChatGPT 管理页显示的精确 `CHATGPT_REDIRECT_URIS`。GitHub OAuth App 的回调为：

`<auth_public_url>/realms/starbench/broker/github/endpoint`

不要把 GitHub App 的回调与 ChatGPT 客户端的回调混为一项。预注册 ChatGPT 客户端 ID 为 `starbench-chatgpt`，对应 secret 由模板生成，留在本机文件中。

```sh
uv run python -m deploy.arena.self_hosted plan --config .arena/deployments/my-server/deployment.json
uv run python -m deploy.arena.self_hosted prepare --config .arena/deployments/my-server/deployment.json
uv run python -m deploy.arena.self_hosted up --config .arena/deployments/my-server/deployment.json
uv run python -m deploy.arena.self_hosted diagnose --config .arena/deployments/my-server/deployment.json
```

`up` 启动前默认要求配置所在主机至少有 10 GiB 可用空间（`min_free_disk_gib` 可配置）；这是防止拉取镜像耗尽主机磁盘的下限，不能保证足够完成所有镜像构建。Docker 数据盘位于其他磁盘或远程主机时，还需检查对应磁盘。

`plan` 不启动服务；`prepare` 生成 Realm、应用与 Compose 配置；`up` 启动本实例服务。existing 不修改外部入口，必须由其运营者另行应用导出的路由。Mac 的 attach 模式要求先自行启动私有 HUB 和匹配 `attachment.env_id/mode` 的 Rust ENV。旧 `.arena/local.json`、8780 入口及现有世界不迁移。

登录后用 `get_profile` 得到 subject，再由运营者本机执行：

```sh
uv run python -m deploy.arena.self_hosted grant --config .arena/deployments/my-server/deployment.json \
  --subject USER_SUBJECT --faction wei
uv run python -m deploy.arena.self_hosted revoke --config .arena/deployments/my-server/deployment.json \
  --subject USER_SUBJECT --faction wei
```

授权表不通过 MCP 暴露。Mac 命令直接访问本实例数据库；Linux 命令通过本实例 Arena 容器执行，不需要公开数据库端口。重新授权同一 subject 恢复原 Agent；不会创建另一个用户可继承的席位。managed 使用原有邀请名单、赛事匹配、Worker 和两榜结算；实例配置 `lifecycle` 设为 `managed`，不额外启动外部 ENV。

`probe` 只启动独立的只读 MCP 连通性工具，不连接游戏数据库或 HUB。即使探针可调用，也不能代替 OAuth 和游戏控制验收。

旧的 `deploy/arena/deploy.py` 无 `--config` 用法继续保留；传入 `--config` 时转到新的实例部署命令。

## 备份、恢复、迁移

```sh
uv run python -m deploy.arena.self_hosted backup --config .arena/deployments/my-server/deployment.json
uv run python -m deploy.arena.self_hosted stop --config .arena/deployments/my-server/deployment.json
```

备份是包含 Arena、Keycloak 两个数据库的 PostgreSQL 自定义归档 ZIP，权限 0600，并输出 SHA-256。部署配置和凭据需另行安全保存；它们不会混入公开源码包。备份包含身份与游戏数据，不应公开分享。

恢复只允许两个目标数据库都为空、且除 PostgreSQL 外的本实例容器均已停止。先生成新实例配置，仅启动其 PostgreSQL，然后执行：

```sh
uv run python -m deploy.arena.self_hosted restore --config .arena/deployments/my-server/deployment.json \
  --backup-file /absolute/path/backup.zip
```

同一 issuer 才可直接恢复。更换 issuer 涉及身份迁移，命令会拒绝。复用同一逻辑部署时保留原认证配置与客户端 secret；启动前核对已恢复 Keycloak 的客户端配置。恢复失败不自动覆盖或清空数据库。

迁移前停止接收新局并等待现有比赛结束。备份不包含运行中的 Rust 世界，不承诺迁移活动比赛。配置变更后重新运行 `up`；现有主机 Gateway 若配置发生变化，需要先 `stop` 再 `up`，避免仍运行旧配置。

Linux VPS 使用 `init --platform linux --lifecycle managed`，选择 direct 或 existing。existing 仅将 Arena/Keycloak 映射到 VPS 回环地址；HUB/数据库无公网端口。direct 的 Caddy 由本实例 Compose 管理。Linux Compose 配置已通过解析；本次镜像构建在复制 Rust 工具链时因主机磁盘耗尽失败，未启动 Linux Arena/HUB。完整 Linux 容器与 VPS 外网仍需分别验收。

两个仓库提交后可生成不含运行配置和凭据的源码部署包（仅包含已提交文件）：

```sh
uv run python -m deploy.arena.self_hosted bundle --config .arena/deployments/my-server/deployment.json \
  --output .arena/releases/starbench-self-hosted.tar.gz
```

解压后保留 `star-main`、`star-network` 相邻目录，按目标实例重新初始化配置。不要复制本机旧的绝对路径配置到另一台机器。

## 验收记录分层

| 层级 | 证据与限制 |
|---|---|
| 网络组件本机测试 | 真实 Caddy + 独立 HTTP/SSE/WS 回显服务；本地测试证书；验证流式、头部、丢响应不重放、重载和回滚。没有公开入口验收含义 |
| OAuth 权限及 Rust 闭环 | 签名 JWT、issuer/audience/scope 校验、席位授予/撤销、两种 Rust 模式、移动和后续位置、多 Agent 通信、操作重试、Gateway 重启后身份恢复 |
| 原有功能回归 | 本机 token/stdio、原生入口、managed 两种模式及榜单、启动器测试 |
| Keycloak 本地协议 | 独立容器中实际完成授权码 + S256 PKCE、真实 JWKS 校验、刷新、授权码不可重用；测试账户使用临时 Realm，结束后删除 |
| GitHub 登录 | 未完成浏览器登录与实际 ChatGPT 回调验收；本地协议测试不替代这一项 |
| 数据备份恢复 | PostgreSQL 自定义归档实际恢复到另一个空测试实例，恢复后的 starbench Realm 已检查；再次恢复到非空库被拒绝 |
| 公网 HTTPS | 本轮不改现役入口；待独立外网验证 STAR 自己的路由 |
| ChatGPT 原生调用 | 待真实工具发现、OAuth、认领/动作/观测及两种模式对局证据；不以 Gateway 已接通 ChatGPT 代替 |

测试时的本机独立 Colima profile 名为 `starbench`；未切换默认 Docker context。其初始 VM 镜像缺少可用 resolv.conf，研发过程中只在此 VM 修复 DNS，并为镜像下载沿用本机已有 HTTP 代理。没有修改 Mac 的系统 DNS 或 Gateway 配置；这些本机修复没有硬编码进 STAR 核心或其他部署实例。

2026-10-15 本地回归：STAR 的 Arena 与启动器回归通过，另已显式启用并通过真实 Keycloak 测试，独立网络项目 5 项通过。Keycloak 测试通过 `STAR_ARENA_IDENTITY_TEST_CONFIG` 指定隔离实例，普通测试默认跳过；没有外部登录行为。

Linux 构建失败后已删除本轮新建的 `starbench` 测试 VM 及其容器数据以释放磁盘，保留 `.arena/deployments/identity-regression/backups/` 中的数据库备份和私密配置。测试容器当前未运行。现役 Mac MCP Gateway、其他项目文件与证书未清理。
