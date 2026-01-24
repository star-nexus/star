#!/bin/bash
# 通用 Agent 启动脚本
# 用法: ./run_agent_generic.sh [ENV_ID] [AGENT_ID] [FACTION] [PROVIDER] [MODE]
#       ./run_agent_generic.sh --print-agent [ENV_ID] [AGENT_ID] [FACTION] [PROVIDER] [MODE]  # 仅打印 AGENT_ENTRY 并退出，供测试用
#
# 根据 PROVIDER 与 MODE 选择 Agent 入口：
#   - provider 包含 nvidia（如 vllm_nvidia_9b）→ nv_nemotron_agent / nv_nemotron_agent_turn
#   - provider 包含 gpt（如 vllm_gpt_oss）    → gpt_oss_agent / gpt_oss_agent_turn
#   - 其余（qwen、siliconflow 等）            → qwen3_agent / qwen3_agent_turn

PRINT_ONLY=0
if [ "$1" = "--print-agent" ]; then
    PRINT_ONLY=1
    shift
fi

ENV_ID=${1:-env_1}
AGENT_ID=${2:-agent_1}
FACTION=${3:-wei}
PROVIDER=${4:-vllm_qwen3_14b}
MODE=${5:-turn_based}

# 根据 PROVIDER 与 MODE 选择 Agent 入口
if [ "$MODE" = "real_time" ]; then
    if [[ "$PROVIDER" == *nvidia* ]]; then
        AGENT_ENTRY="rotk_agent/nv_nemotron_agent.py"
    elif [[ "$PROVIDER" == *gpt* ]]; then
        AGENT_ENTRY="rotk_agent/gpt_oss_agent.py"
    else
        AGENT_ENTRY="rotk_agent/qwen3_agent.py"
    fi
else
    # turn_based
    if [[ "$PROVIDER" == *nvidia* ]]; then
        AGENT_ENTRY="rotk_agent/nv_nemotron_agent_turn.py"
    elif [[ "$PROVIDER" == *gpt* ]]; then
        AGENT_ENTRY="rotk_agent/gpt_oss_agent_turn.py"
    else
        AGENT_ENTRY="rotk_agent/qwen3_agent_turn.py"
    fi
fi

if [ "$PRINT_ONLY" = "1" ]; then
    echo "$AGENT_ENTRY"
    exit 0
fi

uv run "$AGENT_ENTRY" \
    --env-id "$ENV_ID" \
    --agent-id "$AGENT_ID" \
    --faction "$FACTION" \
    --provider "$PROVIDER"
