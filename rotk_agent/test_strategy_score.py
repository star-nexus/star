import asyncio
import json
from typing import Dict, Any
import sys
import os
from time import sleep

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


async def test_move_one_unit(
    server_url="ws://localhost:8000/ws/metaverse", env_id="env_1", agent_id="agent_test_move", faction="wei"
):
    client = AgentClient(server_url, env_id, agent_id)
    waiter = OutcomeWaiter(client)
    await client.connect()
    try:
        # 1) 获取阵营状态，拿到一个可用单位
        req_id = await client.send_action("get_faction_state", {"faction": faction})
        state =  await waiter.wait(req_id, timeout=10)
        sleep(1)
        res =    await client.send_action("strategy_ping", {"faction":"wei","score":0.5,"evidence":"先夺高地后推进"})
        print(res)
        sleep(1)

        print("Done.")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_move_one_unit())