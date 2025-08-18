# 结算报告模块 (Settlement Report Module)

## 概述

结算报告模块是一个完整的游戏数据收集和分析系统，在游戏结束时自动生成详细的结算报告。该模块参考了其他项目的实验报告系统，提供了全面的游戏统计数据和可扩展的架构。

## 功能特性

### 🎯 核心功能
- **自动数据收集**: 游戏结束时自动收集所有相关统计数据
- **多维度分析**: 涵盖单位、战斗、地图、性能等多个维度
- **文件导出**: 支持JSON和CSV两种格式的自动保存
- **可视化展示**: 在游戏结束场景中提供美观的报告界面
- **滚动支持**: 支持鼠标滚轮滚动查看长报告内容

### 📊 统计维度

#### 1. 基础游戏数据
- 实验ID（时间戳）
- 游戏时长
- 总回合数
- 胜利阵营
- 胜利类型（全歼/半歼/平局）

#### 2. 单位统计
- 各阵营单位总数
- 存活/损失单位数量
- 总生命值统计
- 单位详细信息

#### 3. 战斗统计
- 总战斗次数
- 各阵营伤亡统计
- 伤害统计（造成/承受）
- 战斗历史记录

#### 4. 地图统计
- 地图尺寸和总地块数
- 地形分布统计
- 领土控制情况
- 工事等级统计

#### 5. 性能统计（占位）
- 帧率统计
- 内存使用情况
- 渲染性能
- 系统性能

#### 6. 待实现功能（占位）
- 模型信息
- 策略评分
- 思考模式
- 响应次数

## 架构设计

### 组件结构

```
SettlementReport (主组件)
├── BattleStatistics (战斗统计)
├── MapStatistics (地图统计)
└── PerformanceStatistics (性能统计)
```

### 系统架构

```
SettlementReportSystem (数据收集)
└── SettlementReportRenderSystem (界面渲染)
```

## 使用方法

### 1. 自动集成

结算报告系统已自动集成到游戏场景中，无需手动调用。当游戏结束时，系统会自动：

1. 检测游戏结束状态
2. 收集所有统计数据
3. 生成结算报告
4. 保存到文件
5. 在游戏结束场景中显示

### 2. 手动触发（可选）

如果需要手动触发报告生成：

```python
# 获取结算报告系统
settlement_system = None
for system in world.systems:
    if isinstance(system, SettlementReportSystem):
        settlement_system = system
        break

# 手动生成报告
if settlement_system:
    settlement_system._generate_settlement_report()
```

### 3. 自定义统计

可以通过扩展组件来添加自定义统计数据：

```python
# 在SettlementReport组件中添加新字段
@dataclass
class SettlementReport(SingletonComponent):
    # ... 现有字段 ...
    custom_statistics: Dict[str, Any] = field(default_factory=dict)
```

## 文件输出

### 1. JSON报告

位置: `settlement_reports/settlement_YYYYMMDD_HHMMSS.json`

包含完整的游戏统计数据，便于程序读取和分析。

### 2. CSV数据

位置: `settlement_reports/settlement_results.csv`

包含关键指标的表格数据，便于在Excel等工具中分析。

### 3. 控制台输出

在游戏结束时，系统会在控制台输出格式化的报告摘要。

## 扩展指南

### 1. 添加新的统计维度

1. 在 `settlement_report.py` 中定义新的组件
2. 在 `SettlementReportSystem` 中添加数据收集逻辑
3. 在 `SettlementReportRenderSystem` 中添加渲染逻辑

### 2. 实现占位功能

当前标记为"占位"的功能包括：

- **模型信息**: 记录各阵营使用的AI模型
- **策略评分**: 评估各阵营的策略质量
- **思考模式**: 记录是否启用深度思考
- **响应次数**: 统计各阵营的响应频率

这些功能可以在相应的系统实现后，通过修改 `_collect_placeholder_data()` 方法来集成。

### 3. 自定义报告格式

可以通过修改以下方法来自定义报告格式：

- `_save_report_to_files()`: 自定义文件保存格式
- `_print_report_summary()`: 自定义控制台输出格式
- 渲染方法: 自定义UI显示样式

## 性能考虑

- 报告生成只在游戏结束时执行一次
- 使用缓存避免重复计算
- 异步文件保存避免阻塞主线程
- 渲染系统使用字体缓存优化性能

## 故障排除

### 常见问题

1. **报告未生成**
   - 检查游戏是否正常结束
   - 确认 `SettlementReportSystem` 已添加到世界

2. **文件保存失败**
   - 检查目录权限
   - 确认磁盘空间充足

3. **渲染显示异常**
   - 检查字体文件
   - 确认pygame版本兼容性

### 调试模式

启用调试输出：

```python
# 在SettlementReportSystem中添加
print(f"[DEBUG] 数据收集过程: {data}")
```

## 版本历史

- **v1.0.0**: 初始版本，包含基础统计功能
- **v1.1.0**: 添加地图统计和性能统计
- **v1.2.0**: 集成UI渲染系统
- **v1.3.0**: 添加滚动支持和占位功能

## 贡献指南

欢迎贡献代码改进和功能扩展！请遵循以下原则：

1. 保持向后兼容性
2. 添加适当的文档和注释
3. 遵循现有的代码风格
4. 包含测试用例（如果适用）

## 许可证

本模块遵循项目的整体许可证条款。
