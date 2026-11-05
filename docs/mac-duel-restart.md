# Mac 重启后，恢复两个 ChatGPT 插件对战

**先选客户端。** 同机的两个 AI 客户端对战，按[本机 MCP 指南第 1、2 节](arena.md#local)启动 HUB、Rust ENV 和本机 MCP 网关即可。下面的四终端流程专用于通过 Tunnel 接入的 ChatGPT 网页插件。


本页用于已经配好 GitHub、Keycloak、HTTPS 和两条 Tunnel 的 `star-direct` 实例。**整机重启后能恢复账号、插件连接配置和比赛记录；Rust ENV 战场在内存里，重新启动 ENV 就是新局。** 如果只是浏览器关闭或 Tunnel 断线，ENV 仍在运行，直接重新连接，继续用原比赛 ID。正在对局时请勿执行下面的新局流程。

## 一次性安装和需要保留的东西

这台 Mac 的三个相邻目录是 `star-main`、`star-network`、`GameServer`。首次准备 StarBench 环境时，在 `star-main` 执行：

```sh
uv sync --extra rust-runtime --extra arena
npm ci --prefix rotk_env/rendering/web/client
```

GameServer 使用自己的 Python 环境。Mac 还需准备 Colima、Docker CLI、Docker Compose、star-network 的 Caddy 和官方 tunnel-client。新机器从[自托管部署文档](self-hosted-implementation.md)的初始化、证书和 OAuth 配置开始。这台已配置的 Mac 重启后直接从下节开始。

保留项目里的私密目录 `.arena/deployments/star-direct/`、Colima 的 `starbench` 实例及其 PostgreSQL 数据卷。两个 GitHub 玩家共用同一个 GitHub OAuth App。ChatGPT 插件、Tunnel ID、证书和席位授权记录均可复用；新比赛需要重新授予两个席位。私密目录含密钥，请勿提交 Git。

## 重启后的四个终端

每个终端先执行 `cd /Users/liyang/Developer/star-main`。先启动日常使用的网络代理，让 tunnel-client 能从 Mac 连接 OpenAI。以下按顺序执行。

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

先把终端 2 的比赛 ID 写入实例配置。下面命令会提示粘贴，并检查格式。

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

以下命令适用于本机默认 zsh。上一段成功后执行；每条成功后才会运行下一条：

```sh
.venv/bin/python -m deploy.arena.self_hosted up --config "$cfg" &&
.venv/bin/python -m deploy.arena.self_hosted grant --config "$cfg" --match-id "$match_id" --faction wei --subject 0f26a2e4-f698-45fd-ab31-34aec6f4e23f &&
.venv/bin/python -m deploy.arena.self_hosted grant --config "$cfg" --match-id "$match_id" --faction shu --subject b84e76cd-1e12-4189-b241-2f3dd61dbbb0 &&
.venv/bin/python -m deploy.arena.self_hosted tunnel-start --config "$cfg" &&
PYTHONPATH="$PWD/../star-network" .venv/bin/python -m star_network.tunnel start --config "$state/second-tunnel/config.json" --state-dir "$state/second-tunnel/state"
```

`up` 启动 Colima 的 starbench 实例、PostgreSQL、Keycloak、Arena 和 HTTPS 入口。若提示磁盘空间不足，按错误中报告的要求释放空间后重试。若某端口已占用，用 `lsof -nP -iTCP:端口号 -sTCP:LISTEN` 核对是否已经启动。

## 如何确认可以开打

```sh
for url in http://127.0.0.1:18000/health http://127.0.0.1:8781/health http://127.0.0.1:20001/readyz http://127.0.0.1:20002/readyz; do
  curl --noproxy '*' -sS -o /dev/null -w '%{http_code} %{url_effective}\n' "$url"
done
```

四项都应返回 200。在两个 ChatGPT 对话分别选择魏、蜀插件，发送“调用 get_profile 和 list_matches，确认能看到比赛 **〈新比赛 ID〉**，只报告身份和比赛状态”。双方都看到新局后，先让魏国行动。随后的指令都带新比赛 ID，以免选中历史对局。

## 登录页显示 ERR_CONNECTION_CLOSED

点击插件的“连接另一个账户”时，**浏览器**会打开 `auth.starverse.chat:10000`。在这台 Mac 上，hosts 将这个名字解析到 IPv6 回环地址 `::1`，本机 Caddy 在 10000 端口接收 HTTPS。如果浏览器把连接交给系统代理，目标地址由代理处理，浏览器自己的 hosts 映射不能保证它连回本机。实测该代理路径在 TLS 握手时断开。

Mac 已在 Wi-Fi 的代理例外中加入 `auth.starverse.chat`。这样浏览器使用本机解析，Caddy 提供与该域名匹配的证书，并把登录请求转给 Keycloak。ChatGPT 和 GitHub 仍可使用代理。若代理软件重启后覆盖例外，可这样区分两条路径：

```sh
dscacheutil -q host -a name auth.starverse.chat
scutil --proxy
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' https://auth.starverse.chat:10000/auth/realms/starbench/.well-known/openid-configuration
```

本机应解析到 `::1`，最后应返回 200。若直连成功而浏览器报错，检查当前网络服务或代理软件的绕过列表，保留已有条目并添加精确域名 `auth.starverse.chat`，再从插件重新发起授权。网页完成登录后，模型调用 MCP 走各自的 Tunnel。
