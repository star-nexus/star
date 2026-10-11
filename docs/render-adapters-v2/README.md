# Web v2：移动平滑与渲染对象复用

2026-10-11，`codex/render-adapters`。修复前为 `2c7e3a8` / `starbench-web-v1`；当前 Web 视觉版本 `starbench-web-v2`。pygame 保持 `starbench-ui-v6`，native API18/schema5 与原有 Rust 二进制保持不变。

启动与架构见[多渲染器接入](../render-adapters.md)。Python 场景准备仍使用 pygame 字体/素材支持，网页由 Three.js 绘制；Web 入口不再显示 pygame 欢迎信息，启动器不再继承外层 uv 脚本临时环境的 VIRTUAL_ENV。

## 问题与修复

旧客户端收到每个展示包便释放、重建全部单位的 InstancedMesh，选择/命令结果还重复执行该路径；单位位置只在收到服务端位置时跳变。地格每包使用 JSON 序列化比较，侧栏阵营节点反复重建，单位标签每浏览器帧重复写位置。

v2 保留 GPU 实例批次、更新改变的实例；容量不足时按2的幂增长，离开视野/死亡即时移除。保留未变化的地图数组，复用攻击线/效果和侧栏节点。单位与投射物位置在已收到的位置之间按浏览器动画帧平滑显示；选中圈、标签、拾取同步使用绘制位置。没有预测未来状态或改变规则，延迟窗口最多100ms；超过250ms的接收中断直接定位，完整基线清除旧插值状态。

## 浏览器实测

使用 Codex in-app browser、1280×720窗口（战场画布1000×648）、chibi-small、seed42、魏指挥视角、5支可见部队。修复前后均使用同一 DisplayMetrics 诊断代码；服务端默认展示20Hz、权威60Hz。

| 指标 | v1 | v2 |
| --- | ---: | ---: |
| 实际收到的状态包 | 约17–18次/秒 | 约17–18次/秒 |
| 浏览器绘制频率 | 约100 FPS | 约100 FPS |
| 同一步兵从(1,3)到(0,3)的可见位置变化帧 | 10 | 52 |
| 静止画面的 InstancedMesh 创建 | 约50个/秒持续增长 | 初次8个，此后不增长 |

数据见 [browser-before.json](browser-before.json) 和 [browser-after.json](browser-after.json)。`motion_frames` 为浏览器绘制时单位位置发生变化的帧数，`motion_packets` 为收到的位置变化包数；v2该次移动为9个位置更新包，得到52个变化帧。原来页面总体绘制并没有降到20 FPS，卡顿主要表现为移动停顿与跳变；这组测量不能代表其他浏览器、GPU或大规模单位负载。`render_cpu_p95_ms` 仅测浏览器 draw 方法 CPU 提交时间，不包含 GPU 完成或服务器性能。

手工回归包括真实单位/地格拾取、移动MP变化、鼠标结束回合与Space恢复AP、适应地图/平移/缩放、重载和窄窗口；细节见 [browser-validation.json](browser-validation.json)、[战场截图](web-battlefield.jpg)、[按钮恢复AP](web-end-turn-ap-restored.jpg)、[Space恢复AP](web-space-ap-restored.jpg)和[窄窗口](web-narrow-window.jpg)。诊断面板通过 `?perf=1` 开启，默认界面无面板。

## 可复跑验证

```bash
npm test --prefix rotk_env/rendering/web/client
PYTHONPATH=. .venv/bin/python docs/render-adapters-v1/check_desktop.py --output docs/render-adapters-v2
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest -q \
  framework/tests protocol/tests \
  rotk_env/tests/test_ui_context.py rotk_env/tests/test_ui_toolbar_clicks.py \
  rotk_env/tests/test_native_controls.py rotk_env/tests/test_native_input.py \
  rotk_env/tests/test_native_session.py rotk_env/tests/test_native_hub.py \
  rotk_env/tests/test_native_turn.py rotk_env/tests/test_turn.py \
  rotk_env/tests/test_terrain_presentation_cache.py rotk_env/tests/test_starbench_launcher.py \
  rotk_env/tests/test_render_projection.py rotk_env/tests/test_web_commands.py \
  rotk_env/tests/test_web_server.py rotk_env/tests/test_renderer_adapters.py
```

结果：412项Python回归、10项Node测试通过；桌面RGB与实际捕获字节均和合并点2598697一致，绘制不改变权威状态。Node测试核验100个显示包不新建单位GPU批次、不上传静止矩阵，容量增长/移除/拾取ID、连续插值不越界、不修改权威位置、断流/基线清理、攻击线/投射物生命周期复用、完整重同步保留地图缓冲与镜头。HTTP测试验证新增模块可加载；启动测试验证外层环境清理与Web无pygame欢迎提示。

历史v1截图/验收数据保留。Web仍未提供Agent图像观测，也未做5000单位长期容量验收；star-protocol与Agent接入方式保持不变。
