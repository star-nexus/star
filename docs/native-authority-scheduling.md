# Rust 场景的独立权威执行

现有离线 Rust 场景默认使用单一后台权威执行器。Python UI、SDL、显示 World 和图像编码留在创建场景的主线程；权威状态、请求、控制、批次和结算查询由一个 owner 按序执行。`RustRuntime` 直接构造仍保留同步 API，`NativeSession.runtime` 提供相同公开调用的线程封装。native 默认线程数仍为1，已有工作池配置可选2/4，不创建第二个 Rust 线程池。

封顶游戏以 `1/fps` 的固定 dt 在独立时钟推进。owner 在同一锁内以接纳时间与 tick deadline 确定顺序；deadline 前接纳的操作先于该 tick，后来的操作不会无限挤掉 tick。过载时保留固定 dt、降低实际频率，不突发补 tick。记录同一权威操作/dt/wall_time 顺序可重放同一游戏状态。操作异步到达本身与原实时游戏一样受实际到达顺序影响，不宣称跨机器墙钟轨迹一致。

每个 tick 发布独立拥有的展示增量。UI 消费全部有序增量和事件，无丢弃、无覆盖。inbox32/output8是现有有限机制原型的操作参数：前者最多容纳32个等待操作，后者最多积压8份增量；满时背压等待。以30Hz计算，8份增量对应约267ms的队列容量，长期卡住UI仍会阻塞权威。这不是测出的生产最小参数，不以无限内存换取无条件世界推进。

本地控制与读请求使用相同 owner。UI等待同步调用时会继续消费增量与图像栅栏，避免输出满导致双方死锁；其他线程不接触显示数据。成功VLM响应先发布当前权威投影、暂停后续权威操作，由UI重新准备/绘制并调用原捕获器，然后继续批次。保留原输出字段、图像字节编码及历史frame_format标签；不改变star-protocol。禁止显示消费者同步重入权威，异常必须收尾join。

场景暂停停止独立时钟，恢复时建立新deadline，不计算菜单停留时间。成功/失败reset保留原Runtime状态与错误契约，reset前先停时钟并消费旧epoch增量；reset调用者仍须准备新epoch的显示World及controls。close停止接纳、完成已接纳操作、消费剩余增量、join线程后释放World。发生原生故障不换成Python模拟。

串行回退：`star --backend rust --no-hub --native-scheduling serial`。直接会话可用 `NativeSession(authority_scheduling=False, ...)`；默认会话的手动 `step` 在独立时钟未启动时使用既有显式dt，调用 `runtime.start_clock(dt)` 后禁止混入手动推进。显式uncapped测量保留原逐帧wall dt，不自动启动独立固定时钟。

覆盖范围为现有Rust离线场景及运行时接口；Rust Hub/BOT/scale-harness的既有未接入限制保持，Python路径和Agent实现不改。机制收益与CPU代价见E12研究报告；真实窗口验证另记Lab，不将模拟94%换算为生产网络、step、整帧或容量收益。
