# Renderer adapters v1 验收记录

实现和启动说明见[多渲染器接入](../render-adapters.md)。

| 对象 | 视觉版本 | 用途 |
| --- | --- | --- |
| pygame 桌面 | `starbench-ui-v6` | 原有窗口和 Agent 观测截图 |
| Three.js Web | `starbench-web-v1` | 浏览器指挥/旁观，不提供 Agent 图像观测 |
| ENV 展示传输 | schema1 | 私有展示数据，独立于 star-protocol |
| native | API18 / schema5 | 原有二进制，无 Rust 源码变更 |

Three.js 精确锁定 `0.186.1`。Web 使用现有 RoTK 素材、`star-offset-v1` 坐标、正交镜头和连续地面清屏色。隐藏地形与单位在服务端过滤；画面在 resize 时适配地图。

`desktop-parity.json` 比较合并点 `2598697` 的原 NativeSession 与适配后的默认 pygame 会话：dummy SDL、1200×900、river_split、seed42、固定墙钟。RGB 哈希和实际截图字节哈希相同，绘制不改变权威状态；另外核验 Web 与桌面的初始单位规则组件、Fog、interactive/indexed 策略一致。这是限定场景的像素/字节对照，不是所有分辨率或动画阶段的容量结论。

浏览器实测使用 Codex in-app browser：chibi-small、seed42、两个人类槽位。按钮将魏军 AP 从0恢复到2，Space 将蜀军 AP 从0恢复到2；单位拾取后，点击相邻地格使坐标从(1,3)变为(0,3)，MP从4变为3。额外检查460×820窄窗口及凭据链接切换。最终 interactive 服务器也单独验收权威移动动画与索引配置。

截图：

- [浏览器战场与选中部队](web-battlefield.jpg)
- [按钮结束回合恢复 AP](web-end-turn-ap-restored.jpg)
- [Space 结束回合恢复 AP](web-space-ap-restored.jpg)
- [窄窗口](web-narrow-window.jpg)
- [pygame 抽取前](pygame-before.png) / [抽取后](pygame-after.png)

回归覆盖桌面 UI/输入、回合资源、会话与 Hub 生命周期、原协议、展示不可变数据、Fog/领土隐私、权限及 epoch、人类/Agent 接口隔离、HTTP 素材路径、认证、重连、限速和慢客户端。命令、汇总计数与截图元数据见 `validation.json`。
