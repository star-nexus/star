# E13 地图查找研究

当前普通实例保留HashMap地图格子查找；E11地形事实复用和E12调度默认保持，API18/schema5、native默认1及协议/Agent不变。本轮只验证有界dense格子查找，寻路scratch和实体ID容器不改。

实例私有入口 `_set_map_lookup_mode("baseline" | "dense_tile")`，无效模式在状态变更前拒绝。`_map_lookup_diagnostics_json()`说明实际布局；两者不写权威revision、时钟或schema。普通构造与成功reset为baseline，失败reset保留布局与原状态，close释放实例。正式扩展不被研究扩展覆盖。

dense_tile将格子值转移至单一拥有的行数组，包围盒的slot存行索引；读取坐标先检查溢出和边界，空洞返回缺失。只有非空地图、包围盒面积不超过格数两倍且不超过1000000时创建slot，否则沿用HashMap。这两个值是本轮内存护栏，不是测出的最小充分容量。包围盒外新增格子用小HashMap查找，删除释放行供复用，地形字段修改直接作用于同一份TileInfo。数组行上限随历史峰值格数，reset/模式切回/close释放；不按坐标跨度无界分配，也不复制完整World或地形集合。

初次转换保留原HashMap遍历顺序；当前输出的地图集合仍按原BTree/Hex排序，模式切回或格子结构变化后的内部哈希迭代顺序不属于wire契约。搜索仍使用原BinaryHeap、HashMap、BTreeSet、邻居与平局顺序。E11每次读取当前TileInfo并验证精确签名，模式切换无需改变既有可见性或缓存有效性。

P0是隔离的诊断补丁，不进入产品：嵌套计时不能相加、1/64查找采样与空计时器校准都有观察扰动。其旧Map包装未截获通过Deref的`tiles[&cell]`索引，故不是全部地图读取的成本覆盖；容器initial setup也不覆盖后续扩容与销毁。只用作选点，净收益另用无诊断同二进制对照。

目标仍5000 Units+1000 Agents。本轮使用既有12148请求/2617tick/3010观测短输入，有限正确性及一次收益筛选；候选默认关闭，是否采用需单独审查，不宣称整帧、容量、多轮稳定性或未来硬件收益。证据归STAR Lab的2026-10-rust-map-search实验。
