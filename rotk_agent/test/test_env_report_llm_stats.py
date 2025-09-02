import asyncio
import json
import sys
import os
from typing import Dict, Any

# 允许从项目根导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import AgentClient


class OutcomeWaiter:
    def __init__(self, client: AgentClient):
        self.client = client
        self._pending: Dict[int, asyncio.Future] = {}

        def on_message(data):
            payload = data.get("payload", {})
            if payload.get("type") == "outcome":
                req_id = payload.get("id")
                outcome = payload.get("outcome")
                fut = self._pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(outcome)

        def on_error(data):
            payload = data.get("payload", {})
            req_id = payload.get("id")
            error = payload.get("error", "unknown error")
            fut = self._pending.pop(req_id, None)
            if fut and not fut.done():
                fut.set_result({"success": False, "error": error})

        self.client.add_hub_listener("message", on_message)
        self.client.add_hub_listener("error", on_error)

    async def wait(self, req_id: int, timeout: float = 15.0) -> Any:
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(req_id, None)


async def test_env_report_llm_stats(
    server_url: str = "ws://localhost:8000/ws/metaverse",
    env_id: str = "env_1",
    agent_id: str = "agent_test_register_info",
):
    """
    向环境直接发送 report_llm_stats 动作，并获取 ENV 返回结果。
    运行前请确保 ENV WebSocket 服务已启动，地址与 env_id 正确。
    """
    client = AgentClient(server_url, env_id, agent_id)
    waiter = OutcomeWaiter(client)
    await client.connect()
    try:
        # 构造参数（可按需调整）
        params = {
            "faction": "shu",
            "api_stats": {
                "total_calls": 10,
                "successful_calls": 9,
                "failed_calls": 1,
                "success_rate": 90.0,
            },
            "provider": "openai",
            "model_id": "gpt-4o-mini",
        }

        # 直接发送 report_llm_stats 动作
        req_id = await client.send_action("report_llm_stats", params)
        outcome = await waiter.wait(req_id, timeout=15)

        print("report_llm_stats =>", json.dumps(outcome, ensure_ascii=False, indent=2))
        return outcome
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_env_report_llm_stats())


