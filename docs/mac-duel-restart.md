# 历史实例：Mac 重启后恢复两个 ChatGPT 插件对战

**首次部署全新 VPS，请阅读[全新 VPS 部署与多客户端对战指南](vps-arena.md)。** 本页记录特定 Mac 实例的恢复过程，其中的路径、账号 ID 和 Tunnel 配置仅适用于该实例。

> **本地研发环境已于 2026-11-06 退役。** 为释放磁盘，Colima 的 `starbench` 实例及其系统盘、数据盘、容器、镜像和数据库均已删除，本机 STARBench 服务和两条 Tunnel 客户端也已停止。源码、部署脚本和私密实例配置仍保留。下文的账号、数据库和席位恢复说明，仅适用于原部署数据仍保留的实例。若要重新使用这台 Mac，应按[自托管初始化流程](self-hosted-implementation.md)重建服务，重新登录取得 subject 并授权；部署到 VPS 时，则按其中的 Linux 流程创建新实例。

**先确认使用方式。** 如果只是在同一台电脑上让两个 AI 客户端对战，按[本机 MCP 指南第 1、2 节](arena.md#local)启动 HUB、Rust ENV 和 MCP 网关即可。下面的四终端流程用于通过 Tunnel 接入的 ChatGPT 网页插件。

这套流程要求 `star-direct` 实例已经配置好 GitHub、Keycloak、HTTPS 和两条 Tunnel，并保留原部署数据。整机重启后，账号、插件配置和比赛记录可以恢复；**战场状态保存在内存中，重新启动 ENV 会创建新局。** 如果只是关闭浏览器或 Tunnel 断线，而 ENV 仍在运行，重新连接后可继续使用原比赛 ID。进行中的比赛不要执行下面的新局流程。

## 使用前先确认

本页以完成安装和配置为前提。管理员在 Mac 终端操作，玩家在 ChatGPT 网页中操作；即使由同一个人完成，也需将内容输入对应位置。HUB 负责消息路由，ENV 运行战场，Arena 提供工具与权限接口。其他名词见[阅读约定](vps-arena.md#reading)。

操作前，先检查 `.arena/deployments/star-direct/deployment.json`、`secrets.json`、`tunnel.json` 和 `second-tunnel/config.json` 是否存在，再用 `colima list` 确认 `starbench` 实例仍保留。还需确认原数据库、域名证书和两条 Tunnel 可用。2026-11-06 退役的实例已不满足这些条件；若配置或数据库丢失，或已更换机器，请先完成初始化，再使用与新实例对应的启动命令。

下文的 `/Users/liyang/Developer/`、`auth.starverse.chat` 和端口号来自这个历史实例。其他运营者应使用自己的实际配置。`subject` 是玩家登录后通过 `get_profile` 取得的 id；重建数据库后，需要重新登录获取。

## 一次性安装和需要保留的东西

这台 Mac 的三个相邻目录是 `star-main`、`star-network`、`GameServer`。首次准备 StarBench 环境时，在 `star-main` 执行：

```sh
uv sync --extra rust-runtime --extra arena
npm ci --prefix rotk_env/rendering/web/client
```

GameServer 使用独立的 Python 环境。Mac 还需安装 Colima、Docker CLI、Docker Compose、star-network 的 Caddy 和官方 tunnel-client。新机器应先按[自托管部署文档](self-hosted-implementation.md)完成初始化、证书和 OAuth 配置；原部署数据完整保留的 Mac，可在重启后从下一节开始。

要保留恢复能力，应保存项目中的私密目录 `.arena/deployments/star-direct/`、Colima 的 `starbench` 实例及其 PostgreSQL 数据卷。两名玩家可共用一个 GitHub OAuth App，但分别使用自己的 GitHub 账号登录。现有 ChatGPT 插件、Tunnel ID、证书和授权历史可以保留；每场新比赛仍需重新授予两个席位。私密目录含有密钥，请勿提交到 Git。

## 重启后的四个终端

在每个终端中先执行 `cd /Users/liyang/Developer/star-main`，并确认 Mac 能连接 OpenAI；如果这台机器依赖网络代理，请先启动代理。然后依次完成下面的步骤。

请打开四个独立的终端窗口或标签页，分别运行对应服务。下文命令使用 zsh，可用 `echo "$SHELL"` 查看 Shell 配置。`$PWD` 表示当前目录，`$cfg`、`$state` 和 `$match_id` 是当前终端中的变量；关闭或更换窗口后，需要重新设置。

| 终端 | 看到什么再继续 | 使用期间 |
|---|---|---|
| 1 · HUB | 在另一终端运行 `curl --fail http://127.0.0.1:18000/health` 返回 ok | 保持运行 |
| 2 · Rust ENV | 输出 HUB 已连接，记下**新比赛 ID**和观战链接 | 保持运行 |
| 3 · MCP 入口 | Caddy 启动成功并持续运行 | 保持运行 |
| 4 · Arena 和 Tunnel | 下方四个健康检查通过，双方插件都能列出新局 | 启动命令执行完即可 |

**终端 1 · 私有 HUB**（保持运行）

```sh
PYTHONPATH="$PWD/../GameServer" ../GameServer/.venv/bin/python -m uvicorn deploy.arena.hub_app:app --host 127.0.0.1 --port 18000 --no-access-log
```

**终端 2 · 新的 Rust 战场**（保持运行）

```sh
match_id="river-split-turn-$(date +%Y%m%d-%H%M%S)"
echo "$match_id"
.venv/bin/python -u -m rotk_env.rendering.web --players ai_vs_ai --scenario river_split --mode turn_based --seed 42 --env-id "$match_id" --hub-url ws://127.0.0.1:18000/ws/metaverse --port 8766
```

复制第一行输出的比赛 ID。看到 `LLMSystem connected` 和 `spectator (read only)` 后，打开本终端新打印的完整观战链接。

**终端 3 · 两个本机 MCP 入口**（保持运行）

```sh
state="$PWD/.arena/deployments/star-direct/tunnel-ports"
mkdir -p -m 700 "$state"
XDG_DATA_HOME="$state/data" XDG_CONFIG_HOME="$state/config" ../star-network/bin/caddy run --adapter caddyfile --config deploy/arena/Caddyfile.tunnel-ports
```

**终端 4 · Arena、认证、两条 Tunnel 和席位**

先将终端 2 输出的比赛 ID 写入实例配置。下面的命令会提示你粘贴 ID，并检查其格式：

```sh
state="$PWD/.arena/deployments/star-direct"
cfg="$state/deployment.json"
read 'match_id?粘贴终端 2 的新比赛 ID，再按回车：'
.venv/bin/python - "$cfg" "$match_id" <<'PY'
import json, re, sys
from pathlib import Path
from deploy.arena.self_hosted import write
path = Path(sys.argv[1])
assert re.fullmatch(r'river-split-turn-\d{8}-\d{6}', sys.argv[2]), '比赛 ID 格式不符'
data = json.loads(path.read_text())
data['attachment'] = {'env_id': sys.argv[2], 'mode': 'turn_based'}
write(path, data)
PY
```

接着启动 Arena、认证服务和两条 Tunnel，让玩家能够登录。新局的席位将在登录后授予：

```sh
.venv/bin/python -m deploy.arena.self_hosted up --config "$cfg" &&
.venv/bin/python -m deploy.arena.self_hosted tunnel-start --config "$cfg" &&
PYTHONPATH="$PWD/../star-network" .venv/bin/python -m star_network.tunnel start --config "$state/second-tunnel/config.json" --state-dir "$state/second-tunnel/state"
```

启动成功后，两名玩家分别在对应的 ChatGPT 应用中登录并调用 `get_profile`，将返回的 id 提供给管理员。管理员在**同一个终端 4**执行以下命令，按提示粘贴实际 id。这里填写的是玩家 id，请勿填入令牌或 GitHub 用户名：

```sh
read 'wei_subject?粘贴魏国玩家的 get_profile.id：'
read 'shu_subject?粘贴蜀国玩家的 get_profile.id：'
```

确认前面的步骤成功后，在终端 4 继续执行以下命令。命令通过 `&&` 连接，前一条成功后才会运行下一条：

```sh
.venv/bin/python -m deploy.arena.self_hosted grant --config "$cfg" --match-id "$match_id" --faction wei --subject "$wei_subject" &&
.venv/bin/python -m deploy.arena.self_hosted grant --config "$cfg" --match-id "$match_id" --faction shu --subject "$shu_subject"
```

`up` 启动 Colima 的 starbench 实例、PostgreSQL、Keycloak、Arena 和 HTTPS 入口。若提示磁盘空间不足，按错误中报告的要求释放空间后重试。若某端口已占用，用 `lsof -nP -iTCP:端口号 -sTCP:LISTEN` 核对是否已经启动。

## 如何确认可以开打

```sh
for url in http://127.0.0.1:18000/health http://127.0.0.1:8781/health http://127.0.0.1:20001/readyz http://127.0.0.1:20002/readyz; do
  curl --noproxy '*' -sS -o /dev/null -w '%{http_code} %{url_effective}\n' "$url"
done
```

四项检查都应返回 HTTP 状态码 200。如果连接失败或返回其他状态码，请先查看对应服务的终端输出，排查后再开始对战。

入口就绪后，在两个 ChatGPT 对话中分别选择魏、蜀插件，发送：“调用 get_profile 和 list_matches，确认能看到比赛 **〈新比赛 ID〉**，只报告身份和比赛状态。” 请将占位文字替换为终端 2 输出的实际比赛 ID。双方都确认进入新局后，先让魏国行动；后续指令也应带上比赛 ID，避免误选历史对局。具体行动方式见[客户端操作](arena.md#connect)。

## 登录页显示 ERR_CONNECTION_CLOSED

点击插件中的“连接另一个账户”后，浏览器会打开 `auth.starverse.chat:10000`。在这个历史实例中，Mac 的 hosts 将该域名解析到 IPv6 回环地址 `::1`，由本机 Caddy 在 10000 端口接收 HTTPS 请求。如果浏览器通过系统代理访问，连接目标会由代理处理，可能无法按本机 hosts 映射返回 Caddy。当时的测试中，这条代理路径在 TLS 握手阶段断开。

当时的处理方式是在 Wi-Fi 代理例外中加入 `auth.starverse.chat`，让浏览器直接访问本机 Caddy，再由 Caddy 将登录请求转给 Keycloak。ChatGPT 和 GitHub 仍可通过代理访问。如果代理软件重启后覆盖了例外设置，可用以下命令检查本机解析、代理配置和直连结果：

```sh
dscacheutil -q host -a name auth.starverse.chat
scutil --proxy
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' https://auth.starverse.chat:10000/auth/realms/starbench/.well-known/openid-configuration
```

域名应解析到 `::1`，最后一条命令应返回 200。若直连成功、浏览器仍报错，请检查当前网络服务或代理软件的绕过列表：保留已有条目，添加精确域名 `auth.starverse.chat`，再从插件重新发起授权。浏览器完成登录后，模型的 MCP 调用仍通过各自的 Tunnel 传递。
