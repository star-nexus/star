# StarBench 锦标赛系统使用指南

## 系统概述

StarBench锦标赛系统是一个完整的AI模型对战平台，支持14个大语言模型在三国策略游戏中进行双循环积分赛。系统提供了从单场比赛到大规模批量并行对战的完整解决方案。

## 核心组件

1. **`tournament_schedule.json`** - 包含所有91场比赛的完整数据结构
2. **`tournament_launcher.py`** - 单场比赛启动脚本
3. **`tournament.sh`** - 简化的Shell脚本接口
4. **`batch_launcher.py`** - 批量并行启动脚本
5. **`batch_examples.sh`** - 批量启动示例脚本

## 参赛模型

| 序号 | 模型名称 | Model ID |
|------|----------|----------|
| 1 | Gemini 2.5 pro | gemini-2.5-pro |
| 2 | grok-3 beta | grok-3-beta |
| 3 | gpt-4o | gpt-4o |
| 4 | Sonnet 4 | claude-sonnet-4-20250514 |
| 5 | GLM4.5 | glm-4.5 |
| 6 | GLM-4.5-Air | glm-4.5-air |
| 7 | Kimi 2 | kimi-2 |
| 8 | DeepSeek-R1 | deepseek-r1 |
| 9 | DeepSeek-V3.1-Terminus | deepseek-v3.1-terminus |
| 10 | Qwen3-Next-80B-A3B-Instruct | qwen3-next-80b-a3b-instruct |
| 11 | Qwen3-Next-80B-A3B-Thinking | qwen3-next-80b-a3b-thinking |
| 12 | gpt-oss-20b | gpt-oss-20b |
| 13 | gpt-oss-120b | gpt-oss-120b |
| 14 | llama-33-70b-instruct | llama-33-70b-instruct |

## 使用方式

### 1. 单场比赛启动

```bash
# 查看帮助
./tournament.sh

# 启动环境测试
./tournament.sh headless turn    # 测试回合制AI vs AI
./tournament.sh headless real    # 测试实时制AI vs AI

# 启动单场比赛
./tournament.sh 1 1      # 第1场第1局
./tournament.sh 50 2     # 第50场第2局  
./tournament.sh 91 3     # 第91场第3局

# 干运行查看命令
./tournament.sh 25 1 dry
```

### 2. 批量并行启动

```bash
# 查看批量启动帮助
python batch_launcher.py --help

# 运行单场比赛
python batch_launcher.py --matches 1

# 运行多场指定比赛
python batch_launcher.py --matches 1,5,10,15

# 运行连续范围的比赛
python batch_launcher.py --start 1 --end 10

# 运行第2局游戏
python batch_launcher.py --matches 1,2,3 --game 2

# 控制并行数量（推荐不超过3）
python batch_launcher.py --start 1 --end 5 --parallel 2

# 运行所有91场比赛（谨慎使用）
python batch_launcher.py --all --parallel 3
```

### 3. 快速开始

```bash
# 运行示例脚本（推荐新手使用）
./batch_examples.sh

# 测试前3场比赛
python batch_launcher.py --matches 1,2,3 --game 1 --parallel 2

# 测试完整的BO3
python batch_launcher.py --matches 1 --game 1  # 第1局
python batch_launcher.py --matches 1 --game 2  # 第2局
python batch_launcher.py --matches 1 --game 3  # 第3局（如果需要）
```

## 比赛规则

### BO3赛制
- 每场比赛包含最多3局游戏
- Game 1: 模型A选wei，模型B选shu  
- Game 2: 模型B选wei，模型A选shu
- Game 3: 仅在前两局1-1平局时进行

### 环境隔离
- 每场比赛使用独立的env_id（如env_1_1, env_1_2等）
- 支持多场比赛并行运行而不相互影响
- 自动生成唯一的agent ID

## 高级功能

### 批量启动参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--matches` | 指定比赛编号 | `--matches 1,5,10` |
| `--start --end` | 连续范围 | `--start 1 --end 10` |
| `--all` | 所有91场比赛 | `--all` |
| `--game` | 游戏编号(1-3) | `--game 2` |
| `--parallel` | 并行数量 | `--parallel 3` |

### 结果追踪
- 自动保存批量执行结果到JSON文件
- 时间戳格式：`batch_results_20250928_143022.json`
- 包含成功/失败状态和详细信息

### 错误处理
- 自动清理异常退出的进程
- 支持Ctrl+C中断并清理
- 详细的错误日志和状态报告

## 系统要求

- Python 3.8+
- uv包管理器
- 足够的系统资源（建议每个并行比赛至少1GB内存）
- 稳定的网络连接（用于模型API调用）

## 监控和调试

### 实时监控
```bash
# 查看进程状态
ps aux | grep rotk

# 查看网络连接
netstat -an | grep 8765

# 监控资源使用
htop
```

### 日志查看
- 每个环境和agent的输出都会显示对应的env_id
- 格式：`[ENV-env_1_1] 启动环境...`
- 批量执行会显示整体进度和统计信息

## 注意事项

1. **资源管理**: 并行数量不要超过系统承受能力，推荐不超过3个
2. **网络稳定**: 确保模型API访问稳定
3. **存储空间**: 确保有足够空间存储结果和日志
4. **进程清理**: 异常退出时检查是否有残留进程

## 故障排除

### 常见问题

1. **端口冲突**: 每个env_id使用不同端口，一般不会冲突
2. **内存不足**: 减少并行数量或增加系统内存
3. **网络超时**: 检查模型API访问配置
4. **进程残留**: 使用`killall python`清理（谨慎使用）

### 重启方法
```bash
# 停止所有相关进程
pkill -f "rotk_env\|rotk_agent"

# 重新启动批量任务
python batch_launcher.py --matches 1,2,3 --parallel 1
```

## 完整工作流示例

```bash
# 1. 测试环境
./tournament.sh headless turn

# 2. 运行小规模测试
python batch_launcher.py --matches 1,2 --parallel 1

# 3. 查看结果
cat batch_results_*.json

# 4. 运行大规模批量
python batch_launcher.py --start 1 --end 20 --parallel 2

# 5. 运行完整锦标赛
python batch_launcher.py --all --parallel 3
```

现在你可以开始使用StarBench锦标赛系统进行大规模AI模型对战测试了！