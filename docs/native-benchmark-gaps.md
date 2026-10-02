# Rust 迁移：游戏规则、机制与 Benchmark GAP 台账

本台账记录**迁移期间实际出现过的差异**，包括已修复项；也单列尚未迁移的能力和待核验风险。修复不删除历史。新增规则差异必须记录后再决定如何修复，不能借迁移悄悄修改 Python oracle，也不能仅用“回归通过”代表所有配置等价。

当前已执行审计节点：E6（展示组件复用，2026-10-02；固定轨迹正收益，窗口整体对照未全通过，默认关闭）；E7显示链路准备仅完成规划与旧证据计量审计，未实施。E6验证源码 `068c1ecd17988ac6d884984e904aea924968e0ae`，主测量0a297a8，native执行代码相同、API18/schema5。最近修复的机制差异为R3d5/G014。本文件以生产仓库为主台账，Lab保存完整复现/原始轨迹和阶段报告；两个仓库按同级目录放置时，下文证据链接可直接打开。

## E7：显示链路与绘制准备（2026-10-02，仅规划）

[Lab方案](/Users/liyang/Developer/star-lab/records/rust-display-preparation-plan.md)从E6验证节点起步。
旧E6同1800测量帧复算：约3.184ms外层update残差包含约3.077ms Agent服务，扣除后约0.108ms；
不能解释成未知产品渲染成本。带诊断display8.355ms/RMS3.349ms仍需拆准备、实际绘制与平台边界。
首选研究有序命令缓冲，P0归因后再选择单一原型；ordinary apply与reuse_typed层内对照隔离E6收益。
目前没有原型、新性能实验或新加速比，产品显示路径未改变。研究默认关闭，画家顺序/像素/动态输入/
缓存失效/错误前缀与生命周期必须验证。E6窗口负结果、G001–G003历史、G008/G009 OPEN、
R001/R002 RISK保留；没有新增确认玩法差异或GAP关闭、容量/Frontier变化，5000Agents暂缓。
进度：`计量审计 █ | 方案 █ | 新诊断 ░ | 原型 ░ | 等价/收益 ░ | 条件窗口 ░`。


## E6：展示组件复用研究（2026-10-02）

[实现与边界](native-presentation-cache-research.md)：三个私有consumer模式，普通apply不变。
2385项回归及native1/4完整请求/展示/查询/像素契约通过；reuse_typed固定轨迹六轮
apply改善44.26–45.62%、完整链14.66–15.53%、总工作10.78–11.61%，P99及区间门槛通过。
仅复用构造对象的模式apply慢2.11–2.71%，不采用。native4单实例确认通过。
候选三轮实时窗口guards通过，但baseline第二轮帧及队列超限，六次整体窗口gate未通过。
默认仍关闭，未将固定轨迹加速解释为容量提高；不新增已确认玩法GAP。
像素墙钟及地形缓存构建进度的控制失败/相同baseline反例独立归档，产品代码未因此修改。
G001–G003原状态、G008/G009 OPEN、R001/R002 RISK保留；5000Agents暂缓，Frontier不变。
进度：`契约/归因 █ | 原型/回归 █ | 等价 █ | 收益 █ | 条件窗口 █ | 证据/恢复 █`。


## 整体性能评估（2026-10-02，仅规划，执行研究节点仍为E5）

源码审查节点3b167b1；最新完整窗口仍对应E2/source2bc57d5，而非当前E5 binary的新live。canonical复算支持先评估展示消费/显示准备与已有read-batch接入，native候选为Statistics历史结构、Vision集合/Fog提交表示；候选实现与净收益均未验证。约5.1ms未分项update不归因于render/GC，诊断System重叠上限不作为新加速比。详见[Lab整体评估](/Users/liyang/Developer/star-lab/records/rust-performance-optimization-assessment.md)。

若后续实施，必须保留完整观测、动作/RNG/ID顺序、时钟、错误成功前缀、派生引用与一次性事件；表示改变不得改变历史上限或采样，调度改变须记录实际接纳序列。此阶段仅复核已有证据与提出投入建议，没有生产执行/API18/schema5/default1变更、确认新玩法差异、容量/Frontier或GAP关闭。G001–G003历史、G008/G009 OPEN、R001/R002 RISK保留；5000Agents继续暂缓。

## E5：Movement 与 Visuals 的 System 之间真实重叠（2026-10-02）

源码94913a4f836a3c106e08a1334cb81971cfd728c3；窄Position存在性/next-ID事实及Visuals所有权转移，无World复制，复用实例pool。一worker Visuals计算与caller Movement重叠，join后原序Spawn/Remove/状态发布，预期错误成功前缀和两侧panic join边界保留。普通step/default1/API18/schema5/E2 Statistics128策略不变。

13个独立E4/四模式×线程合同输出字节一致，各13场景/377step；2345Python/6Rust/fmt/Clippy/release通过。当前规范目标5000Units/1000Agents的native2/4三轮主对照各仅1轮通过mean/P99/CI95门槛，所以不进入单实例确认或live；0/4/16敏感性不替换预注册门槛8。无新增确认玩法GAP，G001–G003历史、G008/G009 OPEN、R001/R002 RISK保留，5000Agents暂缓。完整证据见[E5边界与决策](native-movement-visuals-parallel.md)和[Lab正式包](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-movement-visuals-parallel/README.md)。结论限于本机/当前轨迹/门槛8，不泛化所有System并行方案。

## E4：System 之间并行派发研究（2026-10-02，筛选负结果已验证）

从 E3 ad02b75 起步，私有 baseline/empty_fork 探针测量一 worker＋caller 的调度预算；普通step保持原序，未实施Vision拆分或实际System之间并行。无新增确认玩法GAP，G001–G003、G008/G009 OPEN、R001/R002 RISK 保留；5000Agents暂缓。阶段停止条件与完整证据见 [E4边界说明](native-between-system-parallel.md)及 [Lab正式包](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-between-system-parallel/README.md)。回归通过不改变旧GAP状态或容量身份。当前配对诊断含计时开销，按收益优先保守停止；无诊断ABBA有矛盾轮次，未形成实际并行净收益结论。

## E3：其他 System 内部候选归因（2026-10-01）

[成本/依赖与条件 roadmap](native-internal-system-candidates.md)：Vision 未缓存几何占整体仅 1.27–1.37%，主要成本在原序 Fog/集合提交；Movement 行处理乐观上界约 5.36–5.45µs/tick，Visuals 单阶段批次很小，Recovery 到期项峰值 24，Capture 无活动样本。当前负载没有足够证据立即新增内部并行；条件保留 Vision 冷缓存几何、更多同时移动单位、Visuals 大批同阶段更新。不得把诊断上界当作普通路径收益或新线程门槛。

源码6d4018c，extension e0f46cf，annotated rust-parallel-e3-internal-attribution-2026-10-01。2315Python/4Rust/fmt/Clippy/release通过；旧E2及新1/2/4共4轮完整40994请求/9880step/展示重放一致，4个36场景/174step契约输出字节相同。[Lab证据](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-internal-system-candidates/README.md)。仅添加按次私有归因，不改规则、动作/RNG/ID顺序、观测、E2策略、默认线程、API18/schema5/oracle。没有新 live 容量/Frontier；未确认新增玩法GAP，不关闭G008/G009/R001/R002。5000Agents仍暂缓。此节优先于旧E2的下一候选。

## E2：Statistics批次记录构建并行（2026-10-01）

[实现和边界](native-statistics-parallel.md)：只收集当前批次窄借用事实，已有实例池计算自有JSON记录；主线程按原序插入组件、提交观测及历史。错误成功前缀、重复/缺失ID、旧Position/MP/Fog采样、历史裁剪、时钟及后续System停止点保持。128行以上且配置2/4线程才调度；默认1线程及游戏批大小不变。没有新增跨System调度器或世界快照。

串行拆分44c3696、实验原型7ab0ac1与独立旧P0二进制比较36场景/174step完整状态、错误、展示、reset；原R4e40994请求/9880tick/展示完整输出流及最终状态也一致。同二进制同线程的交替完整step对照和小批次负结果支持128门槛；正式策略2bc57d5、extension23dc7e4在1/2/4普通step重放一致；2291Python/4Rust/fmt/Clippy/release通过。真实Cocoa5000Units/1000Agents显式4线程三轮30预热＋300秒全部门槛通过；帧P99为28.283/28.643/28.631ms，max91.923/102.449/32.239ms全部保留，不宣称整帧因果加速或每帧无抖动。[Lab证据](/Users/liyang/Developer/star-lab/experiments/2026-09-rust-statistics-compute/README.md)。

未确认新玩法/信息GAP。API18/schema5/oracle和Python生态边界不变；诊断绑定以源码及wheel哈希识别。G001–G003、G008/G009 OPEN、R001/R002 RISK均保留，5000Agents继续暂缓。此节是当前节点；下方E1/P0保留历史决策。

## E1：ECS System之间与内部并行方案探索（2026-09-30）

按用户新指示，活动任务转向ECS内部并行，P0跨请求批次候选暂缓但保留历史。[方案审查](native-ecs-parallel-design.md)识别Recovery/Lifecycle/Vision拆成窄访问后的跨System候选，以及Statistics/Movement/Vision等内部候选。Statistics读旧Position/MP/Fog、按行错误后的部分写入、缺组件插入；Visuals结构修改；Vision LRU/引用计数/事件提交仍是约束，不能由worker完成顺序决定。

锁定Bevy0.19.1的独立机制探针验证窄组件并行、冲突/独占串行、5000实体中100活动子集和已有池的有序返回；这些是简化探针，尚非真实世界System等价性验证。选择E2 Statistics当前批次计算/有序提交的最小原型，先串行拆分和成本分项，再考虑2/4线程。未修改生产执行代码、API/schema/oracle或容量，未确认新玩法GAP；G008/G009/R001/R002不关闭。

## P0：独立Rust并行依赖审计与成本归因（2026-09-30）

从R4e tag隔离到 `codex/rust-ecs-parallel`。完整[System读写依赖表](native-system-dependencies.md)区分System间、System内和跨请求共享。新增私有逐System推进计时入口，共用原step执行顺序；普通step无计时读取，诊断墙钟不参与规则/CD。原错误/部分写入与展示drain边界保留。API18/schema5/oracle不变，需以新源码及wheel SHA识别新增诊断能力。

2239Python回归（22新增）、4Rust/fmt/Clippy/release通过；R4e全40994请求/9880tick/9880完整展示的冻结基线与候选1/2/4输出流及最终状态一致，候选普通/计时路径完整对象直接对照。统计/视野/移动平均0.167/0.045/0.027ms（含录制预热的headless归因）；11007观测中7097处于多查询段，1604同阵营重复，面板无重复。选择P1已接纳连续查询的编码批次候选，尚未实施或确认收益。

本阶段是成本归因，不是并行收益/容量验证；不确认新增玩法GAP，不将“未发现”当作全量证明。G001–G003基线差异、G008/G009 OPEN、R001/R002 RISK全部保留，5000Agents暂缓。诊断可能改变墙钟耗时，不用录制输入重放速度推断真实闭环接纳分布。[Lab记录](/Users/liyang/Developer/star-lab/experiments/2026-09-rust-system-attribution/README.md)。

## R4e：当前容量验证（2026-09-29）

复用R4d实现/API18，未修改生产执行代码或规则。5000Units/1000Agents三轮300秒30Hz长测通过；40994请求/9880tick的4线程重放保持响应、事件及最终权威状态一致。原生产Python与当前规范化Python的单次同条件短测均保留；它们不是同轨迹对照，原版与规范化版仍有G001–G003顺序差异，不能将性能数字解释为完全相同Benchmark轨迹。没有确认新增玩法GAP；G008/G009/R001/R002继续开放。[证据](../../star-lab/experiments/2026-09-rust-1000-agent-validation/README.md)。

## R4d：观测传输接口的兼容边界（2026-09-27）

新增 `get_faction_state_json`，让 Python host 取得 Rust 已编码的完整观测；原字典接口继续保留。实现/契约测试源码 `5147e4d8e0c33c997bd86960d87fa4b5b3ca90c5`，复用 API18 二进制与原鉴权入口。字段、Fog、权限、显式子集顺序、动作接纳及世界时钟没有改动；22项新契约和2217项完整回归通过。

固定5000-Agent实际输入的对照包含19929请求、2679tick和2679展示提取；旧路径及直接传递的1/4线程路径全部响应、事件、最终权威状态一致，该轨迹字节也相同。对照中的直接路径是Lab分段探针，不能单独当作窗口容量结论；正式接口另通过契约与实际窗口录制验证。JSON编码器的数值拼写/空白差异不作为一般字节契约，解码后内容和列表顺序必须保持。没有确认新增A/B类玩法/信息GAP，不据此关闭G008/G009/R001/R002。

本轮测量包含完整客户端解码和原30秒闭环；没有删减公共信息、增加思考期间轮询、改用过期观测或延长思考时间来减负。网络host仍未自动切换到本接口，G009继续OPEN。完整证据与容量限制见[阶段报告](../../star-lab/experiments/2026-09-rust-5000-agents/README.md)。

## 比较基线与影响口径

- **原生产 Python**：`6a970deaee7d9b8d3939edd102973f2377edd6ac`。迁移分支尚未合并 main。
- **当前规范化 Python oracle**：`3cc4ffea091dcf6afa8691c217ec4b09e25d4b5f`，规则标识 `python-r0c-3cc4ffe`。Rust的严格等价目标是这个基线。它与原生产的排序差异见G001–G003；不能把两者混称“原版”。
- **A 数值/机制**：能改变权威状态、动作接纳、评分或统计；**B 信息**：改变Agent能看到的内容/顺序/错误反馈；**C 派生数据**：展示副本/应用层差异，是否影响决策须追踪消费者；**D 能力缺失**：某玩法或入口尚不可运行。
- `CLOSED`表示指定复现和修复验收通过，**不代表整个迁移完成**；`BASELINE CHANGE`表示已明确纳入版本化oracle的变化；`OPEN`为已确认但未修复；`RISK`只有风险线索，不能当成确认差异；`PRESERVED`是原版已有机制，本轮没有引入差异。
- JSON对象键排列本身不属于相等标准，**键被转换成可见字符串后则属于标准**。真实LLM的prompt、报错和列表排序都可能影响决策，即使单元测试中的最终胜负暂未变化。

## 索引

| ID | 差异 | 影响 | 状态 |
| --- | --- | --- | --- |
| G001 | R0实体/事件相关遍历与输出顺序规范化 | A/B，潜在轨迹影响 | BASELINE CHANGE |
| G002 | R0b补齐多技能列表排序 | B | BASELINE CHANGE |
| G003 | R0c补齐两种观测地块排序 | B | BASELINE CHANGE |
| G004 | 死亡后Python展示Player.units仍保留死者 | C；消费者依赖时影响决策 | CLOSED于R3d3a |
| G005 | Unicode十进制数字在策略分/统计计数中不兼容 | A：已复现分数/统计改变 | CLOSED于R3d3a |
| G006 | 对象转文字的键顺序丢失 | B：策略依据/累积标签文字不同 | CLOSED于R3d3b |
| G007 | VLM图像观测入口曾缺失 | B/D | CLOSED于R3d3c本地接口范围 |
| G008 | BOT驱动尚未接Rust世界 | A/D：不能复用原BOT对局 | OPEN |
| G009 | 网络host、回合ACK及结束通知投递未接 | A/D：联网生命周期缺失 | OPEN |
| G010 | 五种非图像观测曾缺失 | B/D | CLOSED于R3b |
| G011 | 三种系统统计/状态指令曾缺失 | A/B/D | CLOSED于R3d2b |
| G012 | 普通应用入口与完整结算曾缺失 | C/D | CLOSED于R3d2b离线范围 |
| G013 | 嵌套文本中Unicode不可打印字符转义不同 | B：策略依据/标签文字不同 | CLOSED于R3d3b |
| G014 | 超长十进制字符串累计统计未遵循Python解释器限制 | A：已复现持久化计数差异 | CLOSED于R3d5 |
| R001 | 其他宽松数值/字符串转换边界 | A/B | RISK，未全面审计 |
| R002 | 其他冷组件的动态展示覆盖 | C | RISK，需逐写入点审计 |

## G001–G003：原Python与规范化oracle之间的差异

**触发**：无序实体/集合遍历，同一场景在不同hashseed下导出列表或处理顺序不同；多技能和两种地块列表在初版R0审计中遗漏。

**旧→新**：G001采用外部实体ID排序、同优先级沿安装/订阅顺序、明确活动条目的处理顺序；G002技能名按字典序；G003 `observation.visible_environment` 与 `unit_observation.visible_terrain` 按 `(col,row)` 排序。显式`unit_ids`保留请求去重后的顺序，固定A*邻居和平局顺序未改。详见[排序契约](runtime-determinism.md)。

**影响**：观测列表/提示顺序确实不同；G001可能影响共享状态更新或随机消费顺序。没有在真实LLM Benchmark中量化胜负变化，不能宣称数值影响为零，也不能把“可能”写成已经观察到排名变化。

**版本/证据**：

- G001 原生产 `6a970deaee7d9b8d3939edd102973f2377edd6ac` → `78cc8da3a03ffedaea58642abae8fcb710db997d` / `rust-python-oracle-r0-2026-09-11`；[R0跨hashseed轨迹、可复现Visibility历史顺序反例](../../star-lab/experiments/2026-09-rust-r0/README.md)。919回归；6配置各150ticks验证对应范围。
- G002 初R0遗漏 → `17b17766923ce4db05efb17aaf023818cf69cdf6` / `rust-python-oracle-r0b-2026-09-12`；[四技能列表反例](../../star-lab/experiments/2026-09-rust-r0b-skill-order/README.md)。1047回归。旧R0及其后未补齐节点不能标为所有可选功能hash独立。
- G003 R3a `7f4ad57bbd6966748c0fb49deb82f6ad43fc7aee`仍有遗漏 → R0c `3cc4ffea091dcf6afa8691c217ec4b09e25d4b5f` / `rust-python-oracle-r0c-2026-09-13`；[R3b报告中的两处顺序反例](../../star-lab/experiments/2026-09-rust-r3-observations/README.md)。1299回归；内容集合不变。

**处置**：用户已批准先规范化再迁移；上述变化作为oracle版本边界保留。旧实验仅从原tag复现；跨oracle分数不可直接合并。新的排序变化必须新增/更新条目，不覆盖旧证据。

## G004：死亡后的Player单位成员投影过期

**触发**：NativeRuntime中一次致死攻击，再提取并应用展示增量；死亡可以发生在首次提取前或之后。

**Python**：从第一个同阵营Player.units集合中删除死者。**Rust权威状态**也已正确删除；但旧WorldPresentation只删Unit实体，没有更新Player.units，展示副本继续持有旧ID。

**影响**：确认派生状态不等价，不能供需要准确成员集合的消费者使用。当前Agent faction查询及R3d2b结算从Rust权威状态读取；本次复现两者的权威对照相同，**未观察到这条GAP改变战斗数值或该结算结果**。未来BOT/展示观测消费者若读取该副本，可能受影响，不能在修复前宣称完整应用等价。

**版本/复现**：WorldPresentation首次出现于 `5bda51db6cd68455aa5724a6ef0eca1e66f89dda`（R3c）；直接测量受影响节点是R3d2b `a6bf5f381b0393b0ab93973502d9744d6b9e3713`，API8。Lab `r3_player_projection_probe.py` 工具 `4c7f057f32633f0353286b2ac961474712a9499a`：两模式×三display×1/2/4线程设置×首次提取前后，共36例，权威一致36/36、展示Player一致0/36。完整反例在[本阶段证据](../../star-lab/experiments/2026-09-rust-r3-player-gaps/README.md)。起始提交来自源码追溯，不把所有中间tag都说成已逐个运行过。

**修复**：初次提取/重置给完整Player基线；后续只发送死亡成员ID补丁。Python消费后不修改Rust。每次死亡不跨语言复制整阵营成员集合；原权威死亡路径的集合扫描成本仍存在，不能宣称整条死亡处理O(active)。保留重复阵营Player的“第一个匹配”历史行为。修复/测量源码 `5e086be1160d49d148d09cfa6f3ee1743a3b8a1c`，R3d3a/API9，annotated tag `rust-kernel-r3d3a-2026-09-23`固定同一代码和更新后的台账。36例展示一致性由0/36变为36/36，权威始终36/36；37项契约覆盖重复Player、首次提取前后死亡、reset/epoch与独立数据生命周期。

## G005：Unicode十进制字符串改变评分/统计

**触发/最小反例**：注册Wei Agent后 `strategy_ping(score="０.５")`；或者先 `report_llm_stats(api_stats={"total_calls":"１２","successful_calls":1})`，再上报次数2、成功1。

**Python**：接受全角数字，策略分累加0.5；统计累计14次、2成功，成功率14.29%。**Rust API8**：拒绝该策略分；计数字符串转换失败按0处理，累计2次、2成功，成功率100%。第一条API计数原始字符串仍被接收，差异在后续累加发生，不能只检查第一条成功响应。

**影响**：A类确认差异，直接改变策略评分和Benchmark统计。普通ASCII样本回归通过不能覆盖此输入范围。没有审计历史真实评测输入是否出现这些值，不能声称历史分数已被影响或完全未受影响。

**版本/证据**：telemetry于 `a6bf5f381b0393b0ab93973502d9744d6b9e3713` / API8引入；同节点最小复现由Lab `r3_gap_audit_probe.py` 工具 `b76302acf93f1c54de2c40fb0ecccdaf956ee5a1`记录完整响应及状态，见[raw/compact](../../star-lab/experiments/2026-09-rust-r3-player-gaps/README.md)。

**修复**：转换CPython3.13/Unicode15.1的Nd十进制数字后，仍沿用原数值格式/下划线规则；不把上标、圈号数字、Unicode加号等额外符号扩大为合法输入。标准表68组、680数字由本机CPython3.13的unicodedata生成，新增跨全部组及拒绝边界的差分契约。修复/测量源码 `5e086be1160d49d148d09cfa6f3ee1743a3b8a1c`，tag `rust-kernel-r3d3a-2026-09-23`；77项新增数值契约通过，全角策略分与累计14次/14.29%反例恢复精确一致。未来CPython/Unicode版本变化必须复核。

## G006：对象转文字后的顺序差异

**触发**：`strategy_ping(score=0.5,evidence={"z":1,"a":2})`。

**Python**存 `"{'z': 1, 'a': 2}"`；**Rust API8**存 `"{'a': 2, 'z': 1}"`。响应可以完全相等，GameStats.strategy_evidence却不同。本次最小复现与G005共用工具和raw，受影响至少R3d2b；类似provider/model/faction错误文本转换的完整范围尚待审计。

**影响**：这不是可忽略的JSON对象键排列，而是持久化的文字内容；可能影响后续评价器或LLM文本输入。示例数值策略分相同，尚未证明最终评分变化。R3d3b审计进一步实测嵌套依据和累计provider/model标签也受影响；旧API9首次保存原始对象时，普通字典相等检查会漏掉这一差异，第二次上报转成文字后才显现。

**修复/状态**：CLOSED于R3d3b。启用已锁定serde_json的preserve_order，JSON输入、存储、导出、reset保留对象插入顺序；删除JSON键使用shift_remove，避免交换末尾元素打乱剩余顺序。明确的实体/事件/BTree遍历顺序不改，Python不提前把输入对象转成字符串。Cargo.lock仅新增已有indexmap依赖边，没有升级版本。实现始于 `0dcd86e`，统一构建/验证源码 `11aefce1fb498cd6b388b1dcf498dbd8529eafb0`（API10/schema5），tag `rust-kernel-r3d3b-2026-09-23`固定相同代码及最终台账。

**证据**：[R3d3b前后完整响应/状态及重放](../../star-lab/experiments/2026-09-rust-r3-text-order/README.md)。前置实测 `a11c2b125cae451bcac6e3c3332bcbd65af24409`：普通依据、嵌套依据、累计标签三组均不一致，修复后全部一致；契约包含截断、reset/重新导入、单条/批次和1/2/4设置。完整1897回归、旧/新场景各510节点重放通过。不能据此声称所有宽松类型转换都已全面兼容，R001保留；历史真实LLM日志是否触发仍未知。

## G007–G009：应用能力迁移状态

- **G007 VLM（CLOSED于R3d3c本地接口范围）**：原Skirmish动作子集本来就不开放此verb，双方都拒绝不能证明功能完成。R3d3b `24215823c74a79774d38cc0b354b6e3d091a3b86` / API10显式启用后，Rust报 `native action get_faction_state_vlm is not implemented yet`；Python返回结构化状态加图像/截图错误。两模式×none/dummy/window×1/2/4设置×无screen/1×1/13×7，共54组实际复现；修复后54组完整响应与权威状态均一致。实现始于 `8b59e6b`，修复/测量源码 **`173410ad603121bfe97c028e6d121c7bd9a8e232` / API11/schema5**，tag `rust-kernel-r3d3c-2026-09-23`固定同一代码与最终文档。原注册/阵营鉴权、可信身份覆盖、unit_ids语义和默认动作集保持不变；拒绝查询不截图。Rust返回结构化数据，公开Python适配器附加已有窗口图像，内核不回调Python。完整批次预校验并冻结参数；VLM处截图完成后才继续后续动作，普通查询继续批次共享；step/reset/close等不能穿过截图。38项新契约、1935完整回归及真实Cocoa四组检查通过；窗口中魏请求配魏/蜀显示视角均与Python截图字节相同。[前后raw、真实窗口、编码历史问题及复现](../../star-lab/experiments/2026-09-rust-r3-vlm/README.md)。这不关闭G009网络投递，也不代表真实多模态模型已收到图像。截图时点、全局视角和编码的原有局限见下方PRESERVED，不借迁移更改Benchmark输入。
- **G008 BOT（OPEN）**：Python可显式启用MockLLMAISystem；Rust NativeSession拒绝BOT。BOT决策/动作/资源与随机消费还没有完整闭环对照，不能将空AI槽当作原BOT难度的等价版本。缺失范围到当前R3d3c；后续实现，不重调既有难度。
- **G009 网络host（OPEN）**：Rust支持可信本地动作接口和结束通知计划，但GameScene拒绝Hub连接。认证来源、回合ACK/重试、墙钟LLM响应接纳、结束通知实际投递/上报等待仍须集成验证。Protocol性能不计本轮容量，并不意味着生命周期兼容可以跳过。没有真实联网Benchmark可比性结论。

G008/G009证据：[离线入口明确限制与拒绝契约](native-runtime.md)、[R3d2b归档](../../star-lab/experiments/2026-09-rust-r3-host/README.md)。这些是明确未完成项，不是已获准的新游戏规则。

## G010–G012：曾经缺失、已分阶段补齐的能力

- **G010（CLOSED于R3b）**：R3a `7f4ad57bbd6966748c0fb49deb82f6ad43fc7aee` 缺五种非图像观测，显式允许后仍报未实现；`d5abc70e9cda8a6820546112e6172dd9e43c1515` / `rust-kernel-r3b-2026-09-13`完成对应handler。54配置4203节点精确差分/重放；[前后探针](../../star-lab/experiments/2026-09-rust-r3-observations/README.md)。不能将此前Rust少观测的对局当同协议Benchmark。
- **G011（CLOSED于R3d2b）**：R3d2a `91dc7688601c93192fea174c69981a315ac80ef9`的strategy_ping/report_llm_stats/retrieve_game_status返回Unknown action；`a6bf5f381b0393b0ab93973502d9744d6b9e3713`接通，66新契约及API7/8前后探针。[证据](../../star-lab/experiments/2026-09-rust-r3-host/README.md)。功能接通不等于所有宽松输入已等价，G005/G006单独保留。
- **G012（CLOSED仅离线范围）**：R3d2a缺普通CLI/GameScene/结算host；R3d2b加入离线入口、等待到期一次权威快照报告。六场景510节点、新进程重放、四真实CLI进程通过；6JSON/CSV落盘，完整报告契约覆盖含Agent数据及失败路径。网络范围仍归G009；不能将关闭此离线项写成完整应用验收。

更早R1/R2是明确标为子集的原型，缺失move/战斗/Fog/权限等能力的历史边界保留在[Lab阶段记录](../../star-lab/records/rust-env-migration.md)及各tag报告；本台账不是穷举所有开发中间态的声明。

## G013：Unicode不可打印字符的嵌套文字转义

**触发**：注册后 `strategy_ping(score=0.5,evidence=["\u00a0"])`，其中字符串包含真实不换行空格U+00A0。Python持久化文本是 `['\xa0']`（含反斜杠转义）；旧Rust保存包含真实U+00A0的文本。provider/model对象或列表在后续统计累加时也走同一转换。顶层字符串在Python中直接作为文本保存，本来就不转义，修复必须保留此行为。

**原因/影响**：Rust字符串repr只覆盖ASCII控制字符，没有Python isprintable规则中的非ASCII分隔符、私用字符和未分配字符。B类已确认文字差异，可能影响消费者文本和截断位置；本例动作响应、策略数值相同，不等于已证明真实LLM评分或排名变化。源码函数起于 `02ac380d631b7391bdf0f583084aee8d13d5de0a`（源码追溯），直接实测前置版本是上述a11c2b1，不宣称所有历史tag都逐个运行过。

**修复/状态**：CLOSED于R3d3b，修复/验证 `11aefce1fb498cd6b388b1dcf498dbd8529eafb0`、API10。按CPython3.13/Unicode15.1生成713个非打印范围，在Rust查表并保留Python的\x/\u/\U宽度、引号和换行等规则；普通顶层字符串不变，无热循环Python回调或新依赖。Lab生成器 `generate_unicode_repr.py --check`核验生成表；契约通过公开动作检查全部可打印性转换边界及其邻居（Unicode标量范围），并覆盖嵌套键/标签和reset。

**证据/限制**：与G006共用[R3d3b定向审计](../../star-lab/experiments/2026-09-rust-r3-text-order/README.md)的唯一before/after raw。`float_text`对照在旧新两版都一致，不能把“可能浮点文字不同”写成已确认GAP。字符表绑定oracle版本；Python3.14/Unicode升级及孤立代理码点的传输兼容未验收，不能从此推导任意Python对象完全兼容。

## R3d4a：网络宿主权威边界补齐（G009仍OPEN）

新增API12 `host_status` / `record_message` / `turn_start_context`。当前回合、结束状态、通知候选和消息计数由Rust读取/修改；Python连接、可信身份来源、通知、ACK及重试继续保留。离线结算改用四字段权威状态，避免把展示缓存当作游戏真相；不再依赖逐Unit或全世界导出来判断结束。报告仍只在既有60墙钟秒到期时导出完整数据。

**兼容范围**：消息与动作分别计数，单条动作之后计消息、批次之前计消息；未注册非空Agent先增加个人计数再报错，包括首次注册装入批次被旧host提前拒绝这一历史行为。重新注册改变消息统计阵营，但不删除旧阵营注册表行；回合通知候选仍取当前阵营注册表与stats映射的并集。候选按原注册表→stats插入次序返回，Python逐项add到set后过滤在线对象，保留原发送顺序。

**PRESERVED及确定性限制**：旧通知顺序来自Python字符串set，可能随进程hash seed改变。R0并未规范这条网络投递路径；本轮不把它擅自排序，也不能据此宣称跨进程网络接纳顺序已确定。重放仍必须记录真实接纳顺序。未来若规范该顺序或清理旧注册表行，需要独立版本化和Benchmark影响记录。没有证据证明历史真实LLM评分已受影响。

验证与精确版本见[Lab报告](../../star-lab/experiments/2026-09-rust-r3-host-authority/README.md)。G009维持OPEN：GameScene仍拒绝Hub，本轮没有真实网络、ACK重试或5000-Agent容量验收。新的权威接口是接通host的前置条件，不是整项关闭。R001/R002和G008也未因本次工作关闭。

## 风险、保留机制与非GAP边界

**R001（RISK）**：Python宽松类型、超长整数字符串、浮点转文字、非标准容器的错误顺序等还需扩大审计；本轮只关闭有直接反例和对应契约的范围。不能把尚未检查的类型都称为已确认错误。

**R002（RISK）**：G004只补Player死亡成员同步。Combat/UnitSkills等冷数据如果将来出现新的写入路径，必须覆盖到派生数据；当前不能以一组正常小场景证明全部可选功能。

以下是已识别的**原版机制/历史行为，迁移暂予保留（PRESERVED）**，不是本次新平衡规则：

- 严重兵力损失影响移动预算；攻击随兵力弱化。用户讨论过取消移动弱化，但迁移计划明确单独处理，本分支没有取消。
- 动态占用、友军穿行/敌军阻挡、移动路径/到达、固定模拟dt及CD/恢复规则；没有开放叠格或改用墙钟推进CD。
- none/dummy/window的原有瞬移/动画、统计采样差异分别比较，不跨配置强行统一。
- Agent占领与人工计时占领、人工/Agent结束回合的不同重置时点；fortify返回AP与实际AP的不一致、地形skill的success/result错配、godview的历史战报属性错误；见[已保留契约](native-runtime.md)。纠正这些机制须单独版本化，不借“Rust修bug”改规则。
- R3d2b保留无Agent/已收齐也等待60墙钟秒的现有结算流程，以及同阵营重复统计累加。这影响评测完成时点与统计解释，但不是新增差异。
- **VLM显示契约（R3d3c实测确认）**：复制当前RenderEngine的全局画面，不因请求阵营改变UI视角、相机或Fog，也不重新渲染到最新tick。当前显示蜀视角时，魏查询也得到这张图；结构化JSON仍按魏权限生成。无screen返回frame_error，headless的1×1 surface保持1×1。这个原有信息边界不能被描述为隔离的逐Agent视觉观测。
- **VLM编码历史行为**：本锁定pygame2.6.1无扩展名编码输出TGA，但字段标注PNG。真实窗口初版像素guard失败，Python/Rust编码字节实际相同；独立3像素实验在旧2421582和新173410a均复现RGBA `(200,80,30,128)` 经捕获后解码为 `(100,40,15,128)`，alpha=0像素RGB变0；直接解析TGA RLE存储值确认变换已在输出字节中，并非仅解码器差异。opaque对照保持不变。完整窗口中原始screen RGB与解码RGB不相同，不能声称无损截图；这个历史编码行为及初版guard负结果已保留，未归为Rust新增GAP、也未静默修复。更改实际编码/标签、截图视角或时点须另行版本化，并核查旧Benchmark输入；本轮未证明历史LLM得分或排名受影响。
- 只读批次共享没有TTL/上一帧观测；R3k4及之前1/2/4配置均串行；R4a起2/4仅对缺失Unit面板真并行，不算规则变化，收益须按场景实测。更快实现引起墙钟响应接纳分布变化，需在性能实验中记录实际输入次序。

## 每阶段维护与Benchmark使用要求

1. 每项记录ID、首次发现/受影响的精确版本（区分源码追溯与实测）、两边行为、触发输入、影响范围、raw/测试、状态、修复SHA/tag、剩余限制。修复后保留反例及旧版本复现，不覆盖旧tag。
2. 原始对局/报表注明backend、生产SHA、oracle标识、native API/schema、场景/模式/display、seed、dt/时钟、动作接纳顺序、Agent节奏及适用GAP ID。旧结果的影响须从日志审计，未知就明确写未知；合成实验不能代替真实LLM排名对照。
3. 当前未合并main，因此原main节点的Python结果不因这些Rust改动自动改变；迁移分支的R0排序变化和实验性Rust结果需各自注明。不能跨版本直接混为一组基准结果。
4. 若出现影响评分、胜负、权限或观测的信息差异，先加入台账并做最小复现。修复目标优先恢复当前oracle；若确需改变规则，明确新规则版本和评测可比性，再同步实现。未关闭的必需功能/GAP不得被“总测试数增加”掩盖或用来提前切默认后端。

台账是持续维护文件，当前属于**回溯已归档重要差异＋本轮新增边界审计**，并非“没有列出就证明无差异”的完备性认证。

本检查点验证：1935完整回归（Native1013，新增38项VLM契约），3Rust/fmt/Clippy；54组VLM前后对照、真实Cocoa四配置逐字节对照、旧新编码独立对照、36组Player投影及旧/新六场景各510节点重放。G007本地接口关闭；G008/G009与R001/R002仍开放。原始窗口RGB并非旧编码的无损等价物，这一负结果按Protocol独立归档。上述数量不代表完整迁移或容量通过。

R3d4a验证补充：运行实现/构建 `97f45b1`，测试/测量 `343ced3809f0ddf57c53036613abea2f9280daf5`（只增加测试起始阵营设定，运行代码一致）。API12/schema5。1979完整回归（Native1057，新增44）、3Rust/fmt/Clippy；9配置45次消息状态与18次回合通知对照、旧/新六场景各510节点及独立进程重放通过。G009仍OPEN，没有新网络/并行/容量结论。

## R3k1：可攻击目标空间筛选（性能迁移补齐，无已确认新玩法GAP）

原Python `LLMActionHandler._unit_attackable` 在空间索引存在时已经按射程枚举候选。API12 Rust仍对每个己方Unit遍历全部可见敌军，多数射程外判断还构造错误JSON；本次将原优化迁入Rust观测内核。按实际占用格与当前阵营可见敌军集合相交，再调用原Combat判定，外部ID升序返回。射程很大或敌军很少时，按敌军坐标过滤以限制枚举成本；行动点不足/缺组件/负射程提前返回。大射程计算方法变化不代表扩大或缩小合法攻击范围。

**Benchmark语义**：Fog、叠格、射程边界、占用移动提交、死亡、行动点、权限和批次写入顺序保持原样。无TTL或上一帧结果，不引入任何近似，也不改变移动力弱化。诊断接口增加三项工作计数，不增加Agent观测字段。API13/schema5；oracle不变。

**证据**：实现/构建 `7460cd9`，最终测试/测量 `8dd16f4`（中间两次仅修正/扩充测试，Rust代码一致）；2112完整回归（新增133），163针对性，3Rust/fmt/Clippy通过，旧六场景510节点重放一致。500/5000 Units×射程1/3/80及AP0，共8组原始场景和完整响应hash逐项相同、查询前后状态不变；500Unit四组另与Python完整响应比较。5000Unit射程1/3查询中位数约11.0/10.6倍提速，只是单查询微基准。射程80略慢的有效负对照保留；没有30Hz/并行/5000Agents容量结论。

第一次新增窗口死亡测试错误混用了基础CombatSystem与窗口移动/占用索引，导致Python遗留尸体占用、reachable差一格；生产WorldBuilder使用WindowCombatSystem且会先清占用。本轮测试改为原生产组合后通过，没有为适配混搭fixture修改游戏规则。失败日志按setup-error保留，不能把它宣传为生产GAP或掩盖为优化收益。

[前后证据与精确复现](../../star-lab/experiments/2026-09-rust-kernel-targets/README.md)。G008/G009作为Python应用接入事项仍OPEN；后续优先Rust世界计算与观测执行，不把网络/ACK/策略/UI改写成Rust。R001/R002继续按实际触发覆盖审计，不因本次优化笼统关闭。

## R3k2：Unit成员索引与地形投影（无已确认新玩法GAP）

实现/构建/测量 `0e912d85c18027e77125fd770500bdd123c30d75`；API14/schema5，oracle仍为 `python-r0c-3cc4ffe`。阵营统计、敌军投影改查按外部ID排序的Unit成员索引，不再遍历地块和特效实体；索引只存实体句柄，导入/reset建立，死亡与特效销毁同步移除。现有动态生成路径只创建视觉实体，未来新增动态Unit必须维护此索引。死亡但尚未销毁、缺Headcount或Position的原过滤语义保留。

Fog地形从可见格和地图格中选较小集合遍历，仍返回精确交集并按原坐标顺序排列；空/缺失视野、越界可见格、缺Terrain与历史tile ID0语义保留。未增加信息延迟、近似或跨帧缓存，未改变权限、CD、兵力弱化或动作顺序。新增访问计数仅用于诊断，Agent完整响应不变。

**证据**：2144完整回归（新增32），165针对性，3Rust/fmt/Clippy通过；旧六场景510节点重放通过。100Units、5个己方查询、6211/60919地块×局部/空/关闭Fog共6组，新旧初始状态和完整响应hash相同、查询不改状态；小地图3组另与Python完整响应相同。60919地块局部7格视野：两次实体扫描各61019→100，地形60919→7，查询中位1.224→0.125ms。关闭Fog仍需输出全图，中位294.697→296.953ms，有效负对照保留；5样本微基准不推断显著性，不代表30Hz或Agent容量验收。

新契约覆盖1/2/4线程配置（仍串行）、死亡/reset索引更新及导入的Unit+特效混合实体过期销毁。未发现新增规则差异；G008/G009应用接入与R001/R002风险仍开放，不能以本次索引覆盖替代全部冷组件写入审计。

[完整复现及原始证据](../../star-lab/experiments/2026-09-rust-kernel-catalog/README.md)。Rust继续负责权威世界与观测计算，Python保留策略、SDK、传输与用户界面。

## R3k3：观测JSON所有权转移（无已确认新玩法GAP）

实现/构建/测量 `450bf97db4c52ead5d5ab36eda5a035a33ee4158`。原实现将已构造的JSON地形/敌军数组、reachable、逐请求Unit数组及整个批次结果再次通过serialize-to-Value装入外层对象，产生不必要的递归复制。现直接转移数组所有权；仍需要独立生命周期的共享事实/Unit面板保留原复制。公开动作批次和内部观测probe均覆盖，不仅优化诊断路径。

**Benchmark语义**：请求预校验、可信身份、认领权限、统计递增时点、M→Q→N读写边界、错误响应、列表顺序和reset/close后结果生命周期保持不变。未增加缓存/近似/轮询，也未修改规则、Python接口、JSON字段或线程调度。API仍14/schema5，规则仍 `python-r0c-3cc4ffe`；复现性能必须注明R3k3源码和wheel SHA，不能仅以API14区分两个版本。

**证据**：2144完整回归、62针对性、3Rust/fmt/Clippy及旧6场景510节点重放通过。复用R3k1/R3k2唯一原始场景，局部/关闭Fog地形与5000Unit场景×1/8请求×handler/可信动作批次共12组，新旧初始化hash、完整结果（含诊断计数）、输出字节长度、最终状态hash均一致；动作批次另与相同内核逐条执行结果及最终状态对照。已有Python差分回归覆盖三种display和1/2/4线程配置（仍串行）。未新增镜像实现的测试。

5000Units/100己方Unit查询，真实批次接口中位单请求52.232→30.815ms，8请求173.365→95.241ms。6211地块关闭Fog的8请求100.544→54.464ms。每项1次预热+5样本，仅native请求/批次与JSON编码，不含reset/import/Python解码/世界tick/绘制/Hub/排队；不同阶段旧数字不可直接混为同一实验。8请求约6.04MB必须完整输出，剩余95ms不能忽略，尚无整帧30Hz或并行容量结论。

[完整A/B和复现](../../star-lab/experiments/2026-09-rust-kernel-assembly/README.md)。无已确认新增机制差异；G008/G009仍为Python应用接入未完项，R001/R002继续开放。本轮没有扩大GAP关闭范围。

## R3k4：只读批次编码共享（无已确认新玩法GAP）

实现/构建/测量 `f37ae76785f05dd9dc9ac3009731267117bbda90`。将阵营公共字段和每个Unit基础面板各编码一次，使用不可变、拥有独立生命周期的共享片段；每个请求单独捕获owner与commandable。单条动作（包括VLM的结构化部分）、可信动作批次与handler probe都使用同一响应表示。仅内核构造的JSON Value经serde编码为RawValue；Agent输入没有作为原始JSON片段拼接。

**Benchmark语义**：正常鉴权、unit_ids去重顺序、Fog、错误响应、统计记录与revision语义保留；参数预校验保持原子，批次执行仍非事务。遇到非faction查询就结束只读段，新段重建。前面响应持有旧事实及当时权限，不再查询实时组件；后面的认领转移、死亡、reset/close不能修改此前结果。没有TTL、延迟拍照、字段删减、近似或新增线程。API15仅扩展四个诊断计数；Agent字段、schema5、oracle均不变。

**证据**：2156完整回归（新增12）、74针对性、3Rust/fmt/Clippy、旧6场景510节点通过。新增契约覆盖三种display×1/2/4线程参数、含引号/反斜杠/换行/空字符/Unicode的身份及技能文字、权限分离、混合批次认领与死亡、结果独立和reset/close。15组前后Agent完整响应、初始/最终状态hash和原有诊断计数相同；public批次另与同内核逐条动作执行比对。诊断包新增字段，不能要求其整体hash/长度与API14相同；单条动作输出长度相同。

5000Units、每请求选择100个己方Unit：public八请求中位88.366→23.552ms，单条动作入口27.639→21.531ms。八请求的public_encodes=1、panel_encodes=100、共享引用8/800（含首次引用，不是cache hit），仍完整输出约6.04MB。每项预热1次+5样本，包含native处理和编码、不含导入/reset/Python解码/世界tick/绘制/Hub/排队。不能把23.552ms当作整帧成本或1000Agents容量达标；真实并行尚未实现。

[前后原始证据及复现](../../star-lab/experiments/2026-09-rust-kernel-encoded/README.md)。未确认新增机制差异，既有G008/G009应用缺口和R001/R002风险保持开放。本次只确定响应事实的生命周期和共享边界，不代表全部权威状态写入已经审计完毕。


## R4a：有界只读并行与状态边界审计（无已确认新增玩法GAP）

实现源码 `ddb084e42e07fdb359c511b8727f888ff3a5a38b`；[完整写入/消费者审计](native-state-boundaries.md)。Combat基础属性和UnitSkills在当前已实现入口内没有动态写入；Player、UnitStatistics冷组件则有写入。Vision和CombatRoll保持Rust权威，Python按展示需要接收派生数据，不作为完整世界副本。不能据此笼统关闭R002；新增写入或消费者仍须逐项审计。既有技能失败语义及移动力弱化均未改变。

**并行边界**：仅在稳定只读段并行计算缺失Unit面板的reachable/attackable/基础字段；公共阵营投影、权限、动作接纳、世界写入和最终输出保持顺序。每请求最多N个块，作用域join后按输入顺序装配；reset复用池，失败不替换世界，close释放池。无跨帧缓存、字段删减、近似、额外Agent轮询或随机数并行消费。

**验证**：2165完整Python回归（新增9项）、83针对性、4 Rust测试、fmt/Clippy及旧6场景510节点通过。新增契约对三种display×Fog开关比较Python与1/2/4线程的完整响应，并覆盖去重顺序、不同权限、写入分段、移动、死亡和reset。Rust屏障测试验证多worker实际同时执行。30个查询场景×旧单线程/新1/2/4共120组，完整Agent结果、权威状态hash及原工作计数相同。MP6诊断保持5000存活单位、调整位置留空格，输出966个可达格；与MP0密集原场景分开报告。

**非语义变化**：API16新增三个诊断字段parallel_panel_batches/panel_tasks/panel_worker_threads；worker利用数可能随调度变化，不属于Agent响应契约。schema5/oracle不变。真实交互中的墙钟完成次序可能变化，仍必须记录实际动作接纳次序用于重放。小查询可能因调度更慢，默认仍为Python/单线程；微测不证明整帧30Hz、排队或5000Agents容量。G008/G009与R001/R002仍开放。

[Lab证据与复现](../../star-lab/experiments/2026-09-rust-read-parallel/README.md)。


## R4b：公共事实直接编码（无已确认新增玩法GAP）

**变化**：公共敌军/地形由Rust类型直接序列化为拥有独立生命周期的不可变片段；同一只读段跨阵营复用，替代临时JSON对象树的构造、递归复制与释放。地图路径、动态占用、Fog、字段、ID/坐标顺序、owner/commandable、权限和写入分段均未改变。原版外部地块ID=0被排除的行为继续保留；新增测试曾误把该格计入总数，已修正测试预期，运行逻辑未改。

**API17诊断边界**：新增内部`_observation_profile_json`，返回普通report和独立计时JSON，不增加Agent字段。普通路径不读取计时墙钟；诊断墙钟不参与CD/世界推进。分段为嵌套墙钟时长，不能全部相加，也不能当worker累计CPU时间。schema5/oracle不变，需使用匹配wheel。

**证据**：2171完整Python回归（新增6项）、89针对性、4Rust测试、fmt/Clippy、旧6场景510节点通过。54组handler测量比较R4a、仅加计时版本、优化版本及1/2/4线程：完整Agent响应、权威状态、字节长度和原工作计数一致（worker利用数除外）。另30组handler/可信批次/单动作查询对照的完整report、状态、计数和字节长度相同；5000Units/100Units可信单请求23.899→6.439ms，8请求26.511→8.742ms。新增三阵营公共事实共享与reset至变更兵力/地形测试，旧响应仍保留旧事实。技能失败与移动力弱化未修改。G008/G009、R001/R002保持开放。

**性能与机制区分**：5000Units/MP6单线程handler查询5Units中位19.189→2.547ms，查询100Units23.339→6.218ms；每组1预热+5样本，不是P99/整帧/排队容量。较快墙钟响应仍可能影响真实输入到达次序，重放需记录实际接纳顺序。默认Python/1线程不变。

[Lab完整证据](../../star-lab/experiments/2026-09-rust-public-facts/README.md)。


## R4c：真实窗口闭环与展示增量直接编码

迁移进度：`R0 █ | R1 █ | R2/R3 ▒ | R4 ▒ | R5 ░`（阶段覆盖，不是工时百分比）。

Rust现在直接序列化dirty Unit组件引用，避免构造每个Unit的中间JSON对象树及再次装配外层Value。所有dirty队列/事件/视觉增量先完成原有提取，再在同一运行锁内序列化借用视图；Python仅收到独立字符串/解码对象，没有ECS引用逃逸。字段、空值、列表顺序、生命周期、事件消耗和动作/查询时序不变。API17/schema5/oracle沿用，性能版本需由源码及wheel SHA识别。

固定真实闭环前2000帧的跨版本重放：9296次请求结果、2000份完整展示增量、输出字节长度、最终权威状态一致。编码平均1.613→0.177ms，P99 2.349→0.434ms；Python解码平均0.452→0.490ms，P99 0.683→1.227ms，未优化解码且保留其慢样本。两次顺序测量不能推断每台机器的P99收益；单独编码成本不等于整帧成本。

Lab现通过生产GameScene/NativeSession/Cocoa窗口运行真实move/attack/get_faction_state闭环。它注入可信合成身份，使用原认领与权限入口、同一调度器及随机策略，替代网络传输。30Hz世界固定dt=1/30；1000Agents控制5000Units，逐Unit动作概率50%/25%/25%，首次0–30秒错开，动作后等待截断正态30±5秒/15–45秒，其间不轮询。按规范保存输入接纳次序、dt、必要墙钟及请求/事件/最终状态hash，可在另一线程数重放。实际在线Unit数与同时移动数分别报告。小地图minimap单位图层沿用canonical配置关闭，不能外推为所有显示配置。

2171完整回归、108展示相关、14Lab测试、4Rust测试、fmt/Clippy、旧六场景510节点通过。首次cargo test --workspace触发扩展crate的Python链接配置错误，改为项目既有core/rotk测试命令；wheel构建/导入和绑定契约在Python回归通过，错误日志保留为setup而非玩法失败。

没有已确认新增游戏机制GAP；移动力弱化、技能失败、Fog精确性与CD时钟均不变。G008/G009网络/BOT应用接入和R001/R002风险继续开放。默认Python/单线程，未合并main或切换默认后端。

**容量证据**：生产窗口/Cocoa、canonical场景、Lab事件预算8ms、单线程内核，30秒预热＋300秒测量×3全部通过。整帧P99为32.479/32.613/32.405ms，观测响应85.990/82.840/87.093ms、动作排队94.090/93.040/94.272ms，均30Hz。全程5000存活Units；实际并发移动远小于5000。部分30秒块仍超33.33ms，不能解释为每帧或任意后程窗口都无卡顿。旧版35.561ms有效负结果保留。此为限定场景的性能通过，不代表全部R3功能/R5安装与发布完成。

[完整原始证据与复现](../../star-lab/experiments/2026-09-rust-rendered-loop/README.md)。实现/测量源码 `e85e3067b1d2aed5cf08be9dbe35b1deed91dba1`；扩展SHA `8c74d05d89f1037c0157ad25e32ed4c6852bad7d316694cb056faa8c72f2d2e2`。


## G014：十进制整数字符串长度限制（CLOSED于R3d5）

**直接反例**：在CPython3.13默认4300位限制下，Agent先上报`report_llm_stats(api_stats={prompt_tokens: "0"*4300+"1"})`，再上报同阵营`prompt_tokens=2`。首次双方都原样保存文本；第二次Python的`int()`抛出ValueError，原统计函数按既定规则回退0，最终计数2；R4c Rust未检查长度，最终计数3。两个动作响应仍相同，只比较响应会漏报。Unicode数字、下划线分隔版本同样复现；负号版本旧Rust最终1、Python2。20组公开入口审计中4组完整状态不同，其他16组为边界/负对照。

**Benchmark影响**：token及工具/HTTP/空间错误等累计统计可改变，属于已确认A类数据差异。没有证据表明历史真实LLM评测曾提交这种字符串，也没有证明最终排名或战斗胜负变化。不是修改攻击力、移动力、CD、Fog、协作权限等玩法规则。

**修复**：`07bdb2e89c69959c2b8cb8e61329536c032f187e` / API18/schema5，oracle仍`python-r0c-3cc4ffe`。Python适配层仅在统计上报接纳时捕获`sys.get_int_max_str_digits()`，作为可信内部信封元数据传给Rust；Agent的同名parameters不能覆盖它。Rust先按原规则规范Unicode数字/分隔符，再计数十进制数字（含前导零，排除正负号/空白/下划线）。超限继续按原规则回退0；0表示解释器关闭限制。首次原样存储、累计时转换、错误次序和所有其他统计逻辑不变。计算在Rust执行，无逐Unit跨语言调用或内核回调Python。

低层原始native信封省略新字段时沿用CPython默认4300；公开Python入口携带实际值，覆盖运行期间设置改变、640/5000及0。批次在接纳时冻结该环境输入，重放需记录它；Lab录制器保存各请求的限制，CLI重放在请求前恢复同值。旧轨迹没有此字段，按当时运行环境解释，不把新值猜补进旧证据。API版本检查阻止Python新适配器配旧wheel。

**证据**：新增24项公开契约，177项针对性、2195完整Python回归、4Rust/fmt/Clippy、15Lab测试与旧6场景510节点通过；20组前后公开动作复现修复后全部响应及权威状态一致。涵盖全部11个累计计数字段、默认界限前/等/后、Unicode/符号/分隔符、自定义/关闭限制、首报与累计、批次、reset及运行中限制改变；另保留长小数字符串score的浮点负对照。自定义640限制的实际输入可由默认环境启动的4线程子进程重放。

[原始前后状态、命令、环境、checksum与复现](../../star-lab/experiments/2026-09-rust-integer-limit/README.md)。R001仍保留未审计的其他类型/数值边界，R002/G008/G009未关闭；不把G014关闭扩大为所有输入完全兼容。本轮未重跑容量矩阵，R4c三轮30Hz证据仍对应其原tag/API17，不改写为API18测量结果。

## E7 显示准备研究进度（2026-10-02，未完成收益验收）

P0完整9880 tick、普通/typed分层及两个真实窗口短诊断完成。普通层领地边界遍历约2.3707ms/tick、批次打包0.1118ms/tick，均包含诊断开销，不是加速比。初始快照及全部完整delta没有TerritoryControl；选择私有empty_territory模式，在live ECS确认为空时跳过重复组件查询，有任意领地组件或非标准输入立即走旧实现。

源码原型67308329c3096119d65870d400bf4624f74803df；普通方法体未改。坐标缓存最多32768项，不缓存归属/样式/实体/Surface，地图ID仍逐帧读取，复杂度仍O(visible)。2389完整回归通过；1200切镜循环缓存进入平台，24实例reset释放；dummy/Cocoa各30组领地字段、成员变化、错误前缀与resize命令/像素对照通过。40994请求/9880tick完整权威、展示和像素验证仍在进行，尚无正式收益或窗口结论。

研究默认关闭，API18/schema5/native默认1/Statistics及规则/观测/动作/确定性不变。旧E6窗口失败保留，G008/G009 OPEN、R001/R002 RISK及历史GAP均不关闭，不更新容量/Frontier，5000Agents暂缓。

**E7 内存事件更新（2026-10-02 14:49）**：用户报告系统应用内存不足，ChatGPT/Codex进程组约8GB。四个双实例全权威导出/像素校验并发及其等待性能矩阵已全部停止，未完成任何全轨迹或正式性能验收。停止后系统空闲内存约49MB→3GB；RSS不能代表压缩/交换后的完整footprint，尚未确认是优化缓存泄漏。1200小型坐标循环和24实例释放只覆盖小型缓存，不能外推整条链路安全。下一步先串行限额、完整导出/GC/模式隔离和压力主动停止保护；原因与安全条件确认前不重启大规模测试。研究默认关闭，容量/Frontier与所有既有GAP不变。
