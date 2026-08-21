#!/bin/bash
# Agent 启动脚本
# 用法: ./run_agent.sh [ENV_ID] [AGENT_ID] [FACTION] [PROVIDER] [MODE] [额外参数...]
#
# 只有一个入口：rotk_agent/main.py。用哪套模型 API 由 --provider 经
# rotk_agent/profiles.py 的档案表推导，也可以用 --profile 直接指定。
#
#   ./run_agent.sh env_1 agent_1 wei vllm_qwen3_14b turn_based
#   ./run_agent.sh env_1 agent_1 shu vllm_gpt_oss   real_time
#   ./run_agent.sh env_1 agent_1 wei deepseek       turn_based --profile baseline
#
# 不接 LLM 的空跑（用脚本化回复走通全链路）：
#   ./run_agent.sh env_1 agent_1 wei fake turn_based

ENV_ID=${1:-env_1}
AGENT_ID=${2:-agent_1}
FACTION=${3:-wei}
PROVIDER=${4:-vllm_qwen3_14b}
MODE=${5:-turn_based}

# 丢掉已消费的位置参数，剩下的透传给 main.py。
# 不能用 `shift 5`：位置参数不足 5 个时它会整体失败，把原参数留在 "$@" 里泄漏到命令行末尾。
for _ in 1 2 3 4 5; do
    [ $# -gt 0 ] && shift
done

uv run rotk_agent/main.py \
    --env-id "$ENV_ID" \
    --agent-id "$AGENT_ID" \
    --faction "$FACTION" \
    --provider "$PROVIDER" \
    --mode "$MODE" \
    "$@"
