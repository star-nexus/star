#!/usr/bin/env python3
"""
Star Cli# 创建支持颜色的控制台实例，专门处理patch_stdout环境
console = Console(
    force_terminal=True,  # 强制认为是终端
    color_system="truecolor",  # 使用真彩色
    width=None,  # 自动检测宽度
    legacy_windows=False,
    no_color=False  # 确保颜色启用
)t 演示
专门展示 Agent 客户端的功能和使用方法
"""

import asyncio
import argparse
from contextvars import ContextVar
import os
from pathlib import Path
import sys


from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

sys.path.append(str(Path(__file__).parent.parent))
from protocol.star_client import AgentClient

# 配置 rich 库
from rich.console import Console
from rich import print_json

# 创建不使用颜色的控制台实例
console = Console(
    # force_terminal=False,
    # color_system=None,
    # width=None,  # 自动检测宽度
    # legacy_windows=False,
    # no_color=True,
)

# from menglong import tool, ChatAgent, ChatMode
# from typing import Any, Dict, List

# CLIENT = None


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


# STATUS = {
#     "self_status": {},
#     "env_status": {},
# }


class AgentDemo:
    """Agent 客户端演示类"""

    def __init__(self, server_url="ws://localhost:8000/ws/metaverse"):
        self.server_url = server_url
        self.env_id = 1
        self.agent_id = 1
        self.agent_client = None
        self.messages = []

    def setup_event_listeners(self):
        """设置事件监听器"""

        def on_connect(data):
            message = f"✅ Agent 连接成功: {data}"
            console.print(message, style="green")
            self.messages.append(message)

        def on_message(data):
            message = f"📨 Agent 收到消息:"
            msg_data = data.get("data")
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
            msg_data = data.get("data", {})
            error = msg_data.get("error", "未知错误")
            console.print(message, style="yellow")
            RemoteContext.get_id_map().update({msg_data["id"]: error})
            self.messages.append(message)

        self.agent_client.add_event_listener("connect", on_connect)
        self.agent_client.add_event_listener("message", on_message)
        self.agent_client.add_event_listener("disconnect", on_disconnect)
        self.agent_client.add_event_listener("error", on_error)

    async def create_and_connect(self):
        """创建并连接 Agent 客户端"""
        console.print("🤖 创建 Agent 客户端", style="bold blue")
        console.print(f"📡 服务器: {self.server_url}")
        console.print(f"🌍 环境ID: {self.env_id}")
        console.print(f"🆔 Agent ID: {self.agent_id}")
        console.print("=" * 50)

        # 创建客户端
        self.agent_client = AgentClient(self.server_url, self.env_id, self.agent_id)
        self.setup_event_listeners()
        RemoteContext.set_client(self.agent_client)

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

    async def demo_auto_actions(self):
        """演示基本动作"""
        print("\n🎭 开始演示基本动作")
        print("=" * 30)

        # 1. 观察环境
        print("\n👀 动作 1: 观察环境")
        try:
            await self.agent_client.observe_environment()
            print("✅ 观察请求已发送")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"❌ 观察环境失败: {e}")

        # 2. 移动动作
        print("\n🚶 动作 2: 移动")
        moves = [
            ("north", "向北移动"),
            ("east", "向东移动"),
            ("south", "向南移动"),
            ("west", "向西移动"),
        ]

        for direction, description in moves:
            print(f"   {description}...")
            try:
                await self.agent_client.perform_action("move", [direction])
                print(f"   ✅ {description}请求已发送")
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"   ❌ {description}失败: {e}")

        # 3. 物品交互
        print("\n📦 动作 3: 物品交互")
        item_actions = [
            ("pickup", ["钥匙"], "拾取钥匙"),
            ("pickup", ["书本"], "拾取书本"),
            ("use", ["钥匙", "门"], "使用钥匙开门"),
            ("drop", ["书本"], "放下书本"),
        ]

        for action, params, description in item_actions:
            print(f"   {description}...")
            try:
                await self.agent_client.perform_action(action, params)
                print(f"   ✅ {description}请求已发送")
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"   ❌ {description}失败: {e}")

    async def interactive_mode(self):
        """交互模式：用户可以手动输入动作"""
        console.print("\n🎮 进入交互模式", style="bold cyan")
        console.print("=" * 20)
        console.print("可用命令:")
        # console.print("  task <prompt>")
        console.print("  message <action> <params> - 自定义动作")
        console.print("  quit - 退出交互模式")
        console.print()

        # 创建异步prompt session
        session = PromptSession()

        while True:
            # 在patch_stdout外部获取用户输入，避免颜色问题
            with patch_stdout():
                command = await session.prompt_async("🎯 请输入命令: ")

            command = command.strip()

            if not command:
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

            # except KeyboardInterrupt:
            #     print("\n👋 用户中断，退出交互模式")
            #     break
            # except Exception as e:
            #     print(f"❌ 命令执行错误: {e}")

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

        # try:
        # 连接
        if not await self.create_and_connect():
            return

        # 进入交互模式
        await self.interactive_mode()

        # 显示总结
        self.show_summary()

        # except KeyboardInterrupt:
        #     print("\n⚠️ 用户中断演示")
        # except Exception as e:
        #     print(f"\n❌ 演示过程中发生错误: {e}")
        # finally:
        #     await self.cleanup()

    async def run_auto_test(self):
        """自动测试模式：完整功能测试"""
        print("🧪 自动测试模式：完整功能")
        print("=" * 30)

        try:
            # 连接
            if not await self.create_and_connect():
                return

            # 基本动作演示
            await self.demo_basic_actions()

            # 高级动作演示
            await self.demo_advanced_actions()

            # Ping 演示
            await self.demo_ping_and_heartbeat()

            print("\n✅ Type2 自动测试完成")
            # 显示总结
            self.show_summary()

        except KeyboardInterrupt:
            print("\n⚠️ 用户中断测试")
        except Exception as e:
            print(f"\n❌ 测试过程中发生错误: {e}")
        finally:
            await self.cleanup()


import asyncio
from typing import Any, Dict

# from menglong import Model, ChatAgent, ChatMode, tool

# from demo_agent import get_client


def obs():
    console.print("haha", style="green")


async def drink():
    task = asyncio.create_task(_drink())
    task.add_done_callback(lambda t: asyncio.create_task(drink_done()))
    await task


async def _drink():
    console.print("开始喝水", style="blue")
    await asyncio.sleep(1)
    console.print("喝水中... 1s", style="cyan")
    await asyncio.sleep(1)
    console.print("喝水中... 2s", style="cyan")
    await asyncio.sleep(1)
    console.print("喝水结束", style="green")


async def drink_done():
    console.print("一共喝了 3s", style="bold green")


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
        custom_action = parts[1]
        params = parts[2] if len(parts) > 2 else ""
        # TODO
        # agent = ChatAgent()
        # RemoteContext.set_task_manager(agent.task_manager)
        # res = agent.chat(params, tools=[available_actions])
        # print(res)
        # await RemoteContext.client.perform_action(custom_action, params)
    else:
        print("❌ 请指定动作，如: chat dance")


# @tool(name="get_available_actions", description="获取当前可用的动作")
# async def get_available_actions() -> list[Dict[str, Any]]:
#     """获取当前可执行的动作描述"""
#     await asyncio.sleep(0)  # 模拟异步操作
#     return [{"name": name, "description": action} for name, action in DESC.items()]


# @tool(name="observe_state", description="获取当前状态")
# async def observe_state() -> Dict[str, Any]:
#     """获取当前状态"""
#     return RemoteContext.get_status()


async def get_response(request_id):
    """获取动作执行的响应"""

    while not RemoteContext.get_id_map().get(request_id):
        await asyncio.sleep(0.1)  # 等待响应
    response = RemoteContext.get_id_map().pop(request_id)

    return response


# @tool(name="perform_action", description="执行动作规划好的动作")
async def perform_action(action: str, params: Any):
    """执行动作"""
    print(f"🚀 执行动作: {action}, 参数: {params}")
    success = await RemoteContext.get_client().perform_action(action, params)
    print(f"执行动作的立刻结果 - success: {success}")
    response = await get_response(success)
    print_json(
        data=response,
    )
    # if success:
    #     RemoteContext.set_status({"任务{success}": f"正在 {action} 到 {params} 中"})
    #     return success
    # else:
    #     return f"执行动作失败: {action}，参数: {params}"


# @tool
async def available_actions() -> list[Dict[str, Any]]:
    """获取当前可用的动作"""
    return await perform_action("get_available_actions", {})


async def task(parts):
    if len(parts) > 1:
        custom_action = parts[0]
        params = parts[1]

        # 特别处理menglong库的颜色输出问题
        # 在patch_stdout环境中，需要确保menglong也能正确输出颜色

        console.print(f"🎯 要执行的任务: {params}", style="bold cyan")

        try:
            # 创建 ChatAgent - 确保在正确的环境下
            # agent = ChatAgent(
            #     mode=ChatMode.AUTO,
            #     system="你是一个专业的助手，能够自主完成各种任务。",
            # )

            # # 自动注册全局工具
            # agent.register_global_tools()

            # 定义任务
            task_description = params

            # 使用 arun 方法而不是 run 方法，避免 asyncio.run() 冲突
            # result = await agent.arun(task=task_description, max_iterations=5)

            # 显示执行结果
            # console.print(f"\n📊 执行结果:", style="bold green")
            # console.print(f"任务状态: {result['status']}")
            # console.print(f"执行时间: {result['execution_time']:.2f}秒")
            # console.print(
            #     f"执行轮次: {result['iterations']}/{result['max_iterations']}",
            # )
            # console.print(f"成功率: {result['success_rate']:.1%}")

        except Exception as e:
            console.print(f"❌ 任务执行失败: {e}", style="bold red")

    else:
        console.print("❌ 请指定动作，如: task desc", style="red")


DESC = {
    "move": {"description": "移动", "params": {"x": "移动的x坐标", "y": "移动的y坐标"}},
    "idle": {"description": "发呆", "params": {"duration": "发呆的持续时间"}},
}

ACTION = {"obs": obs, "chat": chat, "drink": drink, "message": message, "task": task}


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Star Client Agent 演示程序")
    parser.add_argument(
        "--mode",
        choices=["interactive", "autotest"],
        default="interactive",
        help="运行模式: interactive(交互式), autotest(自动测试-基本功能)",
    )
    parser.add_argument(
        "--server-url",
        default="ws://localhost:8000/ws/metaverse",
        help="服务器地址 (默认: ws://localhost:8000/ws/metaverse)",
    )
    parser.add_argument("--env-id", type=int, default=1, help="环境ID (默认: 1)")
    parser.add_argument("--agent-id", type=int, default=1, help="Agent ID (默认: 1)")

    args = parser.parse_args()

    console.print(
        f"🤖 Star Client Agent 演示程序 - 模式: {args.mode}", style="bold blue"
    )
    console.print(f"📡 服务器: {args.server_url}")
    console.print(f"🌍 环境ID: {args.env_id}")
    console.print(f"🆔 Agent ID: {args.agent_id}")
    console.print("=" * 60)

    # 创建演示实例
    demo = AgentDemo(args.server_url)
    demo.env_id = args.env_id
    demo.agent_id = args.agent_id

    # try:
    if args.mode == "interactive":
        console.print("🎮 交互式模式", style="bold cyan")
        await demo.run_interactive_demo()
    elif args.mode == "autotest":
        console.print("🧪 自动测试模式", style="bold yellow")
        await demo.run_auto_test()
    # except KeyboardInterrupt:
    #     print("\n👋 程序已退出")
    # except Exception as e:
    #     print(f"\n❌ 程序错误: {e}")


if __name__ == "__main__":
    # try:
    asyncio.run(main())
# except KeyboardInterrupt:
#     print("\n👋 程序已退出")
# except Exception as e:
#     print(f"\n❌ 程序错误: {e}")
