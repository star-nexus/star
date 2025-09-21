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


async def test_get_faction_state(
    server_url: str = "ws://localhost:8000/ws/metaverse",
    env_id: str = "env_1",
    agent_id: str = "agent_test_register_info",
    faction: str = "shu"
):
    """
    直接测试 get_faction_state 动作获取阵营状态。
    运行前请确保 ENV WebSocket 服务已启动，地址与 env_id 正确。
    """
    client = AgentClient(server_url, env_id, agent_id)
    waiter = OutcomeWaiter(client)
    await client.connect()
    try:
        # 直接构造 get_faction_state 参数
        params = {
            "faction": faction
        }

        print(f"Testing get_faction_state for faction: {faction}")
        print("=" * 60)

        # 直接发送 get_faction_state 动作
        req_id = await client.send_action("get_faction_state", params)
        outcome = await waiter.wait(req_id, timeout=15)

        print("get_faction_state =>")
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        
        # 验证返回结果的基本结构
        if isinstance(outcome, dict):
            if outcome.get("success"):
                print(f"\n✅ Successfully retrieved faction state for {faction}")
                
                # 检查关键字段
                if "faction" in outcome:
                    print(f"   Faction: {outcome['faction']}")
                if "total_units" in outcome:
                    print(f"   Total units: {outcome['total_units']}")
                if "alive_units" in outcome:
                    print(f"   Alive units: {outcome['alive_units']}")
                if "actionable_units" in outcome:
                    print(f"   Actionable units: {outcome['actionable_units']}")
                if "units" in outcome and isinstance(outcome["units"], list):
                    print(f"   Units list length: {len(outcome['units'])}")
                    if outcome["units"]:
                        first_unit = outcome["units"][0]
                        print(f"   First unit example: {json.dumps(first_unit, ensure_ascii=False, indent=2)}")
            else:
                print(f"\n❌ Failed to retrieve faction state: {outcome.get('error', 'Unknown error')}")
        else:
            print(f"\n⚠️ Unexpected response format: {type(outcome)}")
        
        return outcome
    finally:
        await client.disconnect()


async def test_multiple_factions(
    server_url: str = "ws://localhost:8000/ws/metaverse",
    env_id: str = "env_1",
    agent_id: str = "agent_test_register_info"
):
    """
    测试多个阵营的状态获取
    """
    factions = ["wei", "shu", "wu"]
    results = {}
    
    for faction in factions:
        print(f"\n{'='*20} Testing faction: {faction} {'='*20}")
        try:
            result = await test_get_faction_state(
                server_url=server_url,
                env_id=env_id,
                agent_id=f"{agent_id}_{faction}",
                faction=faction
            )
            results[faction] = result
        except Exception as e:
            print(f"❌ Error testing faction {faction}: {e}")
            results[faction] = {"error": str(e)}
    
    print(f"\n{'='*20} Summary {'='*20}")
    for faction, result in results.items():
        if isinstance(result, dict) and result.get("success"):
            total = result.get("total_units", 0)
            alive = result.get("alive_units", 0)
            actionable = result.get("actionable_units", 0)
            print(f"{faction}: {total} total, {alive} alive, {actionable} actionable")
        else:
            print(f"{faction}: Failed - {result.get('error', 'Unknown error')}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test get_faction_state action")
    parser.add_argument("--faction", default="shu", choices=["wei", "shu", "wu"], 
                       help="Faction to test (default: shu)")
    parser.add_argument("--all", action="store_true", 
                       help="Test all factions")
    parser.add_argument("--server", default="ws://localhost:8000/ws/metaverse",
                       help="Server URL (default: ws://localhost:8000/ws/metaverse)")
    parser.add_argument("--env-id", default="env_1",
                       help="Environment ID (default: env_1)")
    
    args = parser.parse_args()
    
    if args.all:
        asyncio.run(test_multiple_factions(
            server_url=args.server,
            env_id=args.env_id
        ))
    else:
        asyncio.run(test_get_faction_state(
            server_url=args.server,
            env_id=args.env_id,
            faction=args.faction
        ))
