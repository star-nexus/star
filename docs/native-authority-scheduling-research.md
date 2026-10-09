# E12：权威执行与展示解耦研究

当前仅提供私有 `_AuthorityExecutor` 机制原型，普通 NativeSession、GameScene、Hub、协议及默认路径不接入。继承 native1、API18/schema5、census 与 E11 默认地形编码复用。

当前主循环每帧接纳本地请求后执行输入、step、增量提取/应用、显示准备、绘制、SDL提交与限帧等待。E12先区分这些等待来源，不把旧性能数字当当前结论。

原型将既有 RustRuntime 的调用权独占转移至一个 Python owner 线程，运行同一个已安装 release 扩展，未新增 Rust 线程池。宿主仍负责给出确定的请求、输入、tick 和展示栅栏顺序；执行器没有自己的时间步或接纳策略。UI 主线程持有派生 World 和 SDL。

JSON输入在接纳前冻结；已接纳 FIFO 操作不可取消。取增量按操作序列写入不可变 JSON publication，附连续 sequence/epoch/revision/tick。UI按序解码应用，每项只消费一次。不合并/丢弃增量或事件。实例独占缓存不跨实例转移。输出队列满时阻塞owner；这会重新产生请求等待，必须量化，不能无界积压。研究默认 inbox32、delta8只用于有界机制验证，不是生产参数结论。

reset先消费旧epoch所有publication；待消费时私有入口拒绝reset，不改变Runtime。原reset失败保留旧状态；成功reset之后宿主必须新建对应展示World并获取新完整baseline。close先关闭接纳，执行已接纳前缀，归还尚未消费增量，再join；宿主必须消费返回增量才可声称展示/事件完整。执行器异常join、停止接纳并向未执行Future报告失败，不自动重启。

VLM需要额外屏障，使图像、阵营视图与权威revision一致，本原型提前拒绝VLM而不访问图像。本限制只属于未接入的私有研究入口，普通协议能力保持。也尚未接入本地交互、Hub发送/结算、生产reset/stop，不能称已证明完整宿主等价。

研究固定测试量：一次有效分解的10秒预热+30秒当前窗口诊断；9项机制契约；固定短输入前400tick(native1)+前20tick(native4)串行/owner逐操作比较，完整权威哈希流式落盘。后续受控等待筛选预注册后才运行，不自动上线、不更新容量/Frontier或关闭既有GAP。完整长轨迹、像素/VLM与真实网络验收属于后续接入审查。
