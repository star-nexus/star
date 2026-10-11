# STARBench ENV

六边形战场支持回合制和即时制，可使用桌面窗口或浏览器，也可无窗口运行 Agent 对局。

- [游戏规则与操作](../docs/game-rules.md)：兵种、资源、移动、攻击、地形、迷雾和胜负。
- [启动与 Agent 接入](../docs/integration.md)：安装、桌面／Web、Hub、自定义 Agent 和评测。
- [Agent 协议](../docs/agent-protocol.md)、[观测字段](../docs/observation-affordance.md)、[消息格式](../docs/hub-envelope.md)：接入参考。

从仓库根目录启动：

```bash
# 离线桌面体验，无模型调用；AI 槽不会自动行动
uv run starbench.py --no-hub

# 浏览器体验，先安装前端依赖
npm ci --prefix rotk_env/rendering/web/client
uv run starbench.py --renderer web --no-hub

# 启动参数
uv run starbench.py --help
```

默认使用 Rust。联网对局需要先启动 GameServer，并让 ENV 和 Agent 使用相同的
Hub 地址与 `env_id`。`--headless` 关闭桌面窗口；`--no-hub` 关闭联网。
本地规则 BOT 仅在显式选择 Python 后端并启用 `--mock-ai` 时运行。
