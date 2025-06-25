"""
LLM系统WebSocket交互示例
展示如何通过WebSocket协议与LLM系统进行交互
"""

import asyncio
import json
import websockets
from typing import Dict, Any


class LLMAgentClient:
    """LLM代理客户端示例"""

    def __init__(self, server_url: str, env_id: int, agent_id: str):
        self.server_url = server_url
        self.env_id = env_id
        self.agent_id = agent_id
        self.websocket = None
        self.action_counter = 0

    async def connect(self):
        """连接到LLM环境服务器"""
        try:
            # 构建连接URL
            url = f"{self.server_url}/agent/{self.env_id}/{self.agent_id}"
            print(f"连接到: {url}")

            self.websocket = await websockets.connect(url)
            print(f"✅ 代理 {self.agent_id} 已连接到环境 {self.env_id}")

            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    async def send_action(
        self, action: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """发送动作到环境"""
        if not self.websocket:
            raise Exception("未连接到服务器")

        self.action_counter += 1
        action_id = f"action_{self.action_counter}"

        message = {
            "instruction": "message",
            "data": {"id": action_id, "action": action, "parameters": parameters},
            "msg_from": {
                "role_type": "agent",
                "env_id": self.env_id,
                "agent_id": self.agent_id,
            },
            "timestamp": asyncio.get_event_loop().time(),
        }

        print(f"📤 发送动作: {action}")
        await self.websocket.send(json.dumps(message))

        # 等待响应
        response = await self.websocket.recv()
        result = json.loads(response)

        print(f"📥 收到响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result

    async def request_observation(
        self, observation_level: str = "faction", **kwargs
    ) -> Dict[str, Any]:
        """请求观测信息"""
        parameters = {"observation_level": observation_level, **kwargs}

        return await self.send_action("observation", parameters)

    async def move_unit(self, unit_id: int, target_position: list) -> Dict[str, Any]:
        """移动单位"""
        parameters = {"unit_id": unit_id, "target_position": target_position}

        return await self.send_action("move", parameters)

    async def attack_unit(self, attacker_id: int, target_id: int) -> Dict[str, Any]:
        """攻击单位"""
        parameters = {"attacker_id": attacker_id, "target_id": target_id}

        return await self.send_action("attack", parameters)

    async def defend_unit(self, unit_id: int) -> Dict[str, Any]:
        """设置单位防御"""
        parameters = {"unit_id": unit_id}

        return await self.send_action("defend", parameters)

    async def scout_area(
        self, unit_id: int, target_area: list = None
    ) -> Dict[str, Any]:
        """侦察区域"""
        parameters = {"unit_id": unit_id}
        if target_area:
            parameters["target_area"] = target_area

        return await self.send_action("scout", parameters)

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            print(f"👋 代理 {self.agent_id} 已断开连接")


async def demo_basic_interaction():
    """基本交互演示"""
    print("=== 基本交互演示 ===")

    # 创建代理客户端
    client = LLMAgentClient(
        server_url="ws://localhost:8000/ws/metaverse", env_id=1, agent_id=5
    )

    try:
        # 连接到服务器
        if not await client.connect():
            return

        # 1. 获取初始观测
        print("\n1. 获取阵营观测...")
        obs_result = await client.request_observation(
            observation_level="faction", faction="WEI", include_hidden=False
        )

        # 2. 移动单位（假设有ID为1的单位）
        print("\n2. 移动单位...")
        move_result = await client.move_unit(unit_id=1, target_position=[6, 7])

        # 3. 获取单位观测
        print("\n3. 获取单位观测...")
        unit_obs = await client.request_observation(observation_level="unit", unit_id=1)

        # 4. 设置防御
        print("\n4. 设置单位防御...")
        defend_result = await client.defend_unit(unit_id=1)

        # 5. 侦察
        print("\n5. 执行侦察...")
        scout_result = await client.scout_area(unit_id=1)

    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
    finally:
        await client.disconnect()


async def demo_tactical_scenario():
    """战术场景演示"""
    print("\n=== 战术场景演示 ===")

    client = LLMAgentClient(
        server_url="ws://localhost:8000/ws/metaverse",
        env_id=1,
        agent_id=6,
    )

    try:
        if not await client.connect():
            return

        # 模拟一个简单的战术序列
        print("\n场景：发现敌军，准备攻击")

        # 1. 获取全局观测，了解战场情况
        print("1. 侦察战场...")
        battlefield_obs = await client.request_observation("godview")

        # 2. 移动己方单位接近敌人
        print("2. 移动部队接近敌人...")
        await client.move_unit(unit_id=1, target_position=[5, 5])

        # 3. 再次观测，确认位置
        print("3. 确认位置...")
        unit_obs = await client.request_observation("unit", unit_id=1)

        # 4. 发起攻击
        print("4. 发起攻击...")
        attack_result = await client.attack_unit(attacker_id=1, target_id=2)

        # 5. 攻击后观测，评估战果
        print("5. 评估战果...")
        post_battle_obs = await client.request_observation("faction", faction="WEI")

    except Exception as e:
        print(f"❌ 战术演示过程中出错: {e}")
    finally:
        await client.disconnect()


async def demo_multiplayer_scenario():
    """多玩家场景演示"""
    print("\n=== 多玩家场景演示 ===")

    # 创建多个代理
    clients = [
        LLMAgentClient("ws://localhost:8000/ws/metaverse", 1, 7),
        LLMAgentClient("ws://localhost:8000/ws/metaverse", 1, 8),
        LLMAgentClient("ws://localhost:8000/ws/metaverse", 1, 9),
    ]

    try:
        # 所有玩家连接
        for client in clients:
            await client.connect()

        # 各玩家执行不同的行动
        tasks = []

        # 魏国玩家：侦察和移动
        tasks.append(clients[0].request_observation("faction", faction="WEI"))
        tasks.append(clients[0].move_unit(unit_id=1, target_position=[4, 4]))

        # 蜀国玩家：防御准备
        tasks.append(clients[1].request_observation("faction", faction="SHU"))
        tasks.append(clients[1].defend_unit(unit_id=2))

        # 吴国玩家：侦察
        tasks.append(clients[2].request_observation("faction", faction="WU"))
        tasks.append(clients[2].scout_area(unit_id=3))

        # 并发执行所有动作
        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("所有玩家动作执行完成")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"动作 {i} 执行失败: {result}")
            else:
                print(f"动作 {i} 执行成功")

    except Exception as e:
        print(f"❌ 多玩家演示过程中出错: {e}")
    finally:
        # 断开所有连接
        for client in clients:
            await client.disconnect()


def create_test_message_examples():
    """创建测试消息示例"""
    print("\n=== WebSocket消息格式示例 ===")

    # 移动动作消息
    move_message = {
        "instruction": "message",
        "data": {
            "id": "move_001",
            "action": "move",
            "parameters": {"unit_id": 123, "target_position": [6, 8]},
        },
        "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "player_1"},
        "timestamp": 1637123456.789,
    }

    # 观测请求消息
    observation_message = {
        "instruction": "message",
        "data": {
            "id": "obs_001",
            "action": "faction_observation",
            "parameters": {"faction": "WEI", "include_hidden": False},
        },
        "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "player_1"},
        "timestamp": 1637123456.789,
    }

    # 攻击动作消息
    attack_message = {
        "instruction": "message",
        "data": {
            "id": "attack_001",
            "action": "attack",
            "parameters": {"attacker_id": 123, "target_id": 456},
        },
        "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "player_1"},
        "timestamp": 1637123456.789,
    }

    examples = {
        "move_action": move_message,
        "observation_request": observation_message,
        "attack_action": attack_message,
    }

    print("消息格式示例:")
    for name, message in examples.items():
        print(f"\n{name}:")
        print(json.dumps(message, indent=2, ensure_ascii=False))


async def main():
    """主函数"""
    print("LLM系统WebSocket交互演示")
    print("=" * 50)

    # 显示消息格式示例
    create_test_message_examples()

    # 注意：以下演示需要LLM服务器运行在localhost:8000
    print("\n注意：以下演示需要LLM服务器运行在localhost:8000")
    print("如果服务器未运行，演示将显示连接错误")

    try:
        # 基本交互演示
        await demo_basic_interaction()

        # 等待一下
        await asyncio.sleep(1)

        # 战术场景演示
        await demo_tactical_scenario()

        # 等待一下
        await asyncio.sleep(1)

        # 多玩家场景演示
        await demo_multiplayer_scenario()

    except KeyboardInterrupt:
        print("\n用户中断演示")
    except Exception as e:
        print(f"\n演示过程中出现错误: {e}")

    print("\n演示结束")


if __name__ == "__main__":
    asyncio.run(main())
