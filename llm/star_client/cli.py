"""
简单的命令行客户端实现
"""

import asyncio
import argparse
from typing import Optional

from .client import AgentClient, EnvironmentClient, HumanClient
from .utils import create_default_handlers, MessageProcessor, DEFAULT_ACTION_HANDLERS
from .types import ClientType


class CLIClient:
    """命令行客户端包装器"""

    def __init__(self, client_type: str, server_url: str, **kwargs):
        self.client_type = client_type

        # 创建对应类型的客户端
        if client_type == ClientType.AGENT.value:
            self.client = AgentClient(
                server_url, kwargs.get("env_id", 1), kwargs.get("agent_id", 1)
            )
        elif client_type == ClientType.ENVIRONMENT.value:
            self.client = EnvironmentClient(server_url, kwargs.get("env_id", 1))
        elif client_type == ClientType.HUMAN.value:
            self.client = HumanClient(
                server_url, kwargs.get("env_id", 1), kwargs.get("human_id", 1)
            )
        else:
            raise ValueError(f"不支持的客户端类型: {client_type}")

        # 设置消息处理器
        self.processor = MessageProcessor()
        for action, handler in DEFAULT_ACTION_HANDLERS.items():
            self.processor.register_action(action, handler)

        # 设置默认事件处理器
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """设置事件处理器"""
        default_handlers = create_default_handlers()

        for event, handler in default_handlers.items():
            self.client.add_event_listener(event, handler)

        # 添加消息处理逻辑
        async def message_handler(data):
            response = await self.processor.process_message(data.get("data", {}))
            if response:
                await self.client.send_message(
                    "response", response, target=data.get("msg_from")
                )

        self.client.add_event_listener("message", message_handler)

    async def start(self):
        """启动客户端"""
        try:
            await self.client.connect()
            print(f"{self.client_type.upper()} 客户端已启动")

            # 保持连接
            while self.client.connected:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n正在退出...")
        finally:
            await self.client.disconnect()


async def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="Agent Client SDK 命令行工具")
    parser.add_argument(
        "--type", choices=["agent", "env", "human"], required=True, help="客户端类型"
    )
    parser.add_argument(
        "--server",
        default="ws://localhost:8000/ws/metaverse",
        help="WebSocket 服务器地址",
    )
    parser.add_argument("--env_id", type=int, default=1, help="环境 ID")
    parser.add_argument("--agent_id", type=int, default=1, help="智能体 ID")
    parser.add_argument("--human_id", type=int, default=1, help="人类 ID")

    args = parser.parse_args()

    # 创建并启动客户端
    cli_client = CLIClient(
        args.type,
        args.server,
        env_id=args.env_id,
        agent_id=args.agent_id,
        human_id=args.human_id,
    )

    await cli_client.start()


if __name__ == "__main__":
    asyncio.run(main())
