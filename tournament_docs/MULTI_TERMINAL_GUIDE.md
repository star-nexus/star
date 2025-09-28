# Multi-Terminal Tournament Launcher

## 功能特点

✅ **完全独立**: 不依赖 `tournament_launcher.py`，完全用shell脚本实现  
✅ **多终端启动**: 自动在不同终端启动环境和agents  
✅ **跨平台支持**: 支持macOS、Linux系统的多种终端  
✅ **智能检测**: 自动检测系统最适合的终端类型  
✅ **灵活配置**: 支持多场次、多局数、不同模式  
✅ **干运行模式**: 查看将要执行的命令而不实际启动  

## 使用方法

### 基本用法

```bash
# 启动单场比赛的单局
./multi_terminal_launcher.sh --match 1 --game 1

# 启动单场比赛的所有3局
./multi_terminal_launcher.sh --match 1

# 启动多个比赛场次
./multi_terminal_launcher.sh --matches 1,2,3

# 使用实时制模式
./multi_terminal_launcher.sh --match 1 --mode real_time

# 干运行查看命令（推荐先用这个）
./multi_terminal_launcher.sh --match 1 --dry-run
```

### 高级选项

```bash
# 指定终端类型
./multi_terminal_launcher.sh --match 1 --terminal-type terminal

# 组合选项
./multi_terminal_launcher.sh --matches 1,2 --game 2 --mode real_time --dry-run
```

## 支持的终端类型

| 系统 | 终端类型 | 说明 |
|------|----------|------|
| macOS | `terminal` | 系统默认终端 |
| macOS | `iterm` | iTerm2 (需要安装) |
| macOS | `xterm` | XTerm |
| Linux | `gnome` | GNOME Terminal |
| Linux | `xterm` | XTerm |
| 通用 | `auto` | 自动检测最佳终端 |

## 实际启动效果

当你运行命令时，脚本会：

1. **启动游戏环境** - 在一个新终端中启动环境服务器
2. **启动Wei Agent** - 在另一个新终端中启动第一个AI智能体
3. **启动Shu Agent** - 在第三个新终端中启动第二个AI智能体

每个终端都有清晰的标题标识：
- `ENV-env_match_1_game_1` - 环境进程
- `WEI-agent_xxx_wei_xxx` - Wei阵营智能体
- `SHU-agent_xxx_shu_xxx` - Shu阵营智能体

## 典型工作流

### 1. 先进行干运行测试
```bash
./multi_terminal_launcher.sh --match 1 --game 1 --dry-run
```
检查命令是否正确，确认对战双方信息。

### 2. 启动实际比赛
```bash
./multi_terminal_launcher.sh --match 1 --game 1
```

### 3. 监控比赛进度
在启动的各个终端中观察：
- 环境终端：游戏状态、回合进展
- Agent终端：AI决策过程、行动日志

### 4. 批量启动多场比赛
```bash
# 谨慎使用！会启动很多终端窗口
./multi_terminal_launcher.sh --matches 1,2,3 --mode turn_based
```

## 注意事项

⚠️ **终端窗口数量**: 每局比赛启动3个终端，多局/多场会产生很多窗口  
⚠️ **系统资源**: 多个并行比赛会消耗较多CPU和内存  
⚠️ **进程管理**: 手动关闭终端窗口来停止对应的进程  
⚠️ **环境冲突**: 不同比赛使用不同的env_id避免冲突  

## 故障排除

### 终端启动失败
如果自动检测的终端类型不工作，手动指定：
```bash
./multi_terminal_launcher.sh --match 1 --terminal-type terminal
```

### 权限问题
确保脚本有执行权限：
```bash
chmod +x multi_terminal_launcher.sh
```

### 路径问题
确保在项目根目录执行脚本：
```bash
cd /path/to/starbench
./multi_terminal_launcher.sh --match 1
```

## 与其他启动方式的对比

| 方式 | 优点 | 缺点 |
|------|------|------|
| `multi_terminal_launcher.sh` | 可视化监控，进程隔离 | 窗口多，手动管理 |
| `batch_launcher.py` | 自动化，统计报告 | 输出混合，难以调试 |
| `tournament.sh` | 简单快速 | 需要手动启动agents |

选择最适合你需求的启动方式！