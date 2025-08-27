#!/usr/bin/env python3
"""
测试 vLLM 本地模型的代理功能

使用前请确保：
1. 已经启动 vLLM 服务：
   python -m vllm.entrypoints.openai.api_server --model <model_name> --port 8000

2. 或者使用 Docker：
   docker run --gpus all -v ~/.cache/huggingface:/root/.cache/huggingface \
   --env "HUGGING_FACE_HUB_TOKEN=<token>" -p 8000:8000 \
   vllm/vllm-openai:latest --model <model_name>
"""

import asyncio
import sys
import os
import httpx

# 添加路径以便导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rotk_agent.standalone_agent import (
    StandaloneChatAgent, 
    LLMConfig, 
    load_config
)


async def test_vllm_connection(base_url: str = "http://localhost:8000/v1"):
    """测试 vLLM 服务是否可用"""
    print(f"🔗 测试 vLLM 服务连接: {base_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            # 测试服务健康状态
            response = await client.get(f"{base_url.rstrip('/v1')}/health", timeout=5.0)
            if response.status_code == 200:
                print("✅ vLLM 服务健康检查通过")
            
            # 测试模型列表
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": "Bearer sk-no-key-required"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                models = response.json()
                print(f"✅ vLLM 服务连接成功")
                print(f"📋 可用模型列表:")
                for model in models.get("data", []):
                    print(f"   - {model.get('id', 'unknown')}")
                return True
            else:
                print(f"❌ 无法获取模型列表: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ vLLM 服务连接失败: {e}")
        print("💡 请确保 vLLM 服务正在运行:")
        print("   python -m vllm.entrypoints.openai.api_server --model <model_name> --port 8000")
        return False


async def mock_available_actions():
    """模拟的 available_actions 函数"""
    return {
        "success": True,
        "total_actions": 3,
        "actions": {
            "move": {
                "category": "unit_control",
                "description": "移动单位到指定位置",
                "parameters": {
                    "unit_id": {"type": "int", "required": True, "description": "单位ID"},
                    "target_position": {
                        "type": "object",
                        "required": True,
                        "description": "目标位置",
                        "properties": {
                            "col": {"type": "int", "description": "列坐标"},
                            "row": {"type": "int", "description": "行坐标"}
                        }
                    }
                }
            },
            "attack": {
                "category": "unit_control", 
                "description": "攻击指定敌方单位",
                "parameters": {
                    "unit_id": {"type": "int", "required": True, "description": "攻击方单位ID"},
                    "target_id": {"type": "int", "required": True, "description": "目标单位ID"}
                }
            },
            "rest": {
                "category": "unit_control",
                "description": "单位休整并恢复状态", 
                "parameters": {
                    "unit_id": {"type": "int", "required": True, "description": "单位ID"}
                }
            }
        }
    }


async def mock_perform_action(action: str, params: dict):
    """模拟的 perform_action 函数"""
    print(f"[模拟] 执行动作: {action}，参数: {params}")
    
    if action == "move":
        return {
            "success": True,
            "message": f"单位 {params.get('unit_id')} 移动到位置 {params.get('target_position')}",
            "new_position": params.get('target_position')
        }
    elif action == "attack":
        return {
            "success": True,
            "message": f"单位 {params.get('unit_id')} 攻击了单位 {params.get('target_id')}",
            "damage_dealt": 25
        }
    elif action == "rest":
        return {
            "success": True,
            "message": f"单位 {params.get('unit_id')} 进入休整状态",
            "health_recovered": 10
        }
    else:
        return {
            "success": False,
            "error": f"未知动作: {action}"
        }


async def mock_stop_running():
    """模拟的 stop_running 函数"""
    return {
        "message": "Stop running tool was called", 
        "status": "test_completed"
    }


async def test_vllm_agent():
    """测试 vLLM 代理"""
    print("🧪 开始测试 vLLM 代理...")
    
    try:
        # 加载 vLLM 配置
        config_path = os.path.join(os.getcwd(), ".configs.vllm.toml")
        print(f"📁 加载 vLLM 配置文件: {config_path}")
        
        if not os.path.exists(config_path):
            print(f"❌ vLLM 配置文件不存在: {config_path}")
            print("💡 请先创建 .configs.vllm.toml 配置文件")
            return False
            
        llm_config = load_config(config_path)
        print(f"✅ 配置加载成功: Provider={llm_config.provider}, Model={llm_config.model_id}")
        print(f"🔗 Base URL: {llm_config.base_url}")
        
        # 测试 vLLM 服务连接
        if not await test_vllm_connection(llm_config.base_url):
            return False
        
        # 创建代理
        agent = StandaloneChatAgent(llm_config)
        print("✅ vLLM 代理创建成功")
        
        # 注册模拟工具
        agent.register_tool(
            name="available_actions",
            function=mock_available_actions,
            description="获取当前可以执行的可用动作列表。",
            parameters={"type": "object", "properties": {}, "required": []},
        )
        
        agent.register_tool(
            name="perform_action",
            function=mock_perform_action,
            description="在游戏环境中执行一个特定的动作。",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "要执行的动作的名称。",
                    },
                    "params": {
                        "type": "object",
                        "description": "指定动作所需的参数字典。",
                        "additionalProperties": True,
                    },
                },
                "required": ["action", "params"],
            },
        )
        
        agent.register_tool(
            name="stop_running",
            function=mock_stop_running,
            description="当检测到游戏结束时，停止代理的运行。",
            parameters={"type": "object", "properties": {}, "required": []},
        )
        
        print("✅ 工具注册完成")
        
        # 执行简单的测试任务
        task = """测试 vLLM 本地模型: 请先调用 available_actions 获取可用动作，然后使用 perform_action 执行一个移动操作（将单位ID为1的单位移动到位置 {col: 3, row: 5}），最后调用 stop_running。
        
        请按顺序执行这些步骤，并在每一步后简要说明你的操作。"""
        
        print("🎯 开始执行 vLLM 测试任务...")
        print(f"📝 任务内容: {task}")
        
        # 执行聊天任务，设置较短的超时时间
        result = await asyncio.wait_for(agent.chat(task=task, max_iterations=5), timeout=120.0)
        
        print("\n" + "="*50)
        print("🎉 vLLM 测试任务完成!")
        print(f"📊 执行结果: {result}")
        
        # 清理资源
        await agent.stop()
        print("✅ vLLM 代理已停止，资源已清理")
        
        return True
        
    except asyncio.TimeoutError:
        print("⏰ vLLM 测试超时")
        return False
    except Exception as e:
        print(f"❌ vLLM 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_basic_vllm_config_loading():
    """测试基本的 vLLM 配置加载"""
    print("🧪 测试 vLLM 配置加载...")
    
    try:
        config_path = os.path.join(os.getcwd(), ".configs.vllm.toml")
        
        if not os.path.exists(config_path):
            print(f"❌ vLLM 配置文件不存在: {config_path}")
            return False
            
        llm_config = load_config(config_path)
        print(f"✅ vLLM 配置加载成功:")
        print(f"   Provider: {llm_config.provider}")
        print(f"   Model: {llm_config.model_id}")
        print(f"   API Key: {llm_config.api_key}")
        print(f"   Base URL: {llm_config.base_url}")
        print(f"   Temperature: {llm_config.temperature}")
        
        return True
        
    except Exception as e:
        print(f"❌ vLLM 配置加载失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始 vLLM 代理测试套件")
    print("="*60)
    
    # 测试配置加载
    if not await test_basic_vllm_config_loading():
        print("❌ vLLM 配置加载测试失败，无法继续")
        return
    
    print("\n" + "="*60)
    
    # 测试完整的 vLLM 代理功能
    success = await test_vllm_agent()
    
    print("\n" + "="*60)
    if success:
        print("🏁 vLLM 测试套件完成 - 成功! ✅")
    else:
        print("🏁 vLLM 测试套件完成 - 失败! ❌")


if __name__ == "__main__":
    asyncio.run(main())
