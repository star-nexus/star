#!/usr/bin/env python3
"""
Simple focused test to verify that the LLM can call the available_actions tool.
This is a minimal test that specifically tests the available_actions functionality.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from menglong import ChatAgent
from rich.console import Console

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


async def mock_available_actions():
    """Mock available_actions function that returns sample game actions"""
    console.print("[cyan]📋 Mock: Getting available actions...[/cyan]")
    
    # Simulate some delay
    await asyncio.sleep(0.5)
    
    # Return mock action data
    actions = {
        "actions": [
            {
                "name": "move",
                "description": "移动单位到指定位置",
                "parameters": {
                    "unit_id": "单位ID",
                    "target_q": "目标Q坐标", 
                    "target_r": "目标R坐标"
                }
            },
            {
                "name": "attack",
                "description": "攻击指定目标",
                "parameters": {
                    "attacker_id": "攻击者ID",
                    "target_id": "目标ID"
                }
            },
            {
                "name": "end_turn",
                "description": "结束当前回合",
                "parameters": {}
            },
            {
                "name": "fortify",
                "description": "建设工事",
                "parameters": {
                    "unit_id": "建设单位ID",
                    "position_q": "建设位置Q坐标",
                    "position_r": "建设位置R坐标"
                }
            }
        ],
        "total_actions": 4,
        "current_player": "wei",
        "turn_number": 1
    }
    
    console.print(f"[green]✅ 返回 {actions['total_actions']} 个可用动作[/green]")
    return actions


async def test_available_actions_tool():
    """Test that LLM can call available_actions tool"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing available_actions Tool with LLM[/bold cyan]")
    console.print("="*60)
    
    # Create agent
    agent = ChatAgent()
    
    # Create only the available_actions tool
    tools = [
        SimpleTool(
            name="available_actions",
            func=mock_available_actions,
            description="获取当前游戏环境中所有可用的动作列表。这个工具会返回当前玩家可以执行的所有动作，包括动作名称、描述和所需参数。",
            parameters={"type": "object", "properties": {}, "required": []},
        )
    ]
    
    # Simple task asking to get available actions
    task = """
    请帮我获取当前游戏中所有可用的动作列表。请使用 available_actions 工具来查询所有可用的动作，然后总结一下有哪些动作可以使用。
    """
    
    console.print(f"[bold]测试任务:[/bold] {task}")
    
    try:
        console.print("\n[yellow]启动 ChatAgent 测试 available_actions 工具...[/yellow]")
        
        # Execute the task
        result = await agent.chat(task=task, tools=tools)
        
        console.print(f"\n[bold green]ChatAgent 执行结果:[/bold green]")
        console.print(result)
        
        console.print("\n[bold blue]测试评估:[/bold blue]")
        if "available_actions" in str(result).lower() or "move" in str(result).lower():
            console.print("[green]✅ 测试成功！LLM 成功调用了 available_actions 工具[/green]")
        else:
            console.print("[yellow]⚠️ 测试结果不确定，请检查输出内容[/yellow]")
            
    except Exception as e:
        console.print(f"[red]❌ 测试失败: {e}[/red]")
        import traceback
        console.print(f"[red]错误详情: {traceback.format_exc()}[/red]")


async def main():
    """Main test function"""
    console.print("[bold blue]🎯 Available Actions Tool Test[/bold blue]")
    console.print("This is a focused test to verify the LLM can call available_actions")
    
    await test_available_actions_tool()
    
    console.print("\n[bold green]🎉 测试完成![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
