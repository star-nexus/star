# 渲染引擎依赖隔离

2026-10-11，`codex/render-adapters`，基线 `1fc91c4`。本轮修正共享场景准备和视觉投影对 pygame 的导入，不改变 Rust 规则、star-protocol 或 Agent SDK。

旧路径中，通用 `VisualProjection` 继承的动画系统在模块导入时加载 pygame；Web 的 interactive 场景准备还实例化了带 pygame 字体的动画系统。隐藏欢迎提示没有隔离依赖。

现在轨迹、攻击阶段及生命周期放在 `systems/animation_lifecycle.py`，interactive 浮动文字轨迹放在 `systems/interactive_animation_lifecycle.py`。pygame 字体和伤害数字绘制位于 `rendering/pygame/animation.py`，旧系统路径保留兼容导出与组合。Web 场景只组装纯数据系统；Rust 接收相同初始数据后独占权威执行。Web 宿主只传送共享 PNG 文件，浏览器负责解码和绘制。

pygame 从基础依赖移到可选 extra。Web 启动仅选择 native；桌面及原 headless 入口选择 native + pygame，Python 桌面对照选择 pygame。桌面不加载 Web 服务、Web 投影或 Three.js 文件。通用 RendererAdapter / FrameProvider 契约保持。

## 验收证据

- [Web 依赖检查](web-dependencies.json)：独立环境未安装 pygame，同时设置“导入即失败”的拦截器；场景初始化、indexed 配置、HTTP 素材、WebSocket 命令、End Turn AP 恢复、Hub Agent 注册/观测和关闭全部成功。Hub 使用原 SyncEnvClient 的测试传输，没有请求模型服务。成功 VLM 结果的补全分支调用 Web FrameProvider，返回已有无图像能力错误，不回退到 pygame；普通遭遇战的动作名单保持原样。
- [桌面依赖检查](pygame-dependencies.json)：禁止导入 Web 服务及 Web 投影，桌面初始化、绘制、原观测截图及关闭成功，绘制不推进权威状态。
- [真实启动器](launcher.json)：无 pygame 环境执行用户同一入口，在独立测试端口 8766 启动，HTTP 成功，日志没有 pygame 提示；服务已正常关闭。
- [兼容性](compatibility.json)：25 个通用生命周期方法、10 个 interactive 方法和 pygame 伤害数字绘制的 AST 与父提交相同；Web 完整初始权威状态和魏视角展示快照相同，前端文件未改变。Rust API18/schema5、扩展 SHA256 与上一轮相同。
- [桌面截图](desktop-parity.json)：1200×900 SDL dummy 固定种子对照，RGB 与 Agent 观测字节 SHA256 相同。基线为 UI 集成点 `2598697`；动画与战斗的差分回归另覆盖动态行为。保留 [修改前](pygame-before.png) 与 [修改后](pygame-after.png) 图像。
- [回归结果](validation.json)：Framework、协议、ENV、Agent 和浏览器测试的命令与结果。全量运行同时清理了沿用旧 `1` 迷雾键、旧菜单布局和缺少 World 的测试夹具，实际 UI 行为没有改变。

## 视觉版本

Web 继续使用 `starbench-web-v2`；pygame 观测继续使用 `starbench-ui-v6`。依赖隔离是实现变化：Web 初始展示快照和前端代码相同，桌面 RGB 与观测字节相同，本轮没有新增观测视觉版本。Web 仍无 Agent 图像观测提供器。

## 复现

从仓库根目录执行；Web 素材先通过 `npm ci --prefix rotk_env/rendering/web/client` 安装。

```bash
# 独立 Web 环境：不选择 pygame extra。
UV_PROJECT_ENVIRONMENT=/tmp/star-web-isolation uv sync --extra native --no-dev --locked
/tmp/star-web-isolation/bin/python -m rotk_env.tests.renderer_dependency_probe web

# 桌面和完整开发测试需要显式选择 pygame。
uv sync --extra native --extra pygame
.venv/bin/python -m rotk_env.tests.renderer_dependency_probe pygame
PYTHONPATH=. .venv/bin/python docs/render-adapters-isolation/check_compatibility.py
PYTHONPATH=. .venv/bin/python docs/render-adapters-v1/check_desktop.py --output docs/render-adapters-isolation
.venv/bin/python -m pytest -q framework/tests protocol/tests rotk_env/tests rotk_agent/tests
npm test --prefix rotk_env/rendering/web/client
```

普通启动命令保持 `uv run starbench.py --renderer web --no-hub --seed 42`，用户无需手动选择 extra。
