#!/usr/bin/env python3
"""
测试智能延迟功能的脚本
验证Agent在移动动作后会正确等待动画完成
"""

import asyncio
import json
import sys
import os
from time import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import AgentClient

class TestAgent:
    def __init__(self, server_url="ws://localhost:8000/ws/metaverse", env_id="env_1", agent_id="test_smart_delay", faction="wei"):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.faction = faction
        self.client = None
        self._pending = {}

    async def connect(self):
        """连接到服务器"""
        self.client = AgentClient(self.server_url, self.env_id, self.agent_id)
        
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
        
        await self.client.connect()
        print(f"✅ 连接成功: {self.agent_id}")

    async def send_action_and_wait(self, action, params):
        """发送动作并等待响应"""
        req_id = await self.client.send_action(action, params)
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout=15.0)
        finally:
            self._pending.pop(req_id, None)

    def calculate_smart_delay(self, action: str, params: dict, response: dict) -> float:
        """计算智能延迟时间（模拟Agent中的逻辑）"""
        if not isinstance(response, dict) or not response.get("success", False):
            return 0.0
        
        if action == "move":
            return self._calculate_move_delay(params, response)
        elif action == "attack":
            return 0.8
        elif action in ["get_faction_state", "observation", "get_action_list"]:
            return 0.0
        else:
            return 0.5

    def _calculate_move_delay(self, params: dict, response: dict) -> float:
        """计算移动延迟时间"""
        try:
            # 从响应中获取预估时间
            if "movement_details" in response:
                estimated_duration = response["movement_details"].get("estimated_duration_seconds", 0)
                if estimated_duration > 0:
                    return estimated_duration * 1.1
                
                path_length = response["movement_details"].get("path_length", 0)
                if path_length > 0:
                    return path_length / 2.0 + 0.2
            
            return 1.0
        except Exception:
            return 1.0

    async def test_smart_delay(self):
        """测试智能延迟功能"""
        print("🧪 开始测试智能延迟功能...")
        
        # 1. 获取阵营状态
        print("\n📊 获取阵营状态...")
        faction_response = await self.send_action_and_wait("get_faction_state", {"faction": self.faction})
        
        if not faction_response.get("success"):
            print(f"❌ 获取阵营状态失败: {faction_response}")
            return
        
        units = faction_response.get("units", [])
        if not units:
            print(f"❌ 没有找到可用单位")
            return
        
        unit = units[0]
        unit_id = unit["unit_id"]
        current_pos = unit["position"]
        print(f"✅ 选择单位 {unit_id}，当前位置: {current_pos}")
        
        # 2. 执行移动动作并测试延迟
        target_positions = [
            {"col": current_pos["col"] + 1, "row": current_pos["row"]},  # 短距离
            {"col": current_pos["col"] - 2, "row": current_pos["row"] - 1},  # 中距离
            {"col": current_pos["col"] + 3, "row": current_pos["row"] + 2},  # 长距离
        ]
        
        for i, target_pos in enumerate(target_positions):
            print(f"\n🎯 测试移动 #{i+1}: 移动到 {target_pos}")
            
            # 记录开始时间
            start_time = time()
            
            # 发送移动指令
            move_response = await self.send_action_and_wait("move", {
                "unit_id": unit_id,
                "target_position": target_pos
            })
            
            action_time = time() - start_time
            print(f"📡 动作响应时间: {action_time:.2f}s")
            print(f"📄 响应内容: {json.dumps(move_response, indent=2, ensure_ascii=False)}")
            
            if move_response.get("success"):
                # 计算智能延迟时间
                delay_time = self.calculate_smart_delay("move", {"unit_id": unit_id, "target_position": target_pos}, move_response)
                print(f"⏳ 计算得出的智能延迟时间: {delay_time:.2f}s")
                
                if delay_time > 0:
                    print(f"⏰ 开始等待 {delay_time}s...")
                    delay_start = time()
                    await asyncio.sleep(delay_time)
                    actual_delay = time() - delay_start
                    print(f"✅ 延迟完成，实际等待时间: {actual_delay:.2f}s")
                
                # 验证位置是否已更新
                print("🔍 验证单位位置...")
                verify_response = await self.send_action_and_wait("get_faction_state", {"faction": self.faction})
                if verify_response.get("success"):
                    verify_units = verify_response.get("units", [])
                    verify_unit = next((u for u in verify_units if u["unit_id"] == unit_id), None)
                    if verify_unit:
                        verify_pos = verify_unit["position"]
                        print(f"📍 验证位置: {verify_pos}")
                        if verify_pos == target_pos:
                            print("✅ 位置验证成功！单位已到达目标位置")
                        else:
                            print(f"⚠️ 位置可能未完全更新，当前: {verify_pos}, 目标: {target_pos}")
                    else:
                        print("❌ 无法找到验证单位")
                else:
                    print("❌ 验证请求失败")
            else:
                print(f"❌ 移动失败: {move_response.get('message', 'Unknown error')}")
            
            print("-" * 60)

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.disconnect()
            print("✅ 连接已断开")

async def main():
    """主函数"""
    agent = TestAgent()
    
    try:
        await agent.connect()
        await agent.test_smart_delay()
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
