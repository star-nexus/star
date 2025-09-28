# StarBench 并行策略详细指南

## 概述

StarBench 批量启动器支持三种不同的并行策略，让你可以根据具体需求和系统资源来优化比赛执行效率。

## 并行策略详解

### 1. Match 并行策略 (`--strategy match`) **[默认]**

**工作原理:**
- 并行运行不同的 match（比赛）
- 同一个 match 内的不同 game（局次）按顺序执行
- 每个 match 是一个独立的执行单元

**优点:**
- ✅ 资源隔离好，不同 match 之间互不影响
- ✅ 内存使用相对稳定
- ✅ 适合长时间运行，稳定性高
- ✅ 便于问题定位和调试

**适用场景:**
- 需要运行大量不同的 match
- 每个 match 只需要运行 1-2 局游戏
- 系统资源中等，追求稳定性
- 长时间批量运行

**示例命令:**
```bash
# 并行运行 5 个不同的 match，每个 match 运行第 1 局
python batch_launcher.py --start 1 --end 5 --game 1 --parallel 5 --strategy match

# 运行指定的几个 match
python batch_launcher.py --matches 1,5,10,20,30 --game 1 --parallel 3 --strategy match
```

### 2. Game 并行策略 (`--strategy game`)

**工作原理:**
- 一个 match 一个 match 地处理
- 在每个 match 内部，并行运行不同的 game（局次）
- 适合 BO3 格式的完整比赛

**优点:**
- ✅ 快速完成单个 match 的所有局次
- ✅ 适合 BO3 决赛制度
- ✅ 可以快速看到每个 match 的最终结果
- ✅ 并行度适中，资源需求可控

**适用场景:**
- 需要完整运行每个 match 的所有 3 局
- match 数量不多，但要快速得到结果
- 想要按 match 为单位进行进度跟踪
- BO3 淘汰赛模式

**示例命令:**
```bash
# 完整运行前 3 个 match，每个 match 的 3 局并行执行
python batch_launcher.py --matches 1,2,3 --game 0 --parallel 3 --strategy game

# 运行单个 match 的所有局次
python batch_launcher.py --matches 10 --game 0 --parallel 3 --strategy game
```

### 3. Both 并行策略 (`--strategy both`)

**工作原理:**
- 同时并行 match 和 game
- 把所有任务（match × game 组合）放入统一的线程池
- 最大化并行度和资源利用率

**优点:**
- ✅ 最高的并行度
- ✅ 最快的整体执行速度
- ✅ 最大化系统资源利用率
- ✅ 适合高性能系统

**注意事项:**
- ⚠️ 对系统资源要求高
- ⚠️ 可能导致系统负载过高
- ⚠️ 需要仔细调整并行数
- ⚠️ 问题定位可能相对困难

**适用场景:**
- 高性能服务器环境
- 需要最快速度完成大量比赛
- 系统资源充足
- 短时间内完成大量任务

**示例命令:**
```bash
# 最大化并行度运行前 10 个 match 的所有局次
python batch_launcher.py --start 1 --end 10 --game 0 --parallel 15 --strategy both

# 全量运行，高并行度
python batch_launcher.py --all --game 0 --parallel 20 --strategy both
```

## 并行数选择指南

### 基于系统配置

| 系统配置 | 推荐并行数 | Match策略 | Game策略 | Both策略 |
|---------|-----------|----------|----------|----------|
| 4核心/8GB | 2-3 | ✅ 推荐 | ✅ 推荐 | ⚠️ 小心 |
| 8核心/16GB | 4-6 | ✅ 推荐 | ✅ 推荐 | ✅ 适用 |
| 16核心/32GB | 6-10 | ✅ 适用 | ✅ 推荐 | ✅ 推荐 |
| 32核心/64GB+ | 10-20 | ✅ 适用 | ✅ 适用 | ✅ 推荐 |

### 基于任务规模

| 任务规模 | Match数量 | Game设置 | 推荐策略 | 推荐并行数 |
|---------|----------|----------|----------|-----------|
| 小规模测试 | 1-5 | --game 1 | match | 2-3 |
| 中等规模 | 5-20 | --game 0 | game | 3-5 |
| 大规模运行 | 20-50 | --game 0 | both | 5-10 |
| 全量运行 | 91 | --game 0 | both | 8-15 |

## 实际使用示例

### 场景1: 快速测试
```bash
# 目标: 快速验证系统工作正常
python batch_launcher.py --matches 1,2 --game 1 --parallel 2 --strategy match
```

### 场景2: 完整的小规模比赛
```bash
# 目标: 运行前10个match的完整BO3比赛
python batch_launcher.py --start 1 --end 10 --game 0 --parallel 3 --strategy game
```

### 场景3: 高效大规模运行
```bash
# 目标: 最快速度完成大量比赛
python batch_launcher.py --start 1 --end 50 --game 0 --parallel 10 --strategy both
```

### 场景4: 全量锦标赛
```bash
# 目标: 运行完整的91场比赛锦标赛
python batch_launcher.py --all --game 0 --parallel 8 --strategy both
```

## 资源使用估算

### 内存使用
- 每个并行任务: ~200-500MB
- Match策略: `并行数 × 500MB`
- Game策略: `min(3, 并行数) × 500MB × match数量`
- Both策略: `并行数 × 500MB`

### CPU使用
- 每个游戏环境: 1个CPU核心的50-80%
- AI Agent: 1个CPU核心的20-40%
- 建议并行数不超过CPU核心数的1.5倍

### 存储空间
- 每局游戏: 1-5MB日志文件
- 完整BO3: 3-15MB
- 91场完整比赛: 300-1500MB
- 建议预留2GB存储空间

## 性能优化建议

### 1. 逐步调优
```bash
# 从小规模开始
python batch_launcher.py --matches 1 --game 1 --parallel 1 --strategy match

# 逐步增加并行数
python batch_launcher.py --matches 1,2 --game 1 --parallel 2 --strategy match

# 测试不同策略
python batch_launcher.py --matches 1,2 --game 0 --parallel 2 --strategy game
```

### 2. 监控系统资源
```bash
# 运行时监控系统负载
htop  # 或 top

# 监控内存使用
free -h

# 监控磁盘IO
iostat -x 1
```

### 3. 根据结果调整
- 如果CPU使用率 < 70%：可以增加并行数
- 如果内存不足：减少并行数或改用match策略
- 如果磁盘IO过高：减少并行数
- 如果频繁出错：减少并行数或改用更稳定的策略

## 故障排查

### 常见问题及解决方案

1. **内存不足**
   ```
   解决方案: 
   - 减少 --parallel 数值
   - 使用 match 策略替代 both 策略
   ```

2. **进程启动失败**
   ```
   解决方案:
   - 检查环境配置
   - 减少并行数
   - 使用 match 策略确保资源隔离
   ```

3. **系统负载过高**
   ```
   解决方案:
   - 降低 --parallel 数值
   - 使用 game 策略减少同时运行的任务数
   ```

4. **比赛结果不一致**
   ```
   解决方案:
   - 使用 match 策略确保隔离性
   - 检查环境ID是否正确分配
   - 验证没有端口冲突
   ```

## 最佳实践总结

1. **开始时保守**: 从小并行数和match策略开始
2. **逐步调优**: 根据系统表现逐步增加并行数
3. **监控资源**: 实时监控CPU、内存、磁盘使用情况
4. **选择合适策略**: 根据任务规模和系统配置选择策略
5. **预留资源**: 不要使用100%的系统资源，预留缓冲
6. **定期检查**: 长时间运行时定期检查系统状态和结果质量

记住：最佳的配置是在你的具体硬件环境下通过实际测试得出的！