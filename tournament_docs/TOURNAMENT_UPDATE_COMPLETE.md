# Tournament 启动工具更新说明

## 主要更新

### 1. tournament_launcher.py
- ✅ 添加了 `launch_env()` 函数来启动游戏环境
- ✅ 支持 `--mode` 参数选择游戏模式（turn_based/real_time）
- ✅ 改进了进程管理和清理
- ✅ 修复了干运行模式下的模式参数传递

### 2. tournament.sh
- ✅ 支持模式参数：`./tournament.sh X Y [turn/real] [dry]`
- ✅ 更新帮助信息，包含所有使用场景
- ✅ 改进参数解析逻辑
- ✅ 支持组合参数：模式+干运行

### 3. Makefile
- ✅ 添加环境测试命令：`make test-turn`, `make test-real`, `make test-both`
- ✅ 支持实时制比赛：`make real-X-Y`
- ✅ 支持实时制干运行：`make dry-real-X-Y`
- ✅ 更新帮助信息，包含所有新功能

## 使用示例

### Shell 脚本方式
```bash
# 回合制模式
./tournament.sh 1 1                # 默认回合制
./tournament.sh 1 1 turn           # 显式指定回合制
./tournament.sh 1 1 turn dry       # 回合制干运行

# 实时制模式
./tournament.sh 1 1 real           # 实时制
./tournament.sh 1 1 real dry       # 实时制干运行

# 环境测试
./tournament.sh headless turn      # 测试回合制
./tournament.sh headless real      # 测试实时制
./tournament.sh headless both      # 测试两种模式
```

### Makefile 方式
```bash
# 回合制比赛
make 1-1                           # 第1场第1局 (回合制)
make dry-1-1                       # 干运行查看命令

# 实时制比赛
make real-1-1                      # 第1场第1局 (实时制)
make dry-real-1-1                  # 实时制干运行

# 环境测试
make test-turn                     # 测试回合制
make test-real                     # 测试实时制
make test-both                     # 测试两种模式

# 帮助信息
make help                          # 查看所有可用命令
```

## 验证结果

### ✅ 基本功能测试
- [x] Shell脚本帮助信息正确显示
- [x] Makefile帮助信息正确显示
- [x] 回合制干运行正常工作
- [x] 实时制干运行正常工作
- [x] 模式参数正确传递到环境启动命令

### ✅ 参数解析测试
- [x] `./tournament.sh 1 1 turn dry` - 回合制干运行
- [x] `./tournament.sh 1 1 real dry` - 实时制干运行
- [x] `make dry-1-1` - Makefile回合制干运行
- [x] `make dry-real-1-1` - Makefile实时制干运行

### ✅ 环境启动命令验证
- [x] 回合制：`--mode turn_based`
- [x] 实时制：`--mode real_time`
- [x] 环境ID格式：`env_match_{match_id}_game_{game_id}`

## 下一步

所有更新已完成并通过测试。现在用户可以：

1. 使用 `./tournament.sh` 或 `make` 启动比赛
2. 选择回合制或实时制模式
3. 使用干运行模式查看启动命令
4. 通过环境测试验证系统功能

系统已经可以支持完整的锦标赛启动流程！