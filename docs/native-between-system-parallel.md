# E4：System 之间并行的派发预算研究

后续不同候选的真实重叠与净收益见 [E5：Movement∥Visuals](native-movement-visuals-parallel.md)。E4的Vision候选边界及负筛选历史保留。

本轮从 E3 `ad02b75f2b83f97fe0bef4c1c9eee5742b1610fb` 起步；目标继续为 5000 Units＋1000 Agents，5000 Agents 暂缓。Rust 执行世界、Python 保留接口与生态。默认 native1、API18/schema5 和普通 step 的执行顺序保持原状。

## 依赖与成本

| 阶段 | 主要读取 | 主要写入 | 并行边界 |
|---|---|---|---|
| Statistics | 旧 Position/MP/Fog、UnitCount、统计活动批次 | 记录、历史、可见性/阵营统计 | E2 仅内部纯记录构建；成功前缀必须先提交 |
| Movement | 路径、位置、资源、占用 | Position/MP、空间索引、Vision dirty、展示 dirty | Vision/Capture 必须看见新位置；本轮不拆 |
| Visuals | 模拟时钟、视觉活动实体 | 新建/删除实体、ID、组件、展示变更 | 必须成功后进入候选区，不能延迟结构修改 |
| Recovery | 时钟、资源组件、到期桶、新 ID、MP pending | AP/MP/SP、恢复索引、展示 dirty | 与 Vision 语义独立；保留原任务内顺序 |
| Lifecycle | 模式、规则、时钟、living 索引 | GameState、GameOverEvent | 不改变 Position/UnitInfo/Vision/Fog；GameOver 后仍更新 Vision |
| Vision | 最新 Position/Vision/UnitInfo、terrain/rules | 缓存/LRU、Fog/refcount、Vision 组件、展示 Fog delta | 需要窄输入/独占工作上下文及原序发布；join 在 Capture 前 |
| Capture | 新位置、占用/资源/归属 | 占领、归属、事件、展示 | 保持在候选区之后，保留错误前缀 |

E3 全 9880 tick 的零开销两分支上界为 `min(Vision, Recovery+Lifecycle)`：均值约 4.0–4.3µs，约占 native step 1.8–2.0%。这是完整阶段的理想预算，含可变 ECS 操作，尚未扣窄输入准备、补丁发布或调度；不能当作已实现收益或整帧加速。

System 内部并行（E2 Statistics）、System 之间重叠（本轮候选）和跨请求只读共享（已有观测批次）是不同机制。本轮未新增跨请求缓存，也未建立通用 Bevy Schedule。

E3 诊断平均成本（µs/tick；native1/2/4 分别列出，不是无诊断净收益）：Movement 31.049/32.968/31.637，Visuals 9.315/9.458/9.264，Recovery 3.887/4.066/4.068，Lifecycle 0.340/0.429/0.377，Vision 43.504/43.685/42.542，Capture 0.066/0.074/0.079。Capture 在此轨迹无活动；这些数字不外推到活跃占领或更高接触密度。Statistics 保留 E2 的已验证内部并行，成本取决于当前活动批次，不能与 R/L/V 无条件重叠。

## 分阶段研究接口

私有 `_between_systems_step_json(dt, wall_time, mode, profile=False)` 是实际推进，不是 dry run；模式只作用于当次调用。阶段一支持 `baseline` 和 `empty_fork`。`split_serial`、`parallel` 在派发预算通过之前明确拒绝，且拒绝发生于时钟写入前。不得将未实施模式当作串行别名后报告为四模式完成。

`empty_fork` 在 Visuals 成功后派发一个空任务，调用线程执行真实 Recovery→Lifecycle，然后 join，再串行 Vision→Capture。复用实例内 ReadPool。调用线程不偷取池任务；区域最多一个后台 worker 加一个调用线程，统计批次已 join。两侧 panic 均在 scope 内捕获、join 后按既有故障边界重新抛出；没有新游戏错误、回滚或重试。阶段一没有转移 Vision/Fog 所有权。

候选条件：native2/4、realtime、window/indexed、Vision enabled/bootstrapped、Fog 存在、Vision dirty 非空、Recovery enabled 且模拟时钟前进，且有新 ID、MP pending 或到期桶。桶检测包含待清除的 stale 项；该谓词保守且只读。不因 GameOver 提前跳过 Vision。

普通 step 的新增分支由 const generic 编译关闭，不读取候选谓词或新增时钟。原 `_step_profile_json` 仍为顺序阶段；E4 诊断返回单独的阶段字典，`eligible/forked` 为计数，`fork_region` 包含 Recovery/Lifecycle，不能再次相加作为完整 step 耗时。

## 决策与证据

最终数字、阶段停止条件、源码/wheel 标识和原始证据见 [Lab E4](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-between-system-parallel/README.md)。以 manifest 的 exact SHA 为准，分支不是测量身份。本机 Lab 位置为 `/Users/liyang/Developer/star-lab/experiments/2026-10-rust-between-system-parallel`。

同二进制、同线程、同私有 FFI 的 baseline/empty_fork 对照关闭诊断。每个 2/4 配置三轮 ABBA 完整输入，不删预热或慢尾。独立诊断只确定相同 tick 的候选 mask，E3 计时只提供理想上界。100-tick 分块（尾部 80 tick 保留）、10000 次 bootstrap、seed42；候选开销置信区间下界耗尽预算时停止拆分。这是收益优先的保守筛选，不证明其他调度器或更大工作量永远无收益。

若未来通过该关口，才依次实现 split_serial、parallel 和真实窗口验收。Vision 必须仅借只读 terrain/rules，独占缓存/Fog，worker 不访问可变 ECS；main 保持 Recovery→Lifecycle，再 join、按原序发布组件与展示补丁，禁止复制完整 World/Fog/cache 或新建全局线程池。

## E4 最终结论（2026-10-02）

触发收益优先的保守停止条件。当前同二进制配对诊断中，2/4线程8020个候选tick的理想预算均值7.098/7.769µs，fork区额外成本9.512/9.048µs；成本减预算95%区间[0.456,5.385]/[0.256,2.421]µs为正。包含计时/bookkeeping与固定先后次序效应，不能解释为无诊断的严格负收益证明。旧E3上界仅历史参考；独立重放的完整无诊断ABBA有轮次矛盾，全部保留，不报告实际System并行净收益。

只完成baseline/empty_fork，split_serial/parallel明确未进入，真实窗口未进入；普通step未接入，无容量/Frontier更新。原始28次完整重放、独立7变体全状态/error/reset合同与校验链见Lab。未来先重测本负载的调度预算或更大的独立CPU工作，再考虑窄输入/独占Vision工作上下文。
