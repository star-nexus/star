#!/usr/bin/env python3
"""
测试独立代理的工具功能
"""

import asyncio
import sys
import os

# 添加路径以便导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rotk_agent.standalone_agent import (
    StandaloneChatAgent, 
    LLMConfig, 
    load_config
)


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


async def test_standalone_agent():
    """测试独立代理"""
    print("🧪 开始测试独立代理...")
    
    try:
        # 加载配置
        config_path = os.path.join(os.getcwd(), ".configs.toml")
        print(f"📁 加载配置文件: {config_path}")
        
        if not os.path.exists(config_path):
            print(f"❌ 配置文件不存在: {config_path}")
            return
            
        llm_config = load_config(config_path)
        print(f"✅ 配置加载成功: Provider={llm_config.provider}, Model={llm_config.model_id}")
        
        # 创建代理
        agent = StandaloneChatAgent(llm_config)
        print("✅ 独立代理创建成功")
        
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
        
        # 执行测试任务
        task = """测试任务: 请先调用 available_actions 获取可用动作，然后执行一个 move 动作，最后调用 stop_running。
        
        具体步骤：
        1. 调用 available_actions 查看有哪些动作可用
        2. 使用 perform_action 执行一个移动操作，将单位ID为1的单位移动到位置 {col: 5, row: 8}
        3. 最后调用 stop_running 结束任务
        
        请按顺序执行这些步骤。"""
        
        print("🎯 开始执行测试任务...")
        print(f"📝 任务内容: {task}")
        
        # 执行聊天任务，设置超时
        result = await asyncio.wait_for(agent.chat(task=task, max_iterations=6), timeout=120.0)
        
        print("\n" + "="*50)
        print("🎉 测试任务完成!")
        print(f"📊 执行结果: {result}")
        
        # 清理资源
        await agent.stop()
        print("✅ 代理已停止，资源已清理")
        
    except asyncio.TimeoutError:
        print("⏰ 测试超时")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


async def test_basic_config_loading():
    """测试基本配置加载"""
    print("🧪 测试配置加载...")
    
    try:
        config_path = os.path.join(os.getcwd(), ".configs.toml")
        
        if not os.path.exists(config_path):
            print(f"❌ 配置文件不存在: {config_path}")
            return False
            
        llm_config = load_config(config_path)
        print(f"✅ 配置加载成功:")
        print(f"   Provider: {llm_config.provider}")
        print(f"   Model: {llm_config.model_id}")
        print(f"   API Key (前10位): {llm_config.api_key[:10]}...")
        print(f"   Temperature: {llm_config.temperature}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始独立代理测试套件")
    print("="*60)
    
    # 测试配置加载
    if not await test_basic_config_loading():
        print("❌ 配置加载测试失败，无法继续")
        return
    
    print("\n" + "="*60)
    
    # 测试完整的代理功能
    await test_standalone_agent()
    
    print("\n" + "="*60)
    print("🏁 测试套件完成")


if __name__ == "__main__":
    asyncio.run(main())
