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


def _neighbors(col: int, row: int):
    # pointy/flat axial neighbor set used by env
    directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    for dq, dr in directions:
        yield col + dq, row + dr

async def test_move_one_unit(
    server_url="ws://localhost:8000/ws/metaverse", env_id="env_1", agent_id="agent_test_move", faction="wei"
):
    client = AgentClient(server_url, env_id, agent_id)
    waiter = OutcomeWaiter(client)
    await client.connect()
    try:
        # 1) 获取阵营状态，拿到一个可用单位
        req_id = await client.send_action("get_faction_state", {"faction": faction})
        state = await waiter.wait(req_id, timeout=10)
        units = state.get("units", [])
        if not units:
            print("No active units found for faction:", faction)
            return
        unit = units[0]
        unit_id = unit["unit_id"]
        pos = unit.get("position", {})
        col, row = pos.get("col"), pos.get("row")
        print(f"Try moving unit {unit_id} from ({col}, {row})")

        # 2) 尝试移动到相邻位置，直到一次成功或全部失败
        moved = False
        for ncol, nrow in _neighbors(col, row):
            req_id = await client.send_action(
                "move",
                {"unit_id": unit_id, "target_position": {"col": ncol, "row": nrow}},
            )
            outcome = await waiter.wait(req_id, timeout=15)
            print(f"move -> ({ncol}, {nrow}) ->", json.dumps(outcome, ensure_ascii=False))
            if outcome and outcome.get("success"):
                moved = True
                break
        ### 两次 action 的间隔
        sleep(0.5)
        ### 两次 action 的间隔
        ###
        # 2) 尝试移动到相邻位置，直到一次成功或全部失败
        ncol = -3
        nrow = -2
        req_id = await client.send_action(
            "move",
            {"unit_id": unit_id, "target_position": {"col": ncol, "row": nrow}},
        )
        outcome = await waiter.wait(req_id, timeout=15)
        if outcome and outcome.get("success"):
            print(f"move -> ({ncol}, {nrow}) ->", json.dumps(outcome, ensure_ascii=False))
        else:
            print(outcome)

        # 3) 若失败且服务给出建议位点，则尝试建议位点
        if not moved:
            # 再查一次可读结果（可选）
            # 也可直接从上次 outcome 中读取 'adjacent_positions'
            print("No adjacent move succeeded; trying suggested positions if available...")
            # 重新请求一次占位失败的典型结构并尝试
            # 这里省略重新提取，按你的日志直接在失败返回里取 'adjacent_positions'
            # 具体逻辑可按需要缓存上一次失败的 outcome
        print("Done.")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_move_one_unit())