# rotk_agent/simple_agent_vllm.py
import asyncio
import argparse
import os
import sys
import json
from typing import Any, Dict, List, Optional

# 保证能 import 到框架与协议层
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich import print_json

from protocol import AgentClient  # 与环境后端通信（WebSocket）
from openai import OpenAI        # vLLM OpenAI 兼容接口（需: pip/uv add openai）

console = Console()


class RemoteContext:
    """环境通信上下文，复用 simple_agent.py 的核心能力"""
    client: AgentClient = None
    status: dict = {}
    id_map: dict = {}

    @staticmethod
    def set_client(client: AgentClient):
        RemoteContext.client = client

    @staticmethod
    def get_client() -> AgentClient:
        return RemoteContext.client

    @staticmethod
    def get_id_map() -> dict:
        return RemoteContext.id_map


async def get_response(request_id):
    """等待异步动作的最终响应"""
    console.print(f"[cyan]等待响应: {request_id}[/cyan]")
    while not RemoteContext.get_id_map().get(request_id, None):
        await asyncio.sleep(0.1)
    response = RemoteContext.get_id_map().pop(request_id)
    console.print(f"[green]响应结果:[/green] {response}")
    return response


async def perform_action(action: str, params: Any) -> Any:
    """执行动作（通过 AgentClient → 环境）"""
    console.print(f"[bold]🚀 执行动作[/bold]: {action}, 参数: {params}")
    client = RemoteContext.get_client()
    success = await client.send_action(action, params)
    resp = await get_response(success)
    try:
        print_json(data=resp)
    except Exception:
        console.print(str(resp))
    return resp


async def available_actions() -> List[Dict[str, Any]]:
    """列出当前可用动作"""
    result = await perform_action("action_list", {})
    return result


async def get_status() -> Dict[str, Any]:
    """
    获取环境运行状态。
    你可以根据自己的后端实现选择更合适的观测接口。
    这里复用 faction_state 以便拿到 game_running / turn 等信息。
    """
    # 例如对 WEI 查询阵营状态，后端会返回 game_running 等字段
    result = await perform_action("faction_state", {"faction": "wei"})
    return result


def build_tools_registry():
    """将可用工具注册为 name -> coroutine 的映射"""
    return {
        "available_actions": available_actions,
        "perform_action": perform_action,
        "get_status": get_status,
    }


def build_tools_schema():
    """OpenAI function calling 工具描述"""
    return [
        {
            "type": "function",
            "function": {
                "name": "available_actions",
                "description": "List available actions from environment",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "perform_action",
                "description": "Perform an action in environment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["action", "params"],
                    "additionalProperties": True,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_status",
                "description": "Get environment running status (game_running, turn, etc.)",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ]


class OpenAIChatAgent:
    """直连 vLLM(OpenAI 兼容) 的简单智能体，优先使用工具调用"""

    def __init__(self, base_url: str, api_key: str, model: str, max_steps: int = 50):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.max_steps = max_steps

    async def chat(self, task: str) -> str:
        tools_registry = build_tools_registry()
        tools_schema = build_tools_schema()

        messages = [
            {"role": "system", "content": (
                "You are a game agent controlling units via tools. "
                "Always use tool calls to act (available_actions, perform_action, get_status). "
                "Do not end the task until the environment status shows game_running=false."
            )},
            {"role": "user", "content": task},
        ]

        steps = 0
        final_text: Optional[str] = None

        while steps < self.max_steps:
            steps += 1
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                temperature=0.2,
            )
            choice = resp.choices[0]
            msg = choice.message

            # 工具调用
            if msg.tool_calls:
                for call in msg.tool_calls:
                    name = call.function.name
                    args_json = call.function.arguments or "{}"
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": call.id,
                            "type": "function",
                            "function": {"name": name, "arguments": args_json},
                        }]
                    })

                    # 执行本地工具
                    try:
                        args = json.loads(args_json)
                    except Exception:
                        args = {}

                    if name == "perform_action":
                        action = args.get("action", "")
                        params = args.get("params", {})
                        result = await tools_registry["perform_action"](action, params)
                    elif name == "available_actions":
                        result = await tools_registry["available_actions"]()
                    elif name == "get_status":
                        result = await tools_registry["get_status"]()
                    else:
                        result = {"error": f"unknown tool: {name}"}

                    # 回传工具结果
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                    # 若是状态查询且已结束，则停止
                    if name == "get_status":
                        try:
                            game_running = (
                                result.get("game_status", {}).get("game_running")
                                if isinstance(result, dict) else None
                            )
                        except Exception:
                            game_running = None
                        if game_running is False:
                            console.print("[bold green]环境已结束（game_running=false），停止规划。[/bold green]")
                            return "Environment finished."

                continue  # 继续下一轮对话-工具交互

            # 常规文本
            content = msg.content or ""
            messages.append({"role": "assistant", "content": content})
            final_text = content

            # 保底：每 N 步后插入一次状态查询（避免 LLM 忘记查询终止条件）
            if steps % 3 == 0:
                # 强制插入一次状态查询
                status = await tools_registry["get_status"]()
                try:
                    if status.get("game_status", {}).get("game_running") is False:
                        console.print("[bold green]环境已结束（game_running=false），停止规划。[/bold green]")
                        return final_text or "Environment finished."
                except Exception:
                    pass

            # 如果没有工具调用，也没有更多输出，结束本轮
            if not content.strip():
                break

        return final_text or ""


class AgentDemo:
    """与环境通信 + 调用 OpenAI 智能体"""
    def __init__(self, server_url="ws://localhost:8000/ws/metaverse", env_id="env_1", agent_id="agent_1"):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.agent_client = None
        self.messages = []
        self.init_client()

    def init_client(self):
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)

    def setup_hub_listeners(self):
        def on_connect(data):
            console.print(f"[green]✅ Agent 连接成功: {data}[/green]")

        def on_message(data):
            msg_data = data.get("payload")
            msg_type = msg_data.get("type")
            if msg_type == "outcome":
                outcome = msg_data.get("outcome")
                RemoteContext.get_id_map().update({msg_data["id"]: outcome})

        def on_disconnect(data):
            console.print(f"[red]❌ Agent 连接断开: {data}[/red]")

        def on_error(data):
            console.print(f"[yellow]⚠️ Agent 错误: {data}[/yellow]")

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def connect(self) -> bool:
        console.print(f"[blue]📡 服务器: {self.server_url}[/blue]")
        console.print(f"[blue]🌍 环境ID: {self.env_id}[/blue]")
        console.print(f"[blue]🆔 Agent ID: {self.agent_id}[/blue]")
        try:
            await self.agent_client.connect()
            console.print("[bold green]✅ Agent 连接成功！[/bold green]")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            console.print(f"[bold red]❌ 连接失败: {e}[/bold red]")
            return False


async def main():
    parser = argparse.ArgumentParser(description="LLM(vLLM OpenAI API) Agent for ROTK Env")
    parser.add_argument("--server-url", default="ws://localhost:8000/ws/metaverse")
    parser.add_argument("--env-id", type=str, default="env_1")
    parser.add_argument("--agent-id", type=str, default="agent_1")
    parser.add_argument("--openai-base-url", default="http://127.0.0.1:8000/v1")  # 你的 vLLM 地址
    parser.add_argument("--openai-api-key", default="EMPTY")                       # vLLM 常用占位
    parser.add_argument("--openai-model", default="your-model-name")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--task", type=str, default="控制wei阵营，消灭敌人，获得胜利。")
    args = parser.parse_args()

    demo = AgentDemo(args.server_url, args.env_id, args.agent_id)
    if not await demo.connect():
        return

    agent = OpenAIChatAgent(
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        model=args.openai_model,
        max_steps=args.max_steps,
    )

    res = await agent.chat(task=args.task)
    console.print("\n[bold cyan]📊 结果摘要[/bold cyan]")
    console.print(res or "")


if __name__ == "__main__":
    asyncio.run(main())