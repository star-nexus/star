# 同一内核、多渲染器：整体验收

本报告保留首次验收的结果。随后已修复下文的 P1 / P2；当前结论、兼容变化和通过证据见[验收问题修复](../render-adapters-fixes/README.md)。

2026-10-11，评估 `codex/render-adapters` 的 `bcb22ba89bc365b5fe8fab7072d53476bf312f97`。对照[已接受的建议架构](../architecture/renderers/proposed.html)和[原实施验收要求](../rendering-architecture-assessment.md)。用户原 `.archify` 链接与仓库中的建议图字节一致。本轮只新增验收脚本、证据和文档，不修改运行代码、Rust 二进制、协议或视觉版本。

**结论：在线多渲染器的主干和基础功能通过；严格的跨渲染器权威数据一致性暂不通过。** 游戏可以继续使用，已有原生规则和性能路径保留；目前不能签署“展示数据彻底排除在权威初始化之外、仅更换 renderer 后完整状态与 Agent 响应相同”的完整验收。

## 设计落实与验收矩阵

| 建议设计 | 实际实现与证据 | 结果 |
| --- | --- | --- |
| 服务端单一 Rust 内核 | `NativeSession → AuthorityRuntime → RustRuntime`；Rust、protocol、Agent 源文件相对集成基线 `2598697` 无变化，API18/schema5 和 native 二进制哈希不变 | 通过 |
| 可替换展示适配器 | `framework/presentation/contracts.py` 的 `RendererAdapter`；ENV 的 `register_renderer/create_renderer` 延迟加载 pygame、web、none，并有第三方 Recorder 的接入/关闭测试 | 通过 |
| 引擎依赖不进入规则/初始化 | 静态直接、间接、函数内导入门禁；未安装 pygame 的环境完成 Web 宿主、HTTP/WebSocket、Hub、范围和 VLM 无回退检查；pygame 拒绝 Web 模块导入仍可绘制/截图 | 引擎代码隔离通过；UI 初始化数据隔离见 P1 |
| 只读展示和视角权限 | 原始 native 增量仅由宿主有序消费；Web 投影过滤隐藏单位、敌军 AP/MP、未探索地形和视野外领土变化；ID/epoch/revision/tick 使用十进制字符串 | 通过 |
| 快照/增量/重同步/慢连接 | schema1；sequence/base_sequence；连接重建完整快照；一槽展示邮箱、独立命令回复队列，发送停滞时 native 时钟继续运行 | 通过，当前小规模测试范围 |
| 人类命令网关 | 凭据绑定阵营/控制能力；owner 同一次接纳校验 epoch、存活单位、回合和目标视野；Space/按钮共用人类结束回合入口并恢复 AP | 通过 |
| 保留 Agent 接入 | 原 `NativeHubHost` 与 SDK/协议通道继续工作；浏览器不伪造 Agent、不改变 Agent 权限或记账；完整 protocol/Agent 回归通过 | 接入通过；跨 renderer 查询中的实体 ID 仍不同 |
| 只读绘制和规则一致性 | none/web 完整权威状态及 Agent 响应一致；三适配器绘制不修改权威状态；两模式操作序列后的单位组件一致 | 严格三适配器完整比较失败，见 P1 |
| 独立 FrameProvider | 可注入独立提供器，保留状态发布/截图围栏；pygame 像素与观测字节对照一致；Web 明确返回无图像能力错误，不加载旧引擎回退 | 最小能力边界通过；Web 图像观测和遗留格式问题未完成 |
| 目录与视觉记录 | 通用展示契约在 framework，RoTK 投影/网关/适配器/Web 客户端在 ENV；顶层四层不变；Web v1–v4 和 pygame ui-v6 有对应记录 | 通过 |

## P1：桌面 UI 初始化数据进入 native，并改变权威 ID

同 seed=42、chibi-small、两个 human 槽位、interactive 策略，分别运行 none、pygame、web。冻结时间，执行相同移动、受控 dt、待命、回合切换（回合制）、Agent 注册、查询与错误请求。回合制9个检查点、实时制7个检查点均得到相同结论，见 [rules-comparison.json](rules-comparison.json)：

| 初始权威数据 | none | Web | pygame |
| --- | --- | --- | --- |
| `entity_counter` | 237 | 237 | 241 |
| `wei_infantry_1` 的 ID | 227 | 227 | 231 |
| native 中的 `UIButton` 实体 | 0 | 0 | 4（225–228） |

四个按钮分别为 `end_turn / show_settings / toggle_help / toggle_stats`。它们先于玩家/单位创建，占用同一个 ID 分配器；[`bootstrap.py`](../../rotk_env/runtime/bootstrap.py) 的 `PRESENTATION` 排除列表没有 `UIButton`，`export_initial_state()` 还保留空实体 ID 和原 `entity_counter`，因此只过滤按钮组件也不足以消除 ID 偏移。

这属于历史桌面路径尚未拆净的初始化边界，并不是重新导入 pygame 的回归。此次序列按单位名称比较全部单位组件，移动/AP/MP/状态等相同；none/web 完整状态与响应逐项一致。三者的 Agent 注册响应和未知动作错误相同，但 `get_faction_state` 的五个己方 `unit_id` 不同。因而不能将“规则表现一致”写成“整个权威世界与 Agent 查询字节一致”。新旧桌面自身的像素与截图字节仍相同。

修复方向是先准备独立的规则场景和权威 ID，再为 pygame 展示 World 创建 UI；UI 使用独立 ID 空间并完全不进入 native 初始数据。现有桌面单位 ID 属于已发布 Agent 观测，改变分配顺序需要单独记录兼容影响。下一轮应复跑本对照，确认四个 UIButton 消失、完整权威状态/Agent 响应一致，再复核旧桌面与截图合同。此次评估不擅自改变既有 ID。

## 其他明确限制

- **既有截图编码标签差异仍在（P2）。** 本次真实捕获经图像解码确认是 TGA，`frame_format` 标签仍为 `png`，详见 [frame-encoding.json](frame-encoding.json)。本轮为保持合同延续旧字节，没有修正。正式图像观测验收应独立解决格式及兼容迁移；不能把当前能力描述成已验证 PNG 观测。
- **Web 图像观测尚未提供。** 可玩页面不等于可信 Agent 截图源。带明确 tick/视角/资产/尺寸/视觉版本的离屏 FrameProvider、超时与无图行为仍需专项实现和验收。
- **浏览器容量没有继承性结论。** native 二进制、默认 worker=1 和优化路径保持，但 Web 投影、编码、带宽、GPU/内存及多客户端成本是新开销。前一轮同提交的小地图20个采样窗口为99.9–100.0次绘制循环/秒，不能证明5000单位/1000 Agent 或 GPU 呈现容量。
- **UI 功能覆盖与部署范围有限。** Web 已覆盖战场及基本人类操作；桌面菜单、小地图、统计详情、结算页面、完整回放产品均未迁移。none 是无画面消费适配器，不是完整回放器。浏览器 Rust/WASM/离线已按用户要求延后，公网部署和长期负载另行验收。
- **保留历史策略名称。** API18 中 `display="window"` 仍代表 interactive native 策略，而 Web 实际没有窗口。`simulation_profile` 已分离图形准备，但内部旧字段尚未重命名；这不引入引擎依赖。

## 本轮实际执行

| 检查 | 结果 |
| --- | --- |
| framework / protocol / ENV / Agent 全套 Python 回归，SDL dummy | **2788 passed，136.39s，无跳过** |
| Web 前端状态、几何、插值、批次、范围、FPS 单元测试 | **17 passed，无跳过** |
| 未安装 pygame 的 Web 范围、HTTP/WebSocket、架构边界测试 | **16 passed，3.93s，无跳过** |
| 无 pygame 的 Web 依赖探针：Hub、结束回合 AP、VLM 无回退、关闭 | 通过，[web-dependencies.json](web-dependencies.json) |
| pygame 反向隔离、绘制不写权威、截图 | 通过，[pygame-dependencies.json](pygame-dependencies.json) |
| 与合并后的 Rust 主线基线 `2598697` 比较桌面像素/观测字节 | 一致，[desktop-parity.json](desktop-parity.json) |
| none / pygame / web，两模式受控命令与完整数据对照 | **严格比较失败，脚本 exit=1；P1 已复现** |
| native 二进制、Rust/protocol/Agent 源文件与集成引用 | 保持，详见 [validation.json](validation.json) |

完整机器记录见 [validation.json](validation.json)。Web v4 人工点击、M/A/Esc、移动/攻击叠层和窄屏证据沿用同实现提交的[视觉记录](../render-adapters-v4/README.md)。本轮没有运行外部模型，没有调用付费 API；Hub 通过 fixture 及本地测试验证。

复跑三适配器严格验收（在 P1 修复前预期 exit=1，并写出结构化差异）：

```bash
PYTHONPATH=. .venv/bin/python docs/render-adapters-acceptance/check_rules.py \
  --output /tmp/star-render-rules.json
```

其他复跑命令见 `validation.json`。本轮验收不将分支合并到 `main` 或 Rust 集成主线；pygame 保持 `starbench-ui-v6`，Web 保持 `starbench-web-v4`。
