#!/bin/bash
# 运行优化版 Agent 的快捷脚本

echo "🚀 启动优化版 qwen3_agent..."
echo "==============================================="
echo "📋 配置信息:"
echo "   - LLM Provider: ${LLM_PROVIDER:-openai}"
echo "   - Agent Faction: ${AGENT_FACTION:-wei}"
echo "   - Config File: .configs.toml"
echo "==============================================="

# 检查配置文件
if [ ! -f ".configs.toml" ]; then
    echo "❌ 错误: 找不到 .configs.toml 配置文件"
    echo "请确保在项目根目录运行此脚本"
    exit 1
fi

# 设置默认环境变量
export LLM_PROVIDER=${LLM_PROVIDER:-deepseek}
export AGENT_FACTION=${AGENT_FACTION:-wei}

echo "🎮 正在启动优化版 Agent..."
echo ""

# 运行优化版 Agent
python rotk_agent/qwen3_agent_optimized.py \
    --hub-url "ws://localhost:8000/ws/metaverse" \
    --env-id "env_1" \
    --agent-id "agent_optimized_$(date +%s)" \
    --provider "${LLM_PROVIDER}" \
    --faction "${AGENT_FACTION}"
