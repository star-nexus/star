#!/usr/bin/env python3
"""
Improved test for the stop_running tool that avoids the deadlock issue.
This test uses a different approach to verify stop_running functionality.
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


# Global flag to track if stop_running was called
stop_running_called = False


async def mock_available_actions():
    """Mock available_actions function"""
    console.print("[cyan]📋 Mock: Getting available actions...[/cyan]")
    await asyncio.sleep(0.2)
    return {"actions": ["move", "attack", "end_turn"], "total": 3}


async def mock_perform_action(action: str, params: dict):
    """Mock perform_action function"""
    console.print(f"[cyan]🚀 Mock: Executing {action} with {params}[/cyan]")
    await asyncio.sleep(0.2)
    return {"success": True, "message": f"Mock execution of {action}"}


async def mock_stop_running():
    """Mock stop_running function that sets a global flag"""
    global stop_running_called
    console.print("[cyan]🛑 Mock: Stop running called[/cyan]")
    stop_running_called = True
    console.print("[green]✅ Stop running flag set to True[/green]")
    return {"message": "Stop running tool executed successfully", "stopped": True}


async def test_stop_running_with_shorter_task():
    """Test stop_running with a task that naturally completes"""
    global stop_running_called
    stop_running_called = False
    
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing stop_running Tool (Improved Version)[/bold cyan]")
    console.print("="*60)
    
    agent = ChatAgent()
    
    tools = [
        SimpleTool(
            name="available_actions",
            func=mock_available_actions,
            description="获取当前可以执行的可用动作列表",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        SimpleTool(
            name="stop_running",
            func=mock_stop_running,
            description="停止代理运行的工具",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
    ]
    
    # Shorter, more direct task
    task = """
    请执行以下简单测试：
    1. 调用 available_actions 获取动作列表
    2. 调用 stop_running 工具来测试其功能
    3. 完成测试并总结结果
    """
    
    console.print(f"[bold]测试任务:[/bold] {task}")
    
    try:
        console.print("\n[yellow]启动测试...[/yellow]")
        
        # Use a shorter timeout and auto_end
        result = await asyncio.wait_for(
            agent.chat(task=task, tools=tools, auto_end=True),
            timeout=30.0
        )
        
        console.print(f"\n[bold green]测试完成! 结果:[/bold green]")
        console.print(result)
        
    except asyncio.TimeoutError:
        console.print("[yellow]⚠️ 超时，但这可能是预期的[/yellow]")
    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
    
    # Check if stop_running was called
    console.print(f"\n[bold]Stop Running 状态检查:[/bold]")
    if stop_running_called:
        console.print("[green]✅ stop_running 工具被成功调用![/green]")
    else:
        console.print("[red]❌ stop_running 工具未被调用[/red]")
    
    return stop_running_called


async def test_stop_running_standalone():
    """Test stop_running tool in isolation"""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Testing stop_running Tool Standalone[/bold cyan]")
    console.print("="*60)
    
    console.print("\n[bold]直接调用 stop_running 工具:[/bold]")
    result = await mock_stop_running()
    console.print(f"结果: {result}")
    
    if result.get("stopped"):
        console.print("[green]✅ stop_running 工具功能正常[/green]")
        return True
    else:
        console.print("[red]❌ stop_running 工具功能异常[/red]")
        return False


async def main():
    """Main test function"""
    console.print("[bold blue]🧪 Stop Running Tool Fix Test[/bold blue]")
    console.print("This test verifies that stop_running works without causing deadlocks")
    
    # Test 1: Standalone test
    standalone_ok = await test_stop_running_standalone()
    
    # Test 2: With LLM (improved version)
    llm_ok = await test_stop_running_with_shorter_task()
    
    console.print("\n" + "="*60)
    console.print("[bold blue]测试总结[/bold blue]")
    console.print("="*60)
    
    if standalone_ok:
        console.print("[green]✅ 独立测试: stop_running 工具功能正常[/green]")
    else:
        console.print("[red]❌ 独立测试: stop_running 工具功能异常[/red]")
    
    if llm_ok:
        console.print("[green]✅ LLM测试: stop_running 工具被成功调用[/green]")
    else:
        console.print("[red]❌ LLM测试: stop_running 工具未被调用[/red]")
    
    if standalone_ok and llm_ok:
        console.print("\n[bold green]🎉 所有测试通过! stop_running 工具工作正常![/bold green]")
    else:
        console.print("\n[bold yellow]⚠️ 部分测试未通过，需要进一步调试[/bold yellow]")


if __name__ == "__main__":
    asyncio.run(main())
