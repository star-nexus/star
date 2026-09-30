# E3：其他 System 内部并行候选（2026-10-01）

研究完成。当前 5000 Units＋1000 Agents 规范负载下，**尚无足够证据启用另一项 System 内部并行**。保留 E2 Statistics 策略：当前批次 JSON 记录构建、128 行门槛、显式 2／4 线程、原序提交；默认 1 不变。System 之间仍顺序执行。5000 Agents 暂缓。

进度：`边界审计 █ | 分项归因 █ | 完整等价 █ | 成本/条件排序 █ | canonical归档 █`。
[Lab 正式报告](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-internal-system-candidates/README.md)提供原始计时、wheel、源码 bundle、复算入口和完整命令。

## 成本与候选表

下表为同一录制输入的 **诊断路径**，含预热，共 9880 tick。数字是 1 线程配置的每 tick 均值；System 内部加入计时会扰动耗时，不能当作普通 step 性能或并行收益。2／4 配置用于完整等价与成本分布复核，其他 System 并没有在这些配置中新增并行。

| System | 整阶段诊断均值 µs | 候选计算及预算 µs/tick | 判断与重访条件 |
|---|---:|---|---|
| Vision | 43.504 | 未缓存几何 0.553；原序提交 28.169 | 条件优先：大量独立冷缓存键或更大合法视距；当前几何只占 1.27%，先关注提交/表示成本 |
| Movement | 31.049 | 去掉空间索引与 dirty 写入的行处理乐观上界 5.359；其中 pixel 0.091 | 条件候选：更多同时移动单位；当前平均 122.47、峰值 186，不是 5000 全移动 |
| Visuals | 9.315 | 四阶段行循环上界 8.135；damage 循环 6.843 | 条件候选：大批同阶段浮字/效果；当前 damage 平均 6.66、峰值 28；逐阶段单独判断 |
| Recovery | 3.887 | AP／MP／skill 到期组整体上界 2.370 | 暂缓；平均 2.81、峰值 24 条到期项，skill 没有活动样本 |
| Lifecycle | 0.340 | 索引计数与标量判定 | 暂缓；已有增量活阵营索引，不应重新扫描 resident Units |
| Capture | 0.066 | 本轨迹没有捕获活动 | 样本不足；共享 tile 的取消/归属提交不能乱序，不凭空闲样本否定大量捕获场景 |
| Clock | 标量阶段 | 时钟推进/校验 | 暂缓；必须先于依赖模拟时间的阶段 |

Vision 共 80603 次重算，78391 geometry hits、2212 misses、0 evictions；8011/9880 tick 没有 miss，单 tick 最多 5 个 miss，最大 effective range=2。几何非空 tick 均值 2.924µs。三配置几何占比 1.27–1.37%，提交占比 63.69–64.75%。不能把整个约 43µs 的 Vision 当作 LOS 纯计算。

Movement 的 row_ns 包含 ECS 写入和嵌套计时。上述上界不是已拆出的纯 kernel，且不包含未来 gather/owned 输出/提交成本。Visuals 行循环仍包含 JSON 修改和 dirty 集合写入；8.135µs 不是一次合法并行批次预算，因为四阶段之间有栅栏。Recovery 到期组包含 pop/version/ledger/组件提交，不是纯算术；其最大约 431µs 的阶段样本对应首次 5007 个新 ID 审计，到期项为 0，不是大到期批次。

E1 独立空派发探针的 median 约 7–9µs 仅说明开销量级，不能用作本版本严格 break-even 或因果 A/B。当前证据支持保守保持串行；未实施新 kernel，不能报告新加速比、吞吐或容量。

## 读写边界与确定性

| System 内部候选 | worker 可读取/计算 | 必须保持原序的写入与栅栏 |
|---|---|---|
| Vision 冷缓存几何 | 窄只读 terrain/rules、center/range/revision；输出有序 HexSet | sorted dirty ID、geometry cache clock/LRU/hit/miss/eviction、Unit Vision、faction refcounts/explored、Fog/展示 delta |
| Movement 活动行计算 | 当前 moving ID、Position、Movement 路径、dt 与像素规则；仅计算结果 | 所有逐段跨格事件、Position/Movement、spatial 占用、vision_dirty、presentation_dirty、活动集合清理 |
| Visuals 同阶段行更新 | 完整前序阶段完成后的自有行或窄事实；各行产生 patch | attack→spawn→projectile→effect→damage；新箭同 tick 得到完整 dt；ID 分配、实体删除、dirty；effect 错误保留原成功前缀 |
| Recovery 到期行计算 | 仅原调度器认定的当前版本到期项及相关组件 | bucket/pop/version、取消/重排、AP/MP/skill、elapsed ledger、presentation dirty；CPython floor-div 和时钟语义 |
| Capture 可分离算术 | 仅独立行 dt/progress 算术，需未来单独归因 | 同 tile 多 Unit 冲突、AP、归属/取消、实体删除；duration=0 的部分写入及停止点 |

不复制整个动态 World，不按线程完成先后来分配 RNG／ID／动作结果，不重新遍历全部 resident 来凑批次，不跨越动作请求或延后本 tick 提交。原 M→Q→N 语义与一次性展示事件不变。

System 内分块、System 间并发和跨请求只读共享是三条不同路线：本阶段只研究第一条；第二条仍是 E1 窄接口候选、没有生产调度；第三条的 ObservationBatch/只读面板能力已存在，本次未改接入。

## 后续实验顺序

1. 优先给 Vision 冷缓存几何建立串行拆分及条件成本试验：使用合法范围、原 dirty 批次，记录 miss 数/视距/纯计算/整理/提交。先逐行模拟缓存元数据顺序；A→B→A、容量 1 时仍须保留三次 miss/两次 eviction，不能靠合并键悄悄改变导出状态。无收益则 inline。
2. Movement 仅在更多同时移动单位的可复现负载下重访。保留 O(active) 和多段跨格事件；先量窄 gather＋compute＋ordered commit，不能把现有行上界当作收益。
3. Visuals 优先浮字等单阶段大批更新；各阶段原序提交后才能进入下一阶段。投射物在规范轨迹为 0，另建合法 ranged 负载后才能判断。
4. 当前 Recovery/Lifecycle/Clock 不启动并行改造；Capture 没有活动数据，先补负载再归因。不同输入上的收益需独立完整等价、同二进制单变量 A/B 与实时闭环验证，才可变更策略。

这些是条件 roadmap，未选择新数值门槛或新增生产线程派发。当前目标下优先减少 Vision 的串行提交/数据表示成本，属于可独立验证的后续优化假设。

## 诊断与验证

测量/validated 源码 `6d4018cc0c607a51a3783428867ba9259bb43f43`，annotated tag `rust-parallel-e3-internal-attribution-2026-10-01`；Release 扩展 SHA256 `e0f46cfbffd8542c08cd2b2e6b4a26c000da05ecb9bffd3466d77fa859a9834d`。问题起点是 E2 最终文档节点 `0aa28ac2ae0267048fcdb3998f9d76175ed4d699`；独立对照为 E2 `2bc57d5`、extension `23dc7e4…`。本阶段没有执行策略 fix。

私有推进接口 `_step_profile_json` 增加 `candidates` 字段；计时仅在本次调用中拥有，既不持久化到 Runtime，也不进入 export/展示。普通路径的 const false 分支不读取计时器。API18/schema5/oracle 保持，诊断能力仍须按源码及 wheel 哈希识别。

- 2315 Python、4 Rust core/rotk 测试、fmt、Clippy、Release 通过。Python 测试包括 PyO3 扩展契约；extension-module crate 不用无 Python 链接的 standalone test binary 代替。
- 24 项新增定向测试覆盖 1/2/4、none/dummy/window、A→B→A LRU、移动、同 tick 投射物、资源到期，逐步比较完整权威状态/展示增量；原错误前缀等回归继续保留。
- 新普通/诊断 twin 在 1/2/4 完整重放，独立 E2 普通路径重放；4 轮各 40994 请求/9880 step/9880 展示，完整响应及事件/最终状态一致。
- 旧/新 4 个契约变体各 36 场景/174 step，含错误、reset/close，完整输出字节相同；复用 E2 canonical raw＋checksum，不重复保存相同内容。

没有新 live 验收/Performance Frontier，没有确认新增玩法 GAP。G001–G003 基线差异、G008/G009 OPEN、R001/R002 RISK 保留；原 49 项删除、两处冻结目录保持。Rust 负责高效世界执行，Python 保留接口与生态。未 push/merge，迁移发布尚未完成。
