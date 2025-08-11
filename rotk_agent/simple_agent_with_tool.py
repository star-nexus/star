import asyncio
import argparse
from contextvars import ContextVar
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from protocol import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

from typing import Any, Dict
from menglong import Model, ChatAgent
from menglong.agents.chat.tool import plan_task


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


class RemoteContext:
    client: ContextVar[AgentClient] = ContextVar("client")
    status: ContextVar[dict] = ContextVar("status")
    task_manager: ContextVar[object] = ContextVar("task_manager")
    id_map: ContextVar[dict] = ContextVar("id_map", default={})

    @staticmethod
    def set_client(client: AgentClient):
        RemoteContext.client.set(client)

    @staticmethod
    def get_client() -> AgentClient:
        return RemoteContext.client.get()

    @staticmethod
    def set_status(status: dict):
        RemoteContext.status.set(status)

    @staticmethod
    def get_status() -> dict:
        return RemoteContext.status.get()

    @staticmethod
    def set_task_manager(task_manager: object):
        RemoteContext.task_manager.set(task_manager)

    @staticmethod
    def get_task_manager() -> object:
        return RemoteContext.task_manager.get()

    @staticmethod
    def set_id_map(id_map: dict):
        RemoteContext.id_map.set(id_map)

    @staticmethod
    def get_id_map() -> dict:
        return RemoteContext.id_map.get()


class AgentDemo:
    """Agent 客户端演示类"""

    def __init__(
        self,
        server_url="ws://localhost:8000/ws/metaverse",
        env_id="env_1",
        agent_id="agent_1",
    ):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.agent_client = None
        self.messages = []

        self.init_client()

    def init_client(self):
        # 创建客户端
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_hub_listeners()
        RemoteContext.set_client(self.agent_client)
        # 初始化状态
        RemoteContext.set_status({"self_status": {}, "env_status": {}})

    def setup_hub_listeners(self):
        """设置事件监听器"""

        def on_connect(data):
            message = f"✅ Agent 连接成功: {data}"
            console.print(message, style="green")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent 收到消息: {data}"
            # print(message)
            msg_data = data.get("payload")
            msg_type = msg_data.get("type")
            if msg_type == "action":
                action = msg_data.get("action")
                params = msg_data.get("parameters")
                message += f"\n   动作: {action}, 参数: {params}"
            elif msg_type == "outcome":
                outcome_type = msg_data.get("outcome_type")
                outcome = msg_data.get("outcome")
                RemoteContext.get_id_map().update({msg_data["id"]: outcome})
                RemoteContext.set_status(
                    {"self_status": {f"任务{msg_data['id']}": outcome}}
                )
                message += f"\n   结果: {outcome}, 结果类型: {outcome_type}"
            # console.print(message, style="blue")
            self.messages.append(message)

        def on_disconnect(data):
            message = f"❌ Agent 连接断开: {data}"
            console.print(message, style="red")
            self.messages.append(message)

        def on_error(data):
            message = f"⚠️ Agent 错误: {data}"
            msg_data = data.get("payload", {})
            error = msg_data.get("error", "未知错误")
            console.print(message, style="yellow")
            # 只有当msg_data有id字段时才更新id_map
            if "id" in msg_data:
                RemoteContext.get_id_map().update({msg_data["id"]: error})
            self.messages.append(message)
            console.print("error 处理完毕", style="red")

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def connect(self):
        """创建并连接 Agent 客户端"""
        console.print("🤖 创建 Agent 客户端", style="bold blue")
        console.print(f"📡 服务器: {self.server_url}")
        console.print(f"🌍 环境ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        # 连接
        console.print("🔗 正在连接到服务器...", style="yellow")
        try:
            await self.agent_client.connect()
            console.print("✅ Agent 连接成功！", style="bold green")

            # 等待连接稳定
            await asyncio.sleep(1)
            return True
        except Exception as e:
            console.print(f"❌ 连接失败: {e}", style="bold red")
            return False

    async def interactive_mode(self):
        """交互模式：用户可以手动输入动作"""
        console.print("\n🎮 进入交互模式", style="bold cyan")
        console.print("=" * 20)
        console.print("可用命令:")
        console.print("  chat <prompt>")
        console.print("  message <action> <params> - 自定义动作")
        console.print("  list - 列出可用动作")
        console.print("  run - 执行预定义动作")
        console.print("  quit - 退出交互模式")
        console.print()

        # 创建异步prompt session
        session = PromptSession()

        while True:
            try:
                # 在patch_stdout外部获取用户输入，避免颜色问题
                with patch_stdout():
                    command = await session.prompt_async("🎯 请输入命令: ")
                    command = command.strip()

                if not command:
                    await asyncio.sleep(1)
                    continue

                if command.lower() == "quit":
                    console.print("👋 退出交互模式", style="bold green")
                    break

                parts = command.split()
                action = parts[0].lower()

                console.print(f"🎯 识别到命令: {action}", style="cyan")
                console.print(f"   参数: {parts[1:] if len(parts) > 1 else '无'}")

                if action in ACTION.keys():
                    # 在patch_stdout外部执行操作，确保颜色正常显示
                    await asyncio.create_task(ACTION[action](parts))
                    # await ACTION[action](parts)
                else:
                    console.print(f"❌ 未知命令: {command}", style="red")
                    console.print("输入 'quit' 退出，或查看上方的可用命令列表")

                await asyncio.sleep(0.1)  # 短暂延迟以便查看结果

            except KeyboardInterrupt:
                print("\n👋 用户中断，退出交互模式")
                break
            except Exception as e:
                print(f"❌ 命令执行错误: {e}")

    def show_summary(self):
        """显示演示总结"""
        console.print("\n📊 Agent 演示总结", style="bold cyan")
        console.print("=" * 25)
        console.print(f"📈 总消息数: {len(self.messages)}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print(f"🌍 环境 ID: {self.env_id}")

        if self.messages:
            console.print("\n📝 消息历史 (最近10条):")
            for i, msg in enumerate(self.messages[-10:], 1):
                console.print(f"   {i}. {msg}")

    async def cleanup(self):
        """清理资源"""
        console.print("\n🧹 正在清理连接...", style="yellow")
        try:
            if self.agent_client:
                await self.agent_client.disconnect()
                console.print("✅ Agent 连接已断开", style="green")
        except Exception as e:
            console.print(f"⚠️ 断开连接时出错: {e}", style="yellow")

    async def run_interactive_demo(self):
        """运行交互式演示"""
        console.print("🎮 Star Client Agent 交互式演示", style="bold cyan")
        console.print("🎯 你可以手动控制 Agent 执行各种动作", style="cyan")
        console.print("=" * 50)

        try:
            # 连接
            if not await self.connect():
                return
            # 进入交互模式
            await self.interactive_mode()

            # 显示总结
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ 用户中断演示")
        except Exception as e:
            print(f"\n❌ 演示过程中发生错误: {e}")
        finally:
            await self.cleanup()


async def message(parts):

    if len(parts) > 1:
        custom_action = parts[1]
        # 将参数按键值对解析成字典
        params = {}
        param_list = parts[2:] if len(parts) > 2 else []
        for i in range(0, len(param_list), 2):
            if i + 1 < len(param_list):
                params[param_list[i]] = param_list[i + 1]
            else:
                params[param_list[i]] = ""  # 如果没有值，设为空字符串
        return await perform_action(custom_action, params)
    else:
        console.print("❌ 请指定动作，如: message dance", style="red")


async def chat(parts):
    if len(parts) > 1:
        custom_action = parts[0]
        params = parts[1] if len(parts) > 1 else ""

        agent = ChatAgent()

        async def stop_running():
            """检测到游戏结束时停止运行"""
            await agent.stop()

        # Create hardcoded tool definitions using SimpleTool
        tools = [
            SimpleTool(
                name="available_actions",
                func=available_actions,
                description="获取当前可以执行的可用动作列表。",
                parameters={"type": "object", "properties": {}, "required": []},
            ),
            SimpleTool(
                name="perform_action", 
                func=perform_action,
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
            ),
            SimpleTool(
                name="stop_running",
                func=stop_running,
                description="当检测到游戏结束时，停止代理的运行。",
                parameters={"type": "object", "properties": {}, "required": []},
            ),
        ]

        res = await agent.chat(task=params, tools=tools)
        # print(res)
    else:
        print("❌ 请指定动作，如: chat dance")


async def raw_llm(parts):

    goal = """
    GOAL TODO
"""
    try:
        agent = ChatAgent()

        # Create hardcoded tool definitions using SimpleTool
        tools = [
            SimpleTool(
                name="available_actions",
                func=available_actions,
                description="获取当前可以执行的可用动作列表。",
                parameters={"type": "object", "properties": {}, "required": []},
            ),
            SimpleTool(
                name="perform_action", 
                func=perform_action,
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
            ),
        ]

        res = await agent.chat(task=goal, tools=[plan_task] + tools)
        # print(res)
    except Exception as e:
        print("执行任务时发生错误:", e)


async def get_response(request_id):
    """获取动作执行的响应"""

    # print(f"等待响应: {request_id}")
    while not RemoteContext.get_id_map().get(request_id, None):
        await asyncio.sleep(0.1)  # 等待响应
    response = RemoteContext.get_id_map().pop(request_id)
    # print(f"响应结果: {response}")

    return response


async def list_action(parts):
    """列出可用动作"""
    # print("获取可用动作列表...")
    actions = await available_actions()
    # print(f"可用动作: {actions}")


async def perform_action(action: str, params: Any):
    """执行动作"""
    # print(f"🚀 执行动作: {action}, 参数: {params}")

    response = None

    client = RemoteContext.get_client()
    # print(f"当前客户端: {client}")

    success = await client.send_action(action, params)
    # print(f"执行动作的立刻结果 - success: {success}")
    response = await get_response(success)

    # if response:
        #  print_json(data=response)
    return response


async def available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""

    result = await perform_action("action_list", {})

    return result


async def run_action(parts):
    """执行指定动作"""
    rule = """游戏规则:
# 阵营
有两方阵营，wei 和 shu
所有单位同时进行操作
# 地图
地图大小：通常为不超过50x50六边形格子,以(0,0)为地图中心
# 单位
每个阵营开始时拥有若干个单位
初始单位包含步兵、骑兵、弓兵的组合
# 阶段
可以任意顺序操作所有己方单位
每个单位可进行移动、攻击、建造、使用技能等动作
可以多次在不同单位间切换操作
如果无法行动则结束回合
"""
    await chat(["chat", rule + "控制wei阵营,消灭敌人,获得胜利。"])


ACTION = {
    "chat": chat,
    "message": message,
    "list": list_action,
    "run": run_action,
    "raw": raw_llm,
}


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Star Client Agent 演示程序")

    parser.add_argument(
        "--server-url",
        default="ws://localhost:8000/ws/metaverse",
        help="服务器地址 (默认: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument(
        "--env-id", type=str, default="env_1", help="环境ID (默认: env_1)"
    )
    parser.add_argument(
        "--agent-id", type=str, default="agent_1", help="Agent ID (默认: 1)"
    )

    args = parser.parse_args()

    console.print(f"📡 服务器: {args.server_url}")
    console.print(f"🌍 环境ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print("=" * 60)

    # 创建演示实例
    demo = AgentDemo(args.server_url, args.env_id, args.agent_id)
    console.print("🎮 交互式模式", style="bold cyan")
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())
