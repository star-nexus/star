# 多渲染器接入

2026-10-11，在 `codex/render-adapters` 实现。沿用[已确认的顶层设计](architecture/renderers/proposed.html)：服务端 Rust 执行权威规则，pygame / Three.js 读取展示投影。浏览器不运行 Rust/WASM。

当前 Web 视觉版本为 `starbench-web-v3`。v3 默认显示 FPS，并补齐内核与渲染器的依赖边界；[验收及视觉记录](render-adapters-v3/README.md)包含默认角标、窄屏和依赖检查证据。v2 的单位插值、GPU 对象和侧栏复用继续保留；[性能记录](render-adapters-v2/README.md)包含修复前后对照。pygame 仍为 `starbench-ui-v6`。

## 启动

从仓库根目录执行，首次安装 Web 素材依赖需要 Node/npm：

```bash
npm ci --prefix rotk_env/rendering/web/client
uv run starbench.py --renderer web --no-hub --scenario chibi-small --seed 42
```

打开终端打印的魏、蜀或旁观链接。默认两个人类槽位，分别使用对应链接，两个页面共享同一 Rust 对局。链接中的凭据绑定服务端视角，每次启动重新生成，使用 URL fragment 而不进入 HTTP 请求路径。普通启动仍为 pygame：`uv run starbench.py --no-hub`。

Web 的场景准备、Rust 宿主、展示投影和 Hub 路径都不导入 pygame，也不初始化字体或 SDL。pygame 是可选依赖；启动器只在选择桌面渲染时请求 `pygame` extra，Web 只请求 `native` extra。桌面路径不加载 Web 服务、Web 投影或 Three.js 素材。Web 入口无需隐藏任何 pygame 提示。启动器清除外层 PEP 723 临时环境的 `VIRTUAL_ENV` 后执行内层 uv，让它选择仓库 `.venv`，避免环境不匹配警告。独立无 pygame 环境及双向导入隔离的证据见[依赖隔离记录](render-adapters-isolation/README.md)。

更新后停止旧服务，重新运行命令，再刷新网页。已有的 Web 会话凭据会随服务重启失效，需要使用新链接。默认在地图左下角显示小型绿色 FPS 角标，窄屏移到地图右上侧；角标不接收鼠标事件。FPS 按浏览器完成的绘制帧计数，约每秒更新，从后台返回页面后重新采样，与 Rust 60Hz 时钟、展示状态 20Hz 分别计量。默认不采集详细诊断数组。

诊断时在链接的 `#token=...` 前加 `?perf=1`，例如 `http://127.0.0.1:8765/?perf=1#token=...`；角标额外显示状态更新频率与绘制调用数，保留本地 p95 等详细采样。这些指标仅在本地显示，不发送到外部。

Web 的 Hub 接入使用原来的宿主与 SDK：

```bash
uv run starbench.py --renderer web --players human_vs_ai --hub-url ws://localhost:8000/ws/metaverse --env-id env_1
uv run starbench.py --renderer web --players three_kingdoms --mode real_time --hub-url ws://localhost:8000/ws/metaverse --env-id env_1
```

Agent 继续通过原来的 Hub 注册、认领单位、提交动作及读取观测；AI 槽位的浏览器链接只读。Web 默认离线；显式 `--hub-url` 或 `STAR_HUB_URL` 接入，`--no-hub` 优先。没有自动 BOT。Web 参数与桌面参数分别由各自入口校验；Web 不支持 `--headless`、`--mock-ai`、`--native-scheduling serial` 等桌面选项。

浏览器操作：点击己方部队选择，再点击地格移动；`M/A` 切换移动/攻击目标，按钮提供待命、驻扎、占领和筑垒；`1` 步兵、`2` 骑兵、`3/4/5` 弓兵；`Space` 与“结束回合”按钮共用同一个命令函数。滚轮缩放、拖动平移、`F` 适应地图，窗口调整后重新计算正交相机范围。

## 目录与职责

四个产品层的顶层目录保持原样。RoTK 专属数据和 Web 服务都在 ENV 内，没有新建顶层前端项目。

```text
framework/presentation/
  contracts.py                 RendererAdapter / FrameProvider 通用契约
  capture.py                   显式截图回调；缺失能力时返回无图像错误
  stream.py                    可丢弃展示状态的一槽邮箱
rotk_env/rendering/
  __init__.py                  注册与延迟加载适配器
  adapters.py                  none / web 适配器与可选截图能力
  pygame_adapter.py            原桌面渲染、输入与 UI 挂载
  pygame/animation.py          pygame 字体、Surface 与伤害数字绘制
  pygame/controls.py           pygame 键码到通用动作的转换
  pygame/display.py            pygame 窗口尺寸读取
  pygame/frame_capture.py      桌面与 dummy 窗口的 FrameProvider
  projection.py                RoTK 展示模型、视野过滤与视角增量
  commands.py                  服务端视角授权与人类命令校验
  web/
    __main__.py                Web 对局入口
    server.py                  HTTP 素材与 WebSocket 展示宿主
    client/                    Three.js、HTML/CSS、显示状态、npm 锁文件
      tests/                   浏览器状态与坐标单元测试
rotk_env/runtime/              原有 Rust/PyO3 宿主、权威调度、Hub、生命周期
rotk_env/prefabs/              场景初始化及模拟策略选择
  controls.py                  通用键名、动作及帮助文案，不导入引擎
rotk_env/ui/start_layout.py    pygame 菜单字体测量与点击矩形
rotk_env/systems/
  animation_lifecycle.py       无引擎依赖的轨迹与生命周期
  interactive_animation_lifecycle.py  interactive 浮动文字轨迹
  animation_system.py          原 pygame 系统导入路径的兼容入口
  window_animation_system.py  interactive 生命周期与 pygame 绘制组合
  ...                         原有规则系统与性能路径
rotk_env/components/           原有组件
rotk_env/maps/                 原有地图
docs/render-adapters-v1/       初版历史记录与可复用桌面对照脚本
docs/render-adapters-v2/       移动/对象复用修复证据、视觉版本、截图
docs/render-adapters-v3/       默认 FPS、渲染边界补查与视觉记录
docs/render-adapters-isolation/  依赖隔离、桌面像素对照与验收记录
```

`node_modules` 和 `.archify` 作者工具中间文件忽略；固定设计图保存在 `docs/architecture/renderers/`。

```mermaid
flowchart LR
  Agent[原有 Agent SDK] <--> Hub[star-protocol / Hub]
  Hub <--> Host[NativeHubHost]
  Host <--> Authority[单一 AuthorityRuntime]
  BrowserInput[浏览器人类输入] --> Grant[服务端授权与校验]
  Grant --> Authority
  DesktopInput[桌面人类输入] --> Authority
  Authority <--> Rust[Rust ECS / RoTK 规则]
  Rust --> Delta[拥有独立数据的原始展示增量]
  Delta --> World[展示 World]
  World --> Pygame[pygame 适配器]
  Delta --> Model[RoTK 展示模型]
  Model --> View[按授权视角过滤]
  View --> Stream[快照 / 增量 / 重同步]
  Stream --> Three[Three.js 浏览器]
  Capture[独立 FrameProvider] --> Host
```

图中的 pygame 与 Web 是可选宿主配置；每个 `NativeSession` 安装一个展示适配器。Web 宿主可以给多个浏览器分发不同视角，它们共享一个权威世界。原始 native 增量和未过滤事件不直接发给浏览器。

## 规则、性能路径与截图边界

`simulation_profile` 从实际绘制模式中分离。默认桌面仍使用原有 interactive 路径，原有 none/dummy/headless 默认保持参考路径。Web 无 SDL 窗口，但选择 interactive：复用空间索引、窗口版本 Vision / Movement / Combat / ResourceRecovery / Statistics / Realtime 的初始化，以及权威移动与视觉生命周期。

API18/schema5 内部的历史 `display="window"` 字段仍表示这套 native 策略。Web 的实际准备必须使用 `display="none"`；它既不创建 pygame 窗口，也不导入 pygame。没有修改 Rust 源码或重编译二进制，已有原生优化开关和默认 worker=1 保留。Python 仍进行一次纯数据场景准备，之后卸载所有 Python 模拟系统，Rust 独占规则推进。通用动画轨迹和生命周期位于 `systems/`，pygame 字体和绘制位于 `rendering/pygame/`。Web 宿主从磁盘传送共享 PNG 素材，浏览器解码；场景初始化不加载字体或构造 Surface。

展示适配器只执行 `apply / render / close`，不能推进权威时钟。`FrameProvider` 独立注入会话，在原来的发布与截图围栏上调用。选中 pygame 的会话安装 `PygameFrameProvider`；桌面入口的历史 headless/dummy 路径也显式安装它。pygame 截图沿用原字节、视角、错误和格式标签；历史格式问题不在本次更改中修正。

底层 `RustRuntime`、`AuthorityRuntime` 和 Python `LLMActionHandler` 不再默认导入 `RenderEngine` 或 pygame 来补齐截图。直接调用这些 API 的宿主如需图像，显式传入 `frame_capture` 回调；`NativeSession` 从其 `FrameProvider` 注入。未配置提供器时，成功的 VLM 请求保留结构化状态，返回 `frame_base64=None`、`frame_format=None` 与 `frame_error="No Agent observation frame provider configured"`。规则、star-protocol、Hub 和 Agent 的动作接口保持原样。

Web 不提供 Agent 的图像观测。`get_faction_state_vlm` 返回原有无图像错误字段，不回退到旧窗口或未授权浏览器画面。浏览器截图仅是人工验证证据。要让 Web 对局支持 VLM，后续需要独立可信离屏 FrameProvider，并单独记录其视觉版本及验收结果。

## 引擎依赖检查

组件定义、通用动作/快捷键、配置、ECS、协议、规则系统和权威 runtime 不承担窗口、字体、键码或截图实现。菜单字体测量和 `pygame.Rect` 从 `components/start_menu.py` 移到 `ui/start_layout.py`；窗口读取从 `GameConfig` 移到 pygame 适配器，配置只接收 `set_viewport_size(width, height)`；pygame 键码在输入适配器中转换为通用键名。运行身份的视觉版本由选中的宿主传入，内核默认 `none`。

`test_renderer_boundaries.py` 作为回归门禁，检查受保护模块的直接、间接以及函数内部导入，阻止其到达具体引擎、UI 和渲染实现；检查 Rust 依赖锁没有图形引擎；在新进程中拒绝图形导入，执行场景准备、原生和 Python 成功 VLM 请求、会话关闭。场景构建器和 `NativeSession` 是选择渲染器的组装入口，可以按所选分支导入桌面实现；它们的 none/Web 分支由运行时拒绝导入检查覆盖。历史桌面系统保留原路径作为明确列出的展示叶节点，新规则模块默认受静态保护，新引擎实现应放在 `rendering/`。

无 pygame 的独立环境还验证 Web 素材、WebSocket、结束回合恢复 AP、原有 Hub 路径与 VLM 无截图回退。桌面独立进程反向拒绝导入 Web 服务、投影和 Three.js 素材。

## 展示传输与人类输入

展示包是 ENV 私有的 schema1，和 star-protocol 分开。首包包含场景、完整授权单位、地格、HUD、视觉提示；后续为相同视角的差分。`epoch / revision / tick / entity id` 为十进制字符串，避免 JavaScript 舍入 Rust u64。`sequence / base_sequence` 串接显示包；断线重连、增量缺口或请求 `resync` 使用完整快照重建。

阵营视角保留己方部队，仅包含可见敌军；敌军 AP/MP 不发送。未探索地格不发送地形或资源地址。已探索地格只保留最后看见的领土状态，视野外新占领不会泄露。桌面的 Fog 绘制开关不扩大浏览器授权。旁观凭据可查看全图，但不能下命令。

服务端解析白名单人类命令，在权威线程同一次接纳内发布最新权限事实、核验阵营、存活单位、当前回合、目标视野、场景 epoch，然后调用已有 `execute_control / start_capture / finish_human_turn`。按钮与 Space 最终都进入人类 `finish_human_turn`；不会伪造 Agent 注册或绕过 Agent 动作网关。

每连接展示邮箱容量=1，积压时换成完整快照；命令结果单独保留在容量=16 的队列中。最大16个连接、8KiB 入站消息、容量8的接收队列、每秒8个请求（突发12个）、认证5秒、发送超时2秒。慢浏览器发送由异步任务处理，不阻塞权威线程。原有 Agent/Hub 可靠消息不走可丢弃邮箱，也不合并或重放。

Rust 权威时钟仍为60Hz，展示状态默认最多20Hz。v2 在浏览器动画帧之间插值收到的单位/投射物位置，不预测未收到的权威状态；延迟窗口最长100ms，长时间断流与完整重同步直接定位，消失/不可见单位立即移除。拾取、标签和选中圈跟随实际绘制位置。GPU 实例批次复用已有容量，只上传改变的位置/颜色；地格无变化时保留数组与缓冲，攻击线/效果对象按生命周期复用，侧栏节点保留。渲染器仍无游戏规则与时钟推进职责。

第一版覆盖地图、Fog、领土标记、单位、资源、移动/攻击/基本行动、回合、视觉提示、镜头、重连与旁观。行动按现有场景能力启用；没有 TerritorySystem 的对局禁用占领/筑垒，不额外添加规则系统。桌面菜单、小地图、统计详页、结算报告页面暂未搬到 Web。新 Web 路径尚未做5000单位/1000 Agent 的长期容量验收；原有原生测量记录继续有效，不据此宣称浏览器具有相同容量。

## 验证

可复跑的桌面对照：

```bash
uv sync --extra native --extra pygame
PYTHONPATH=. .venv/bin/python docs/render-adapters-v1/check_desktop.py
npm test --prefix rotk_env/rendering/web/client
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest -q \
  framework/tests/test_presentation_stream.py \
  rotk_env/tests/test_renderer_boundaries.py \
  rotk_env/tests/test_renderer_adapters.py rotk_env/tests/test_renderer_dependencies.py \
  rotk_env/tests/test_render_projection.py \
  rotk_env/tests/test_web_commands.py rotk_env/tests/test_web_server.py
```

证据见[v1 初版验收](render-adapters-v1/README.md)、[v2 性能及视觉记录](render-adapters-v2/README.md)、[首次依赖隔离](render-adapters-isolation/README.md)与[v3 FPS 及边界补查](render-adapters-v3/README.md)。v3 桌面 RGB 与观测字节对照相同，pygame 保持 `starbench-ui-v6`；Web 加入默认角标后记录为 `starbench-web-v3`。Git 集成路径：`codex/ui-polish` 的 `c34fd65` 合入 `codex/rust-ecs-parallel`，合并点 `2598697`；`codex/render-adapters` 从该点创建。`main` 未参与这次集成。
