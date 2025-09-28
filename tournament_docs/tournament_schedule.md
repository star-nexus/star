# 三国策略游戏 AI 模型锦标赛

## 赛制说明

**赛制**: 双循环积分赛  
**参赛模型**: 14个  
**对战形式**: BO3 (Best of 3)  
**积分规则**: 
- 胜利一局: 3分
- 平局: 1分
- 失败: 0分

每轮BO3完成后，两个模型交换阵营再进行一轮BO3，确保公平性。

## 参赛模型列表

| 序号 | 模型名称 | Agent ID |
|------|----------|----------|
| 1 | Gemini 2.5 pro | agent_gemini25_pro |
| 2 | grok-3 beta | agent_grok3_beta |
| 3 | gpt-4o | agent_gpt4o |
| 4 | Sonnet 4 | agent_sonnet4 |
| 5 | GLM4.5 | agent_glm45 |
| 6 | GLM-4.5-Air | agent_glm45_air |
| 7 | Kimi 2 | agent_kimi2 |
| 8 | DeepSeek-R1 | agent_deepseek_r1 |
| 9 | DeepSeek-V3.1-Terminus | agent_deepseek_v31 |
| 10 | Qwen3-Next-80B-A3B-Instruct | agent_qwen3_instruct |
| 11 | Qwen3-Next-80B-A3B-Thinking | agent_qwen3_thinking |
| 12 | gpt-oss-20b | agent_gpt_oss_20b |
| 13 | gpt-oss-120b | agent_gpt_oss_120b |
| 14 | llama-33-70b-instruct | agent_llama33_70b |

## 对战安排

### 第一循环 (91场对战)

每个模型与其他13个模型各对战一次，每次对战包含2轮BO3：
- 第一轮BO3：模型A选wei，模型B选shu
- 第二轮BO3：模型A选shu，模型B选wei

**总计**: 13 × 14 ÷ 2 = 91场对战，每场对战2轮BO3，共182轮BO3，546局游戏

### 第二循环 (91场对战)

重复第一循环的所有对战组合

**总计**: 91场对战，182轮BO3，546局游戏

## 启动命令模板

### 启动环境服务器
```bash
uv run rotk_env/main.py
```

### 启动Agent模板
```bash
# Wei阵营
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id {agent_id}_wei \
    --faction "wei" \
    --provider infinigence \
    --model_id {model_id}

# Shu阵营  
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id {agent_id}_shu \
    --faction "shu" \
    --provider infinigence \
    --model_id {model_id}
```

## 具体对战时间表

### 第一轮对战 (Model 1 vs Others)

#### 1. Gemini 2.5 pro vs grok-3 beta
**第一轮BO3**: Gemini选wei，grok选shu
```bash
# Terminal 1: 启动Gemini (Wei)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gemini25_pro_wei \
    --faction "wei" \
    --provider infinigence \
    --model_id gemini-2.5-pro

# Terminal 2: 启动grok (Shu)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_grok3_beta_shu \
    --faction "shu" \
    --provider infinigence \
    --model_id grok-3-beta
```

**第二轮BO3**: Gemini选shu，grok选wei
```bash
# Terminal 1: 启动Gemini (Shu)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gemini25_pro_shu \
    --faction "shu" \
    --provider infinigence \
    --model_id gemini-2.5-pro

# Terminal 2: 启动grok (Wei)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_grok3_beta_wei \
    --faction "wei" \
    --provider infinigence \
    --model_id grok-3-beta
```

#### 2. Gemini 2.5 pro vs gpt-4o
**第一轮BO3**: Gemini选wei，gpt-4o选shu
```bash
# Terminal 1: 启动Gemini (Wei)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gemini25_pro_wei \
    --faction "wei" \
    --provider infinigence \
    --model_id gemini-2.5-pro

# Terminal 2: 启动gpt-4o (Shu)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gpt4o_shu \
    --faction "shu" \
    --provider infinigence \
    --model_id gpt-4o
```

**第二轮BO3**: Gemini选shu，gpt-4o选wei
```bash
# Terminal 1: 启动Gemini (Shu)  
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gemini25_pro_shu \
    --faction "shu" \
    --provider infinigence \
    --model_id gemini-2.5-pro

# Terminal 2: 启动gpt-4o (Wei)
uv run rotk_agent/qwen3_agent.py \
    --env-id env_1 \
    --agent-id agent_gpt4o_wei \
    --faction "wei" \
    --provider infinigence \
    --model_id gpt-4o
```

*[继续类似的对战安排...]*

## 积分统计表格模板

### 第一循环结果

| 排名 | 模型名称 | 胜场 | 平场 | 负场 | 积分 | 胜率 |
|------|----------|------|------|------|------|------|
| 1 | - | - | - | - | - | - |
| 2 | - | - | - | - | - | - |
| 3 | - | - | - | - | - | - |
| 4 | - | - | - | - | - | - |
| 5 | - | - | - | - | - | - |
| 6 | - | - | - | - | - | - |
| 7 | - | - | - | - | - | - |
| 8 | - | - | - | - | - | - |
| 9 | - | - | - | - | - | - |
| 10 | - | - | - | - | - | - |
| 11 | - | - | - | - | - | - |
| 12 | - | - | - | - | - | - |
| 13 | - | - | - | - | - | - |
| 14 | - | - | - | - | - | - |

### 第二循环结果

| 排名 | 模型名称 | 胜场 | 平场 | 负场 | 积分 | 胜率 |
|------|----------|------|------|------|------|------|
| 1 | - | - | - | - | - | - |
| 2 | - | - | - | - | - | - |
| 3 | - | - | - | - | - | - |
| 4 | - | - | - | - | - | - |
| 5 | - | - | - | - | - | - |
| 6 | - | - | - | - | - | - |
| 7 | - | - | - | - | - | - |
| 8 | - | - | - | - | - | - |
| 9 | - | - | - | - | - | - |
| 10 | - | - | - | - | - | - |
| 11 | - | - | - | - | - | - |
| 12 | - | - | - | - | - | - |
| 13 | - | - | - | - | - | - |
| 14 | - | - | - | - | - | - |

### 总积分榜

| 排名 | 模型名称 | 总胜场 | 总平场 | 总负场 | 总积分 | 总胜率 |
|------|----------|--------|--------|--------|--------|--------|
| 🥇 | - | - | - | - | - | - |
| 🥈 | - | - | - | - | - | - |
| 🥉 | - | - | - | - | - | - |
| 4 | - | - | - | - | - | - |
| 5 | - | - | - | - | - | - |
| 6 | - | - | - | - | - | - |
| 7 | - | - | - | - | - | - |
| 8 | - | - | - | - | - | - |
| 9 | - | - | - | - | - | - |
| 10 | - | - | - | - | - | - |
| 11 | - | - | - | - | - | - |
| 12 | - | - | - | - | - | - |
| 13 | - | - | - | - | - | - |
| 14 | - | - | - | - | - | - |

## 注意事项

1. **环境准备**: 每场比赛前确保环境服务器已启动
2. **Agent配置**: 根据实际的模型API配置调整provider和model_id参数
3. **结果记录**: 每轮BO3结束后及时记录结果到积分表
4. **错误处理**: 如遇连接问题，重启对应的Agent即可
5. **公平性**: 确保每轮比赛后都交换阵营，保证测试的公平性

## 预计时间

- **单局游戏时间**: 约10-15分钟
- **单轮BO3时间**: 约30-45分钟  
- **单场对战时间**: 约1-1.5小时 (包含交换阵营)
- **第一循环总时间**: 约91-136.5小时
- **完整锦标赛时间**: 约182-273小时

建议分阶段进行，每天安排8-12场对战。