#!/bin/bash
# 通用 Agent 启动脚本
# 用法: ./run_agent_generic.sh [ENV_ID] [AGENT_ID] [FACTION] [PROVIDER] [MODE]

ENV_ID=${1:-env_1}
AGENT_ID=${2:-agent_1}
FACTION=${3:-wei}
PROVIDER=${4:-vllm_qwen3_14b}
MODE=${5:-turn_based}

# echo "Starting Agent: $AGENT_ID ($FACTION) using $PROVIDER connecting to $ENV_ID"

# 根据模式选择 Agent 入口
AGENT_ENTRY="rotk_agent/qwen3_agent_turn.py"
if [ "$MODE" = "real_time" ]; then
    AGENT_ENTRY="rotk_agent/qwen3_agent.py"
fi

# 注意：如果需要测试 gpt_oss_agent 或其他，可能需要更复杂的逻辑或在该脚本外层控制
uv run "$AGENT_ENTRY" \
    --env-id "$ENV_ID" \
    --agent-id "$AGENT_ID" \
    --faction "$FACTION" \
    --provider "$PROVIDER"
