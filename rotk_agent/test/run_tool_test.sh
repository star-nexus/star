#!/bin/bash

# Simple script to run tool usage tests

echo "🧪 Running Tool Usage Tests for simple_agent.py"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "rotk_agent/test_tool_usage.py" ]; then
    echo "❌ Error: Please run this script from the starbench root directory"
    exit 1
fi

echo ""
echo "Testing individual tools..."
python rotk_agent/test_tool_usage.py --test individual

echo ""
echo "Testing parameter validation..."
python rotk_agent/test_tool_usage.py --test validation

echo ""
echo "Testing LLM tool usage (this may take a while)..."
python rotk_agent/test_tool_usage.py --test llm

echo ""
echo "✅ All tests completed!"
