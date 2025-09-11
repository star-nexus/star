import asyncio
import json
import sys
import os
from typing import Dict, Any, Optional

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


class TurnStartListener:
    def __init__(self, client: AgentClient):
        self.client = client
        self._future: Optional[asyncio.Future] = None

        def on_message(data):
            payload = data.get("payload", {})
            # 直接监听 type == turn_start 的消息
            if payload.get("type") == "turn_start":
                if self._future and not self._future.done():
                    self._future.set_result(payload)

        self.client.add_hub_listener("message", on_message)

    async def wait(self, timeout: float = 60.0) -> Any:
        # 创建一次性 future 等待一条 turn_start
        self._future = asyncio.get_event_loop().create_future()
        try:
            return await asyncio.wait_for(self._future, timeout=timeout)
        finally:
            self._future = None


async def test_turn_start_oneway(
    server_url: str = "ws://localhost:8000/ws/metaverse",
    env_id: str = "env_1",
    agent_id_wei: str = "agent_minimal_wei",
    agent_id_shu: str = "agent_minimal_shu",
):
    """
    最简测试：
      1) WEI 与 SHU 同时注册
      2) 仅 SHU 开启监听 turn_start
      3) 仅 WEI 发送 end_turn
      4) SHU 打印接收到的 turn_start
    """
    wei = AgentClient(server_url, env_id, agent_id_wei)
    shu = AgentClient(server_url, env_id, agent_id_shu)
    await asyncio.gather(wei.connect(), shu.connect())

    try:
        # 注册双方
        wei_waiter = OutcomeWaiter(wei)
        shu_waiter = OutcomeWaiter(shu)

        reg_wei_params = {
            "faction": "wei",
            "provider": "test",
            "model_id": "test-model",
            "base_url": "http://localhost",
            "agent_id": agent_id_wei,
            "version": "0.0.1",
            "note": "minimal",
            "enable_thinking": False,
        }
        reg_shu_params = {
            "faction": "shu",
            "provider": "test",
            "model_id": "test-model",
            "base_url": "http://localhost",
            "agent_id": agent_id_shu,
            "version": "0.0.1",
            "note": "minimal",
            "enable_thinking": False,
        }

        req_reg_wei = await wei.send_action("register_agent_info", reg_wei_params)
        req_reg_shu = await shu.send_action("register_agent_info", reg_shu_params)
        reg_wei = await wei_waiter.wait(req_reg_wei, timeout=15)
        reg_shu = await shu_waiter.wait(req_reg_shu, timeout=15)
        print("register(wei) =>", json.dumps(reg_wei, ensure_ascii=False, indent=2))
        print("register(shu) =>", json.dumps(reg_shu, ensure_ascii=False, indent=2))

        # 仅 SHU 开启监听
        shu_turn_listener = TurnStartListener(shu)
        await asyncio.sleep(0.05)

        # 并行：先开始监听，再发送动作，避免信号先到被错过
        turn_task = asyncio.create_task(shu_turn_listener.wait(timeout=60))
        await asyncio.sleep(0.01)

        req_end = await wei.send_action("end_turn", {"faction": "wei"})
        end_outcome = await wei_waiter.wait(req_end, timeout=20)
        print("end_turn(wei) =>", json.dumps(end_outcome, ensure_ascii=False, indent=2))

        # 等待并行监听结果
        turn_start = await turn_task
        print("turn_start(received_by_shu) =>", json.dumps(turn_start, ensure_ascii=False, indent=2))

        return {"reg_wei": reg_wei, "reg_shu": reg_shu, "end_outcome": end_outcome, "turn_start": turn_start}
    finally:
        await asyncio.gather(wei.disconnect(), shu.disconnect())




async def test_turn_start_roundtrip(
    server_url: str = "ws://localhost:8000/ws/metaverse",
    env_id: str = "env_1",
    agent_id_wei: str = "agent_roundtrip_wei",
    agent_id_shu: str = "agent_roundtrip_shu",
):
    """
    复杂用例（双向验证）：
      1) WEI 与 SHU 同时注册
      2) 同时创建监听器对象（不立即等待）
      3) 并行启动 SHU 的监听任务，WEI 发送 end_turn，SHU 输出 turn_start
      4) 并行启动 WEI 的监听任务，SHU 发送 end_turn，WEI 输出 turn_start
    """
    wei = AgentClient(server_url, env_id, agent_id_wei)
    shu = AgentClient(server_url, env_id, agent_id_shu)
    await asyncio.gather(wei.connect(), shu.connect())

    try:
        # 注册双方
        wei_waiter = OutcomeWaiter(wei)
        shu_waiter = OutcomeWaiter(shu)
        reg_wei = await wei_waiter.wait(await wei.send_action("register_agent_info", {
            "faction": "wei",
            "provider": "test",
            "model_id": "test-model",
            "base_url": "http://localhost",
            "agent_id": agent_id_wei,
            "version": "0.0.1",
            "note": "roundtrip",
            "enable_thinking": False,
        }), timeout=15)
        reg_shu = await shu_waiter.wait(await shu.send_action("register_agent_info", {
            "faction": "shu",
            "provider": "test",
            "model_id": "test-model",
            "base_url": "http://localhost",
            "agent_id": agent_id_shu,
            "version": "0.0.1",
            "note": "roundtrip",
            "enable_thinking": False,
        }), timeout=15)
        print("register(wei) =>", json.dumps(reg_wei, ensure_ascii=False, indent=2))
        print("register(shu) =>", json.dumps(reg_shu, ensure_ascii=False, indent=2))

        # 创建监听器
        wei_listener = TurnStartListener(wei)
        shu_listener = TurnStartListener(shu)

        # Phase A: SHU 监听，WEI 发送
        shu_task = asyncio.create_task(shu_listener.wait(timeout=60))
        await asyncio.sleep(0.01)
        end_outcome_wei = await wei_waiter.wait(await wei.send_action("end_turn", {"faction": "wei"}), timeout=20)
        print("end_turn(wei) =>", json.dumps(end_outcome_wei, ensure_ascii=False, indent=2))
        shu_turn_start = await shu_task
        print("turn_start(received_by_shu) =>", json.dumps(shu_turn_start, ensure_ascii=False, indent=2))

        # Phase B: WEI 监听，SHU 发送
        wei_task = asyncio.create_task(wei_listener.wait(timeout=60))
        await asyncio.sleep(0.01)
        end_outcome_shu = await shu_waiter.wait(await shu.send_action("end_turn", {"faction": "shu"}), timeout=20)
        print("end_turn(shu) =>", json.dumps(end_outcome_shu, ensure_ascii=False, indent=2))
        wei_turn_start = await wei_task
        print("turn_start(received_by_wei) =>", json.dumps(wei_turn_start, ensure_ascii=False, indent=2))

        return {
            "reg_wei": reg_wei,
            "reg_shu": reg_shu,
            "end_outcome_wei": end_outcome_wei,
            "shu_turn_start": shu_turn_start,
            "end_outcome_shu": end_outcome_shu,
            "wei_turn_start": wei_turn_start,
        }
    finally:
        await asyncio.gather(wei.disconnect(), shu.disconnect())


if __name__ == "__main__":
    # asyncio.run(test_turn_start_oneway())
    asyncio.run(test_turn_start_roundtrip())