# E13 地图查找默认实现与研究依据

普通Rust实例在构造和成功reset时尝试有界dense地图格子查找；空、稀疏和超限地图保留HashMap回退。E11地形事实复用和E12调度默认保持，API18/schema5、native默认1及协议/Agent不变。寻路scratch和实体ID容器保持现状。

实例私有入口 `_set_map_lookup_mode("baseline" | "dense_tile")`保留诊断与回退能力，无效模式在状态变更前拒绝。`_map_lookup_diagnostics_json()`说明实际布局；两者不写权威revision、时钟或schema。普通构造与成功reset的requested为true，active由地图资格决定；失败reset保留布局与原状态，close释放实例。手动切回baseline只影响当前实例，下一次成功reset重新选择默认布局。

dense_tile将格子值转移至单一拥有的行数组，包围盒的slot存行索引；读取坐标先检查溢出和边界，空洞返回缺失。只有非空地图、包围盒面积不超过格数两倍且不超过1000000时创建slot，否则沿用HashMap。这两个值是本轮内存护栏，不是测出的最小充分容量。包围盒外新增格子用小HashMap查找，删除释放行供复用，地形字段修改直接作用于同一份TileInfo。数组行上限随历史峰值格数，reset/模式切回/close释放；不按坐标跨度无界分配，也不复制完整World或地形集合。

初次转换保留原HashMap遍历顺序；当前输出的地图集合仍按原BTree/Hex排序，模式切回或格子结构变化后的内部哈希迭代顺序不属于wire契约。搜索仍使用原BinaryHeap、HashMap、BTreeSet、邻居与平局顺序。E11每次读取当前TileInfo并验证精确签名，模式切换无需改变既有可见性或缓存有效性。

P0是隔离的诊断补丁，不进入产品：嵌套计时不能相加、1/64查找采样与空计时器校准都有观察扰动。其旧Map包装未截获通过Deref的`tiles[&cell]`索引，故不是全部地图读取的成本覆盖；容器initial setup也不覆盖后续扩容与销毁。只用作选点，净收益另用无诊断同二进制对照。

采用依据是既有12148请求/2617tick/3010观测短输入的完整正确性与一次native1收益筛选：ENV观测均值改善5.01%，所测请求＋step＋增量提取总工作改善4.20%；step增加约0.90%（1.76µs/tick）且P99回退。这是已接受的观测密集负载取舍，不能称step加速或保证低观测负载更快。正式接入只补默认/回退/reset、受影响契约及新wheel普通入口验证，不增加性能矩阵。

当前14400slot约225KiB；1000000slot护栏约15.26MiB，仅为slot数组，不包括行、字符串与allocator。构造/reset发生一次性转换，原观测计时不含此成本。密度护栏在转换时判断，行/空闲列表可保留历史峰值；未来动态地图扩张/收缩API需另行审查。

目标仍5000 Units+1000 Agents，不宣称整帧、容量、多轮稳定性或未来硬件收益。证据归STAR Lab的2026-10-rust-map-search实验。
