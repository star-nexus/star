# 三国策略游戏锦标赛启动系统

## 系统组成

1. **`tournament_schedule.json`** - 完整的91场比赛赛程数据
2. **`tournament_launcher.py`** - Python启动脚本，读取JSON并生成启动命令
3. **`tournament.sh`** - Shell脚本，简化启动流程

## 使用方法

### 启动游戏环境
```bash
./tournament.sh env
```

### 启动比赛
```bash
./tournament.sh X Y          # 启动第X场比赛的第Y局
```

### 干运行（查看启动命令但不执行）
```bash
./tournament.sh X Y dry      # 查看第X场比赛第Y局的启动命令
```

## 使用示例

```bash
# 查看帮助
./tournament.sh

# 启动环境
./tournament.sh env

# 第1场比赛
./tournament.sh 1 1          # 第1场第1局: Gemini 2.5 pro(wei) vs grok-3 beta(shu)
./tournament.sh 1 2          # 第1场第2局: grok-3 beta(wei) vs Gemini 2.5 pro(shu)
./tournament.sh 1 3          # 第1场第3局: 如果前两局1-1平局才需要

# 第50场比赛
./tournament.sh 50 1         # 第50场第1局
./tournament.sh 50 2         # 第50场第2局

# 最后一场比赛
./tournament.sh 91 1         # 第91场第1局: gpt-oss-120b vs llama-33-70b-instruct
./tournament.sh 91 2         # 第91场第2局
./tournament.sh 91 3         # 第91场第3局

# 干运行 - 只查看命令
./tournament.sh 25 1 dry     # 查看第25场第1局的启动命令
```

## 赛程安排

- **总场次**: 91场比赛（14个模型两两对战）
- **每场比赛**: BO3格式（最多3局）
- **总局数**: 182-273局（取决于平局数量）
- **阵营轮换**: 每场比赛的第1局和第2局会交换阵营，确保公平

### 比赛对阵表（部分）

| 场次 | 模型A | 模型B |
|------|-------|-------|
| 1 | Gemini 2.5 pro | grok-3 beta |
| 2 | Gemini 2.5 pro | gpt-4o |
| 3 | Gemini 2.5 pro | Sonnet 4 |
| ... | ... | ... |
| 89 | gpt-oss-20b | gpt-oss-120b |
| 90 | gpt-oss-20b | llama-33-70b-instruct |
| 91 | gpt-oss-120b | llama-33-70b-instruct |

## 实际使用流程

1. **准备环境**
   ```bash
   # 启动游戏环境（保持运行）
   ./tournament.sh env
   ```

2. **开始比赛**
   ```bash
   # 在新的终端中，先查看启动命令
   ./tournament.sh 1 1 dry
   
   # 确认无误后，启动比赛
   ./tournament.sh 1 1
   ```

3. **脚本会显示启动命令并询问是否自动启动**
   - 选择 `y` : 自动在后台启动两个agent
   - 选择 `n` : 显示命令，需要手动在两个终端中运行

4. **比赛结束后进行下一局**
   ```bash
   ./tournament.sh 1 2    # 第1场第2局
   ```

## 文件说明

### `tournament_schedule.json`
包含所有91场比赛的完整数据：
- 参赛模型信息和ID映射
- 每场比赛的对阵信息
- 每局游戏的阵营分配
- 模型对应的model_id

### `tournament_launcher.py`
Python启动脚本功能：
- 读取JSON赛程文件
- 根据场次和局数查找对应比赛
- 生成正确的agent启动命令
- 支持干运行模式
- 自动生成合适的agent ID

### `tournament.sh`
Shell脚本功能：
- 简化命令行参数
- 调用Python脚本
- 提供帮助信息
- 支持环境启动

## 注意事项

1. **第3局规则**: 只有在前两局1-1平局时才需要进行第3局
2. **环境依赖**: 需要确保 `uv` 和相关Python环境已正确配置
3. **并发限制**: 同时只能运行一场比赛（两个agent）
4. **模型配置**: 所有模型都使用 `infinigence` 作为provider，实际使用时可能需要调整

## 快速开始

```bash
# 1. 确保脚本可执行
chmod +x tournament.sh

# 2. 启动环境（保持运行）
./tournament.sh env

# 3. 在新终端中启动第一场比赛
./tournament.sh 1 1

# 4. 根据比赛结果继续后续局次
./tournament.sh 1 2
# 如果需要的话
./tournament.sh 1 3
```

现在你可以用简单的 `./tournament.sh X Y` 命令来启动任意场次的比赛了！