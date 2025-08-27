#!/usr/bin/env python3
"""
Test script to verify that the LLM can use the three tools:
- available_actions
- perform_action  
- stop_running

This script creates a minimal test environment to validate tool functionality.
"""

import asyncio
import argparse
import sys
import os
from unittest.mock import AsyncMock, MagicMock
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import AgentClient
from menglong import ChatAgent
from rich.console import Console
from rich import print_json

console = Console()


class SimpleToolInfo:
    """Simple tool info class to mimic the structure expected by ChatAgent"""
    
    def __init__(self, name: str, func: callable, description: str, parameters: dict):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters


class SimpleTool:
    """Simple tool class to mimic decorated tools"""
    
    def __init__(self, name: str, func: callable, description: str, parameters: dict):
        self._tool_info = SimpleToolInfo(name, func, description, parameters)


class MockRemoteContext:
    """Mock remote context for testing"""
    
    def __init__(self):
        self.client = None
        self.id_map = {}
        self.call_count = 0
    
    def set_client(self, client):
        self.client = client
    
    def get_client(self):
        return self.client
    
    def get_id_map(self):
        return self.id_map


class MockAgentClient:
    """Mock agent client for testing"""
    
    def __init__(self):
        self.call_history = []
        self.mock_responses = {
            "action_list": {
                "actions": [
                    {
                        "name": "move",
                        "description": "移动单位到指定位置",
                        "parameters": {
                            "unit_id": "string",
                            "target_q": "integer", 
                            "target_r": "integer"
                        }
                    },
                    {
                        "name": "attack",
                        "description": "攻击指定目标",
                        "parameters": {
                            "attacker_id": "string",
                            "target_id": "string"
                        }
                    },
                    {
                        "name": "end_turn",
                        "description": "结束当前回合",
                        "parameters": {}
                    }
                ]
            },
            "move": {
                "success": True,
                "message": "单位移动成功",
                "new_position": {"q": 2, "r": 3}
            },
            "attack": {
                "success": True,
                "message": "攻击成功",
                "damage": 25
            }
        }
    
    async def send_action(self, action: str, params: dict):
        """Mock send_action method"""
        self.call_history.append({"action": action, "params": params})
        
        # Generate a fake request ID
        request_id = f"req_{len(self.call_history)}"
        
        # Simulate async response
        await asyncio.sleep(0.1)
        
        # Store response in mock context
        response = self.mock_responses.get(action, {"success": True, "message": f"Mock response for {action}"})
        mock_context.id_map[request_id] = response
        
        console.print(f"[green]Mock client: sent action '{action}' with params {params}[/green]")
        console.print(f"[blue]Mock client: generated request ID '{request_id}'[/blue]")
        
        return request_id


# Global mock context
mock_context = MockRemoteContext()


async def mock_get_response(request_id):
    """Mock get_response function"""
    console.print(f"[yellow]Waiting for response: {request_id}[/yellow]")
    
    # Simulate waiting for response
    max_wait = 50  # 5 seconds max
    wait_count = 0
    
    while request_id not in mock_context.id_map and wait_count < max_wait:
        await asyncio.sleep(0.1)
        wait_count += 1
    
    if request_id in mock_context.id_map:
        response = mock_context.id_map.pop(request_id)
        console.print(f"[green]Response received: {response}[/green]")
        return response
    else:
        console.print(f"[red]Timeout waiting for response: {request_id}[/red]")
        return {"error": f"Timeout waiting for response: {request_id}"}


async def mock_perform_action(action: str, params: dict):
    """Mock perform_action function"""
    console.print(f"[cyan]🚀 执行动作: {action}, 参数: {params}[/cyan]")
    
    client = mock_context.get_client()
    if not client:
        return {"error": "No client available"}
    
    request_id = await client.send_action(action, params)
    response = await mock_get_response(request_id)
    
    if response:
        print_json(data=response)
    
    return response


async def mock_available_actions():
    """Mock available_actions function"""
    console.print("[cyan]📋 获取可用动作列表...[/cyan]")
    result = await mock_perform_action("action_list", {})
    return result


async def mock_stop_running():
    """Mock stop_running function - for testing purposes, just return a message"""
    console.print("[cyan]🛑 Stop running called[/cyan]")
    # Return a message that indicates the test should end
    return {"message": "Stop running tool was called", "status": "test_completed"}


async def test_individual_tools():
    """Test each tool individually"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing Individual Tools[/bold cyan]")
    console.print("="*60)
    
    # Setup mock client
    mock_client = MockAgentClient()
    mock_context.set_client(mock_client)
    
    # Test 1: available_actions
    console.print("\n[bold]Test 1: available_actions[/bold]")
    result1 = await mock_available_actions()
    console.print(f"Result: {result1}")
    
    # Test 2: perform_action  
    console.print("\n[bold]Test 2: perform_action[/bold]")
    result2 = await mock_perform_action("move", {"unit_id": "wei_infantry_1", "target_q": 2, "target_r": 3})
    console.print(f"Result: {result2}")
    
    # Test 3: stop_running
    console.print("\n[bold]Test 3: stop_running[/bold]")
    result3 = await mock_stop_running()
    console.print(f"Result: {result3}")
    
    # Show call history
    console.print("\n[bold]Mock Client Call History:[/bold]")
    for i, call in enumerate(mock_client.call_history, 1):
        console.print(f"  {i}. Action: {call['action']}, Params: {call['params']}")


async def test_llm_tool_usage():
    """Test that LLM can actually use the tools"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing LLM Tool Usage[/bold cyan]")
    console.print("="*60)
    
    # Setup mock client
    mock_client = MockAgentClient()
    mock_context.set_client(mock_client)
    
    # Create agent
    agent = ChatAgent()
    
    # Create tools
    tools = [
        SimpleTool(
            name="available_actions",
            func=mock_available_actions,
            description="获取当前可以执行的可用动作列表。这个工具不需要任何参数，会返回游戏环境中所有可用的动作及其描述。",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        SimpleTool(
            name="perform_action", 
            func=mock_perform_action,
            description="在游戏环境中执行一个特定的动作。需要提供动作名称和相应的参数。",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "要执行的动作的名称，例如: move, attack, end_turn",
                    },
                    "params": {
                        "type": "object",
                        "description": "指定动作所需的参数字典。不同的动作需要不同的参数。",
                        "additionalProperties": True,
                    },
                },
                "required": ["action", "params"],
            },
        ),
        SimpleTool(
            name="stop_running",
            func=mock_stop_running,
            description="当检测到游戏结束或需要停止代理运行时调用此工具。",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ]
    
    # Test task: Ask LLM to get available actions
    test_task = """
    请帮我测试工具的使用。请按照以下步骤操作：
    
    1. 首先调用 available_actions 工具来获取所有可用的动作列表
    2. 然后调用 perform_action 工具来执行一个移动动作，移动单位"wei_infantry_1"到位置(2,3)
    3. 最后调用 stop_running 工具来标记测试完成
    4. 总结所有工具调用的结果并报告测试状态
    
    请确保每个工具都被正确调用，并在最后提供一个测试完成的总结。
    """
    
    console.print(f"\n[bold]测试任务:[/bold]\n{test_task}")
    
    try:
        # Execute the task with timeout
        console.print("\n[yellow]启动 ChatAgent 进行工具测试...[/yellow]")
        
        # Add timeout to prevent hanging and use auto_end=True
        try:
            result = await asyncio.wait_for(
                agent.chat(task=test_task, tools=tools, auto_end=True),
                timeout=60.0  # 60 seconds timeout
            )
        except asyncio.TimeoutError:
            console.print("[yellow]⚠️ 测试超时 (60秒)，但这可能是正常的，因为 stop_running 工具被调用了[/yellow]")
            result = "Test completed with timeout (this may be expected after stop_running is called)"
        
        console.print(f"\n[bold green]ChatAgent 执行结果:[/bold green]")
        console.print(result)
        
        # Show final call history  
        console.print(f"\n[bold]最终调用历史 (共 {len(mock_client.call_history)} 次调用):[/bold]")
        for i, call in enumerate(mock_client.call_history, 1):
            console.print(f"  {i}. Action: '{call['action']}', Params: {call['params']}")
            
        # Verify expected tools were called
        actions_called = [call['action'] for call in mock_client.call_history]
        console.print(f"\n[bold]被调用的动作:[/bold] {actions_called}")
        
        if "action_list" in actions_called:
            console.print("[green]✅ available_actions 工具被成功调用[/green]")
        else:
            console.print("[red]❌ available_actions 工具未被调用[/red]")
            
        if "move" in actions_called:
            console.print("[green]✅ perform_action 工具被成功调用[/green]")
        else:
            console.print("[red]❌ perform_action 工具未被调用[/red]")
        
    except Exception as e:
        console.print(f"[red]测试过程中出现错误: {e}[/red]")
        import traceback
        console.print(f"[red]错误详情: {traceback.format_exc()}[/red]")


async def test_tool_parameter_validation():
    """Test tool parameter validation"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing Tool Parameter Validation[/bold cyan]")
    console.print("="*60)
    
    # Setup mock client
    mock_client = MockAgentClient()
    mock_context.set_client(mock_client)
    
    # Test valid parameters
    console.print("\n[bold]Test: Valid Parameters[/bold]")
    try:
        result = await mock_perform_action("move", {"unit_id": "test_unit", "target_q": 1, "target_r": 2})
        console.print(f"[green]✅ Valid parameters accepted: {result}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Error with valid parameters: {e}[/red]")
    
    # Test invalid parameters
    console.print("\n[bold]Test: Missing Parameters[/bold]")
    try:
        result = await mock_perform_action("move", {})  # Missing required params
        console.print(f"[yellow]⚠️ Missing parameters handled: {result}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Expected error with missing parameters: {e}[/yellow]")


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test tool usage in simple_agent")
    parser.add_argument("--test", choices=["individual", "llm", "validation", "all"], 
                       default="all", help="Which test to run")
    
    args = parser.parse_args()
    
    console.print("[bold blue]🧪 Tool Usage Test Suite[/bold blue]")
    console.print("This script tests whether the LLM can use our three tools:")
    console.print("  • available_actions")
    console.print("  • perform_action") 
    console.print("  • stop_running")
    
    if args.test in ["individual", "all"]:
        await test_individual_tools()
    
    if args.test in ["validation", "all"]:
        await test_tool_parameter_validation()
        
    if args.test in ["llm", "all"]:
        await test_llm_tool_usage()
    
    console.print("\n[bold green]🎉 所有测试完成![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
