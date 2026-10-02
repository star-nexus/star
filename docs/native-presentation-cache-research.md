# E6：展示数据与 ECS 缓存研究

进度：`归因 █ | 契约/原型 █ | 完整等价 █ | 配对收益 █ | 条件窗口 █ | 归档 █`。

执行源码 `0a297a868f589dd49eb514f3c73402142df05e2c`，起点4657dd4。
研究入口 `WorldPresentation._apply_research(delta, *, mode="baseline")`；普通apply不变，
默认关闭，未自动采用。API18/schema5、native默认1、Statistics策略及Rust普通step不变。

## 实现与缓存契约

仅九类Unit展示组件可复用：Position、Unit、Count、Movement、MovementPoints、
ActionPoints、Status、SkillPoints、ConstructionPoints。已有规范对象保持identity，
完成全部字段转换后一次发布独立字典；path、cooldown和其他可变输入容器不共享。
新增、移除、删除、空间索引upsert、World revision和事件顺序仍按原路径执行。
缺字段、未知字段、非标准类型、扩展属性或非规范容器退回原构造/替换路径，
保留默认值、异常位置及此前成功提交的前缀；无效mode在任何写入前拒绝。

公开World.add_component仍然替换。query缓存保存成员/次序，引用缓存保存活组件；
成员或引用变化才失效，原地字段直接可见。UI缓存引用后逐帧检查faction序列，
阵营变化触发计数重算；Animation读取活字段。计算结果缓存必须依赖World revision
或专用失效机制，不能将component_reference_version当作字段内容版本。
其他Tiles/Singleton/Players/Fog/HUD/Visuals路径不变。

## 结果

同扩展、依赖、固定完整40994请求/9880tick，四个独立持久实例逐tick交替ABBA/BAAB，
native1/native4各三轮，诊断关闭。reuse_typed六轮apply均值改善44.26–45.62%，
完整展示链14.66–15.53%，固定轨迹总工作10.78–11.61%；各轮三项P99不回退，
100-tick分块/10000次bootstrap/seed42的改善区间下界均大于零。
reuse_constructed六轮apply反而慢2.11–2.71%，不满足至少10%改善门槛；不采用。
这证明仅复用引用虽降低下游重建，但不能代替减少复制及临时构造。

native4单实例完整ABBA确认：apply改善45.58%，链14.77%，总工作10.65%，通过。
fixed replay的display链包含decode/apply/displaySystems/clear/RMS提交，使用dummy，
不含Cocoa平台提交；总工作另含请求、step、delta编码，不包含验证/hash/IO/初始化。

三组新Cocoa闭环，每侧30秒预热＋300秒测量。候选帧P99为31.236/31.183/28.316ms，
均30Hz且观测/队列、完整负载、存活、合法动作guards通过。baseline第二轮帧P99
37.627ms，观测/观测队列/动作队列P99为106.806/102.427/109.141ms，guards失败；
其余baseline通过。因此六次窗口对照整体门槛未全通过，保留全部慢样本，不补跑挑选。
实时轨迹可能不同，这些运行验收数字不能替代固定输入的配对因果收益。

## 正确性与方法边界

2385项Python回归通过。native1/4分别完整校验规范请求、delta、事件、最终权威状态，
全部可变展示字段与查询次序、每100tick及末尾完整冷World；每侧29640次像素检查。
另6组Cocoa场景共2880帧（RT/TB、近战/远程、选择/未选择），权威状态不随绘制改变。

像素输入新增固定镜头/缩放/阵营/选择脚本，历史trace不包含这些输入。
早期失败先来自未冻结的选择脉冲墙钟；固定后native4在6609tick再失败。
三个相同baseline负对照也在609tick失败，证实地形缓存1.5ms墙钟构建配额导致不同帧
切换绘制路径。像素契约统一条目配额（原2048上限，时间预算无限），游戏墙钟固定，
实际perf计时仍真实。正式性能/实时验收保留原1.5ms预算；产品渲染代码未修改。
这些失败作为方法控制证据归档，不冒充玩法差异或成功性能样本。

持久轨迹内存高水位、实体及引用列表记录保留；补充三模式5万次字段发布的存活分配
检查用于发现无界保留，不能据此证明所有运行场景不存在泄漏。

完整证据、原始样本、wheel、源码bundle、命令及校验链见
[Lab E6](/Users/liyang/Developer/star-lab/experiments/2026-10-rust-presentation-cache/README.md)。
未增加容量或Frontier、不关闭既有GAP，5000Agents暂缓，不push/merge。
下一项为显示链路准备成本：从新增真实窗口分项继续追踪未归因update与RMS准备。
