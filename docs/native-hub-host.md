# 正式联网 Benchmark 的 Rust ENV

RoTK 的窗口、headless、`run_env.sh`、`run_headless_env.sh` 和 `auto_test.py` 默认 Rust。显式 `--backend python` 保留原 ENV 对照与本地规则 BOT。此默认改变只在本研究分支，尚未合并 main。

STAR 仍严格分为 **ECS Framework、star-protocol、STARBench ENV、Agent**。Python/Rust 是 ENV 内部实现；GameServer、协议和 Agent 源码保持。仍使用原 Envelope、`env_id`、`agent_id`、注册与阵营/单位权限。参与者不必更换 SDK、动作、响应解析或策略。

## 启动

先按根 README 启动现有 Hub。统一启动器自动准备 ENV 依赖；首次源码构建需要 Rust 工具链，uv 管理 Python 3.13。缺失/规则/API/宿主能力不匹配会明确失败，不静默回退。

```bash
uv run starbench.py
# 菜单选择 External Agent / Hub

./run_headless_env.sh --players three_kingdoms --mode real_time
uv run python auto_test.py --mode real_time --players ai_vs_ai --list provider.txt

# 显式 Python 对照或离线 BOT
uv run starbench.py --backend python --no-hub --mock-ai --skip-start
```

Hub 地址、Agent 启动及身份方式沿用原设置；`--no-hub` 只表示明确离线。Rust 的 External Agent / Hub 已开放，本地 BOT 与 scale-harness 暂仍需 Python。静态 AI 槽不会自行行动。

`starbench.py` 是纯标准库启动器（PEP 723 无依赖脚本），帮助不加载 pygame 或 Rust。它在仓库根目录调用原 ENV 入口，Rust 时由内部 `uv run --extra native` 准备扩展，显式 Python 时不请求 native extra；参数、退出状态和 ENV 默认配置保持。POSIX 用 exec 保留信号语义，Windows 用子进程路径。原 ENV/Shell 入口继续支持；构建排障时可显式使用 `uv sync --extra native`。

native 默认 1 线程，`--native-threads 2|4` 可选。`--native-scheduling threaded` 默认采用独立固定时钟；serial 保留帧驱动，但联网请求仍进入同一个权威执行器。

## 所有权及兼容合同

先准备世界、Rust 实例和展示系统，再连接 Hub。网络回调深拷贝已收到的请求，进入有界宿主队列（32）；单个宿主线程复用原 `LLMSystem` 的解析、Envelope 包装和冷却政策，把世界操作交给 `AuthorityRuntime`。网络发送/ACK/重试不访问展示 World，也不占用 Rust owner 等待发送。权威 inbox32、展示 output8 仍使用背压，无丢弃、覆盖或新错误码。

单条消息先执行动作，再发送原响应，发送成功后提交动作计数，最后提交消息计数。批量消息先记消息计数，按原序执行和计数，再发送原批量响应。发送失败不回滚已完成动作；ACK/缺动作名的早返回及其发送错误前缀沿用 Python。仅连续、可编码的 `get_faction_state` 项交给已有 `ObservationBatch`；写操作、结束回合及截图保持边界。没有等待聚合独立消息。

回合通知、8 秒重试、最多 5 次重试、ACK 或其他动作取消、结束通知、允许的统计上报及完整 60 秒结算等待保留。最终报告从一次 Rust 权威快照生成，主线程仅安装独立报告和 HUD 事实。退出先停止接纳，排完已接纳消息并完成截图栅栏，再关闭网络、join 权威并释放展示；故障不替换为 Python 世界。

VLM 在原权限允许的场景里沿用当前 UI 视角及历史编码/标签。owner 发布有序增量并等待显示线程截图，后续操作不跨截图屏障。普通遭遇战原本不开放 `get_faction_state_vlm`，本次不改变名单。全尺寸图像验收使用现有 VLM 能力夹具及测试参与者的 16MiB 接收预算；SDK 的默认接收上限可能拒绝超过 1MiB 的旧格式响应，该既有参与者传输配置问题不在本轮修改。没有修正历史 `frame_format=png` / 实际 TGA 字节差异。

## 运行身份

世界准备与 Hub 确认后打印 `STAR_ENV_READY <JSON>`；批量启动器只认可匹配 backend 且 `hub_connected=true` 的记录，再启动 Agent。`--runtime-manifest PATH` 可将同一记录写入本地文件。每局批量运行写 `logs/run_<pid>/match_<n>_runtime.json`。字段包括 backend、源码 SHA、实际扩展 SHA256、API/schema、oracle、seed、调度和视觉版本；profiler 也记录这些身份。均不进入协议或权威 schema。

native 构建缓存跟踪 bindings、两个相邻 Rust crate、Cargo manifests/lock 和 Python 包输入，避免更改 Rust 源码后重复使用旧编译扩展。

## 本轮验收范围

4 次现有 Hub 无界面对照覆盖 Python/Rust × 两种模式；同初始输入的逐步完整权威状态、响应、动作/消息计数及最终报告相同。测试生命周期夹具只在验收工具中设置结束状态并推进可控墙钟，实际实现的 60 秒门槛没有缩短。

2 次 Rust Cocoa 实际窗口覆盖人类选中、帮助、迷雾、缩放窗口、联网移动、允许/拒绝 VLM 和关闭。双 ENV 测试覆盖不同 env_id 的注册/状态、现有 Agent 间消息和一个 ENV 退出后另一实例继续请求。5000 Units + 1000 实际 AgentClient WebSocket 合成参与者做一次 10 秒预热 + 30 秒运行，核对有界队列、世界时钟、完整请求计数和采用优化的实际使用。

这属于有限接入验收，不代表完整新性能矩阵、付费 LLM 评测、多轮容量结论或 5000 Agents 验收。源/wheel、raw、校验链及启动重现见 [Lab 包](../../star-lab/experiments/2026-10-rust-hub-adoption/README.md)。G009 在上述普通联网宿主范围关闭；G008、R001/R002 和其他未决项保留。
