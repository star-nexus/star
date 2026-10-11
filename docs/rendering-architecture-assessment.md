# STAR 渲染架构评估

后续实现：顶层建议已确认，第一版在 `codex/render-adapters` 落地，见
[多渲染器接入与 Web 启动](render-adapters.md)。下文保留评估时的代码快照和判断；
图中的“当前”指评估时现状，不代替后续实现记录。

评估时间：2026-10-11。对象：`codex/ui-polish`，工作目录 `/Users/liyang/.codex/worktrees/rust-ecs-parallel/star-main`，HEAD `65941ef0bc31016bb610591e95ac0ded4ba03ea7`，包含尚未提交的 UI v6 与回合按钮修复。本文件是评估与建议，不代表新增接口已经实现。

## 判断

**可行。现有 Rust 权威内核与 Python 展示投影的分离，已经提供了关键基础；尚未形成可以直接替换 pygame 的跨平台展示接口。**

优先路线是保留服务端 Rust 内核及 Python 宿主，新增只读展示模型与 Web 传输适配，浏览器用 Three.js 绘制。游戏规则、Agent 接入和已有 native 性能优化可以继续复用。浏览器离线运行 Rust/WASM 是另一项部署目标，需要独立验证，不能等同于更换渲染器。

当前图：[Rust / pygame 现状](architecture/renderers/current.html)。建议图：[多展示适配器设计](architecture/renderers/proposed.html)。现状图固定到 HEAD 的证据；本文同时说明工作树中的 UI 修改。建议图描述尚未实现的目标。

## 当前技术架构

四个产品层依然成立，语言变化发生在 ENV 内部。

| 层 | 当前职责 | 与渲染的关系 |
| --- | --- | --- |
| Agent / STARAgents | 策略、模型调用、通过 SDK 注册与提交动作 | 通过已有 ENV 接口取观测；不直接访问 Rust ECS |
| star-protocol / Hub | 身份与消息路由、Envelope、连接、响应、通知与 ACK | 现有 Agent 通道，不是跨平台渲染 API |
| STARBench ENV / RoTK | 场景、规则、动作合法性、视野、统计、宿主、UI | Rust 执行权威规则；Python 仍承担配置、宿主和桌面展示 |
| ECS Framework / STAREngine | 通用世界、时钟、资源及运行框架 | Rust core 提供权威 ECS 基础；旧 Python framework 继续承载展示 World 和 pygame 主循环 |

依据：[README](../README.md)、[联网宿主合同](native-hub-host.md)、[Cargo 工作区](../Cargo.toml)、[Rust Runtime](../native/rotk/src/runtime.rs)。当前只引入 `bevy_ecs` / `bevy_tasks`，没有 Bevy 渲染栈。`star-core` 与 `star-rotk` 没有 PyO3 / pygame 依赖，PyO3 单独放在 `native/python`。

### Rust 与 pygame 实际如何连接

1. `GameScene` 选择后端。当前默认 Rust，Python 保留为显式参考实现。`NativeSession` 调用 Python `build_skirmish_world` 准备场景，导出拥有独立数据的初始 JSON，然后移除准备阶段的 Python 模拟系统和订阅。
2. `RustRuntime` 通过 PyO3 的 `NativeRuntime` 创建 Rust 世界。`AuthorityRuntime` 在专属线程中串行接纳命令、观测与 tick，Rust 拥有权威状态。内部可选读任务并行不意味着多个线程同时随意写世界。
3. Rust `Runtime::presentation()` 导出 changed rows、removed IDs、状态、Fog、HUD、视觉生命周期与事件，以及 `epoch / revision / tick`。PyO3 在持锁期间序列化；Python 得到拥有独立生命周期的结果。
4. `WorldPresentation.apply()` 将结果转为独立 Python 展示组件，检查 epoch 与旧 revision。静态地图、资源和 UI 已经在准备阶段存在，不是每帧从 Rust 导出完整世界。
5. `attach_battlefield_renderers()` 在展示 World 上挂载地图、单位和特效绘制；`NativeSession` 另外挂载 UI、面板、小地图和输入。渲染系统读取这些 Python 组件，提交 pygame 绘制命令。
6. `RenderEngine` 分层、裁剪、批量提交 `Surface.blits`，`GameEngine` 最后调用 `pygame.display.flip()`。它的 screen 类型明确要求 `pygame.Surface`。

定位：[场景入口](../rotk_env/scenes/game_scene.py)、[初始化桥](../rotk_env/runtime/bootstrap.py)、[NativeSession](../rotk_env/runtime/session.py)、[权威执行器](../rotk_env/runtime/authority.py)、[PyO3](../native/python/src/lib.rs)、[展示投影](../rotk_env/runtime/world_presentation.py)、[战场渲染挂载](../rotk_env/runtime/window_presentation.py)、[RenderEngine](../framework/engine/renders.py)。

因此，pygame 不直接驱动 Rust ECS，也不是 Rust 的渲染模块。当前连接点是 **Rust 展示增量 → Python 展示 World → pygame 专用绘制系统**。替换渲染器应围绕展示数据做适配，不能仅把 `pygame.draw` 换成 Three.js 函数。

### 输入与截图也属于接入边界

人类输入通过 `LocalControls` 调用可信本地控制接口；Agent 经 `NativeHubHost` 保留身份、所有权、统计和原响应合同。二者进入同一个权威执行器，但权限与部分业务语义不同。例如人类 `finish_human_turn` 与 Agent `end_turn` 不能为了统一 UI 而无条件合并。最近 Space / End Turn 的问题说明：同一人类操作的键盘和按钮应使用同一命令入口。

VLM 截图由 Python 完成。当前 owner 发布状态后等待显示线程消费并截取画面，后续请求与 tick 不跨该栅栏。截图使用当前 UI 视角，普通遭遇战默认动作名单没有开放 VLM。历史编码仍存在实际 TGA 字节 / `png` 标签差异；本评估不改变它，也不据接口存在推断实验已收到图像。

依据：[LocalControls](../rotk_env/runtime/local_controls.py)、[本地 / Agent 请求区分](../rotk_env/runtime/native.py)、[ENV Hub 宿主](../rotk_env/runtime/hub.py)、[截图栅栏](../rotk_env/runtime/authority.py)、[捕获编码](../framework/engine/frame_capture.py)。

## 已有基础与缺口

| 边界 | 现状 | 对多渲染器的意义 |
| --- | --- | --- |
| 游戏规则与绘制 | Rust 单权威，Python 投影不写回内核 | 可以复用规则、状态转换、观测和已有 native 优化 |
| 展示增量 | 已有 JSON、稳定 ID、删除、epoch、revision、tick | 可作为新展示合同的起点，不必每帧完整导出世界 |
| 展示数据可移植性 | 混合逻辑坐标、像素位置、Python 组件形状；地图依赖初始化 World | 需要明确坐标、静态 baseline、资产键和生命周期，不直接暴露 Python 对象 |
| renderer 抽象 | `RenderEngine` 是 pygame 专用命令队列，含任意 Python 回调与 Surface | 不能把它直接作为浏览器 GPU 的统一命令协议 |
| 多视角与权限 | 内部 delta 无用户视角参数，输出变化单位与多个阵营 Fog | 远程玩家必须经过服务端视角过滤；浏览器遮挡不能代替过滤 |
| 消费与多客户端 | dirty rows 用 `mem::take` 消耗；当前 owner 发布给单个主线程消费者 | 一个发布者消费后分发，客户端不能分别调用破坏式 delta 出口 |
| 慢消费者 | output 容量 8，队列满则等待；现有 UI 必须持续 pump | 不能让慢浏览器的发送或绘制拖住权威模拟，需要有界分发与重同步 |
| 截图 | pygame 全局画面、显示线程及同步 fence | 需独立 FrameProvider；Web UI 可用不代表 VLM 截图合同自动成立 |
| 完全浏览器运行 | PyO3、Python 准备和宿主、native 线程与 unwind 配置仍在 | 增加 WASM 绑定及运行平台适配，并做浏览器验证 |

注意：Rust 视觉对象生命周期目前影响外部 ID 分配。Three.js 可以自行插值和绘制，但不能擅自改变 Rust 的视觉出生、结束或 ID 分配，否则可能影响现有兼容结果。依据：[视觉生命周期](../native/rotk/src/presentation.rs)。

文档有历史段落滞后：`native-runtime.md` 开头写默认 Python、联网待接入，和当前 `GameScene`、README 启动说明、`native-hub-host.md` 冲突。上述判断以代码及较新的联网合同为准；诊断里的历史阶段标签同样不宜当作功能验收结论。

## 建议的接口方向

建议按三条接口分离职责，保留现有 Agent 协议。

**只读展示接口。** 提供静态 `SceneBaseline`，全量 `RenderSnapshot` 和增量 `RenderDelta`。内容包括当前六边形坐标约定与方向、地图语义、单位 ID/类型/阵营/位置/资源、已授权视野、动态领土、视觉对象生命周期、UI 需要的事实。资产通过稳定键索引，字体、Surface、GPU buffer、相机矩阵和屏幕矩形由适配器持有。先用已有 JSON 形状映射，是否改二进制由测量决定。

Web 连接还要有 `scene/epoch`、有序流 sequence、baseline revision 与当前 tick。加入、刷新、断线重连、切换视角或丢失增量时重新建立 baseline。视野变化要产生“新可见 / 不再可见”更新；不能只过滤发生物理变化的单位，否则静止敌军进入视野时会漏显示，离开视野时可能残留。已探索地形、玩家视角和获准的全局观战视角必须分别定义。

当前 delta 包含事件并消耗 dirty 集合。宿主应在有序边界消费一次，维护独立只读投影并向各视角分发，不能随意丢弃中间 delta。慢连接可在确定的 sequence 之后用 snapshot 重建状态；需要保留的事件应另有序处理。分发、序列化、网络等待都要与权威热循环隔离并保持有界内存。

**命令入口。** 桌面和 Web 人类输入提交同一种操作意图，由宿主确认用户身份、阵营/单位控制范围、场景 epoch 和命令顺序。局部选择、相机移动、按钮反馈留在客户端；移动、攻击、占领、结束人类回合交给内核。禁止把受信任的 `execute_control` 直接暴露为任意网页可调用的远程接口。Agent 继续使用原注册、权限和 `execute_host_action`，不为渲染迁移改变动作、计数、错误、通知和重试语义。

**FrameProvider。** 将观测截图与交互窗口解耦：指定获准视角、状态版本、尺寸、画面内容和视觉版本；截图只读，不接纳输入或推进游戏。可以先保留 pygame 作为权威观测截图提供者，同时 Three.js 提供交互画面。若以后用 Web 画面生成 Agent 观测，应单独验证 DOM HUD 是否入图、真实编码、视野、状态一致性、超时与无图行为；不能把不可信远程浏览器回传的画面直接当作实验权威观测。新 provider 需要异步取帧及状态关联设计，避免网络往返时长期冻结 owner。旧截图路径的同步语义先保留。

这些是应用边界和数据合同，不要求 pygame/Python 与 Three.js/TypeScript 共用同一个运行时基类。各适配器可以分别实现 `load baseline / apply delta / render / dispose`，传输与绘制保持独立。若新增公共 Agent 图像格式，另做兼容决策；渲染版本、资产版本和截图配置优先记录到现有运行 manifest，不默认扩展 star-protocol。

## Web 两种路线

| 路线 | Rust 在哪里运行 | 复用范围 | 新工作与限制 | 优先级 |
| --- | --- | --- | --- | --- |
| 服务端 Rust + 浏览器 Three.js | 现有 Python/PyO3 宿主所在服务器 | 现有 native 内核、宿主、Agent 接入与 native 优化 | Web 展示流、权限过滤、基线/重连、浏览器绘制与输入；现有 headless 主循环不自动等于 Web 展示宿主 | 先做 |
| 浏览器 Rust/WASM + Three.js | 浏览器 Worker 中 | 目标是复用 core/rotk 的规则代码 | 新 WASM binding、JSON 初始化来源、时钟与平台依赖、线程/任务池、panic 策略、网络宿主及观测图像路径；尚未进行本仓库 target 编译或浏览器验收 | 有离线需求后再做 |

Three.js 支持 WebGL2 绘制、正交相机以及实例化网格，足以表达当前六边形地形、二维贴图单位和特效。可以先做俯视 2D/2.5D，Web HUD 使用 DOM/CSS；更换它并不要求改成 3D 规则。[WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html)、[OrthographicCamera](https://threejs.org/docs/pages/OrthographicCamera.html)、[InstancedMesh](https://threejs.org/docs/pages/InstancedMesh.html)。GPU 实例化和资源复用是可选实现方式，不构成本项目性能提升的证据。

Rust 可以面向 `wasm32-unknown-unknown`，但该目标的标准文件系统、普通线程等能力受到限制，不能只换编译 target 就继承现有运行方式。[Rust 官方目标说明](https://doc.rust-lang.org/rustc/platform-support/wasm32-unknown-unknown.html)。当前 Cargo 启用 native `multi_threaded`、release `panic=unwind`，读池使用 `bevy_tasks`；需要逐项确认浏览器兼容。WASM 的 Worker / 共享内存并行要满足 Web 平台线程与安全隔离条件。[wasm-bindgen 官方并行示例](https://rustwasm.github.io/docs/wasm-bindgen/examples/raytrace.html)。因此不要把 native 多线程性能直接算到 WASM 上。

## 建议实施顺序与验收

1. **固化现有边界。** 保留 Rust 权威状态与当前绘制结果，抽出只读语义展示合同和人类命令入口。第一步先让 pygame 成为该合同的第一个适配器。避免重写已采用的缓存和批量绘制。
2. **接只读 Web 观战。** 一个有明确授权视角的客户端显示地图、单位、Fog 和 HUD；加入、刷新、重连能恢复。Native 状态、Agent 响应和协议路径保持原行为。
3. **接 Web 人类操作。** 服务端权限检查后调用现有人类命令语义；按钮与快捷键使用同一入口。验证回合制与实时制、资源恢复、无权限操作、旧 epoch 和重连。
4. **补多视角与运行质量。** 验证敌军进入/离开视野、删除/死亡、场景 reset、多个客户端、慢连接和服务端关闭。测量 Rust tick/观测延迟、展示提取/编码成本、消息带宽、浏览器帧时间、GPU/内存。保留原 native worker 默认，不承诺未测量的容量或帧率。
5. **独立处理截图，再评估 WASM。** 只有截图视角、状态版本、尺寸、真实格式和读写边界验收通过，才把 Web renderer 作为观测图像源；有明确离线部署需求后，再单独做 WASM 可编译最小运行时。

共同验收：同 seed、初始场景、命令顺序与受控 dt 下，对照完整权威状态、Agent 响应/错误/顺序、权限和最终报告；重复纯绘制及截图不改变权威状态。新增视觉路径需要记录 renderer ID、`visual_version`、资产/镜头配置，并分别保存基准图。规则一致不意味着 pygame 与 Three.js 像素一致，涉及观测图像的实验应按视觉版本区分。

当前 `runtime_identity()` 已在协议与权威 schema 外记录 `visual_version`；工作树当前为 `starbench-ui-v6`。本次仅增加文档和架构图，没有改变游戏画面，因此不提升游戏视觉版本。

## 评估范围

本次核对了 README、当前联网与窗口渲染文档、Cargo 依赖、场景初始化、Python/PyO3/Rust 接口、展示增量与消费、pygame 渲染队列、人类与 Agent 命令入口、截图栅栏和运行版本。图表执行 schema、源证据与浏览器检查。本次不重新跑容量基准，不声称 WASM 已成功编译，也未实现 Web renderer。
