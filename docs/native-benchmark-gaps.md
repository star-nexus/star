# Rust 迁移：游戏规则、机制与 Benchmark GAP 台账

本台账记录**迁移期间实际出现过的差异**，包括已修复项；也单列尚未迁移的能力和待核验风险。修复不删除历史。新增规则差异必须记录后再决定如何修复，不能借迁移悄悄修改 Python oracle，也不能仅用“回归通过”代表所有配置等价。

当前审计节点：R3k3（已验证JSON装配优化检查点，2026-09-24；完整迁移仍未完成）；前置 Rust `67e35deaacef22ed1754f39245d771c3af887888`（R3k2/API14）。本文件以生产仓库为主台账，Lab保存完整复现/原始轨迹和阶段报告；两个仓库按同级目录放置时，下文证据链接可直接打开。

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
- 只读批次共享没有TTL/上一帧观测；1/2/4线程当前串行，不算规则变化，也不能声称并行收益。更快实现引起墙钟响应接纳分布变化，需在性能实验中记录实际输入次序。

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
