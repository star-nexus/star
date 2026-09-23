# Rust 迁移：游戏规则、机制与 Benchmark GAP 台账

本台账记录**迁移期间实际出现过的差异**，包括已修复项；也单列尚未迁移的能力和待核验风险。修复不删除历史。新增规则差异必须记录后再决定如何修复，不能借迁移悄悄修改 Python oracle，也不能仅用“回归通过”代表所有配置等价。

当前审计节点：R3d3c（已验证功能检查点，2026-09-23；完整R3仍未完成）；前置 Rust `24215823c74a79774d38cc0b354b6e3d091a3b86`（R3d3b/API10）。本文件以生产仓库为主台账，Lab保存完整复现/原始轨迹和阶段报告；两个仓库按同级目录放置时，下文证据链接可直接打开。

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
- 只读批次共享没有TTL/上一帧观测；1/2/4线程当前串行，不算规则变化，也不能声称并行收益。更快实现引起墙钟响应接纳分布变化，需在性能实验中记录实际输入次序。

## 每阶段维护与Benchmark使用要求

1. 每项记录ID、首次发现/受影响的精确版本（区分源码追溯与实测）、两边行为、触发输入、影响范围、raw/测试、状态、修复SHA/tag、剩余限制。修复后保留反例及旧版本复现，不覆盖旧tag。
2. 原始对局/报表注明backend、生产SHA、oracle标识、native API/schema、场景/模式/display、seed、dt/时钟、动作接纳顺序、Agent节奏及适用GAP ID。旧结果的影响须从日志审计，未知就明确写未知；合成实验不能代替真实LLM排名对照。
3. 当前未合并main，因此原main节点的Python结果不因这些Rust改动自动改变；迁移分支的R0排序变化和实验性Rust结果需各自注明。不能跨版本直接混为一组基准结果。
4. 若出现影响评分、胜负、权限或观测的信息差异，先加入台账并做最小复现。修复目标优先恢复当前oracle；若确需改变规则，明确新规则版本和评测可比性，再同步实现。未关闭的必需功能/GAP不得被“总测试数增加”掩盖或用来提前切默认后端。

台账是持续维护文件，当前属于**回溯已归档重要差异＋本轮新增边界审计**，并非“没有列出就证明无差异”的完备性认证。

本检查点验证：1935完整回归（Native1013，新增38项VLM契约），3Rust/fmt/Clippy；54组VLM前后对照、真实Cocoa四配置逐字节对照、旧新编码独立对照、36组Player投影及旧/新六场景各510节点重放。G007本地接口关闭；G008/G009与R001/R002仍开放。原始窗口RGB并非旧编码的无损等价物，这一负结果按Protocol独立归档。上述数量不代表完整迁移或容量通过。
