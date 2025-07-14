"""
LLM系统 - 通过Star Client WebSocket框架与外部LLM通信，执行观测和动作
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple

from rich import print_json
from framework import System, World
from ..prefabs.config import Faction, PlayerType, GameMode

from protocol.star_client import SyncWebSocketClient, ClientInfo
from .llm_action_handler import LLMActionHandler
from .llm_observation_system import LLMObservationSystem, ObservationLevel

# from menglong import Model, ChatAgent, ChatMode, tool

# from prompt_toolkit import PromptSession
# from prompt_toolkit.patch_stdout import patch_stdout


class SyncEnvClient(SyncWebSocketClient):
    """同步环境客户端"""

    def __init__(self, server_url: str, env_id: int):
        client_info = ClientInfo(role_type="env", env_id=env_id)
        super().__init__(server_url, client_info)

        self.connected_agents = {}

    def _build_connection_url(self) -> str:
        """构建环境连接 URL"""
        return f"{self.server_url}/env/{self.client_info.env_id}"

    def response_to_agent(self, agent_id, action_id, outcome: str, outcome_type="str"):
        """执行动作 - 同步接口"""

        return self.send_message(
            "message",
            {
                "type": "outcome",
                "id": action_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
            target={
                "role_type": "agent",
                "env_id": self.client_info.env_id,
                "agent_id": agent_id,
            },
        )


class LLMSystem(System):

    def __init__(self):
        super().__init__()
        self.name = "LLMSystem"

    def initialize(self, world):
        self.world = world

        # 初始化动作处理器和观测系统
        self.action_handler = LLMActionHandler(world)
        self.observation_system = LLMObservationSystem(world)

        # 使用同步客户端
        self.client = SyncEnvClient(
            server_url="ws://localhost:8000/ws/metaverse",
            env_id=1,
        )
        self.add_listener()
        self.actions = {}
        self.add_env_actions()
        self.connect()

        return

    def add_listener(self):
        # 添加事件监听器
        self.client.add_event_listener("message", self.on_message)
        self.client.add_event_listener("connect", self.on_connect)
        self.client.add_event_listener("disconnect", self.on_disconnect)
        self.client.add_event_listener("error", self.on_error)

    def add_env_actions(self):
        # 动作处理
        self.actions["move"] = self.handle_move
        self.actions["attack"] = self.handle_attack
        self.actions["defend"] = self.handle_defend
        self.actions["scout"] = self.handle_scout
        self.actions["retreat"] = self.handle_retreat
        self.actions["fortify"] = self.handle_fortify
        self.actions["patrol"] = self.handle_patrol
        self.actions["end_turn"] = self.handle_end_turn
        self.actions["select_unit"] = self.handle_select_unit
        self.actions["formation"] = self.handle_formation

        # 观测请求
        self.actions["observation"] = self.handle_observation
        self.actions["unit_observation"] = self.handle_unit_observation
        self.actions["faction_observation"] = self.handle_faction_observation
        self.actions["godview_observation"] = self.handle_godview_observation
        self.actions["limited_observation"] = self.handle_limited_observation
        self.actions["tactical_observation"] = self.handle_tactical_observation

        # 状态查询指令
        self.actions["get_unit_list"] = self.handle_get_unit_list
        self.actions["get_unit_info"] = self.handle_get_unit_info
        self.actions["get_faction_units"] = self.handle_get_faction_units
        self.actions["get_game_state"] = self.handle_get_game_state
        self.actions["get_map_info"] = self.handle_get_map_info
        self.actions["get_battle_status"] = self.handle_get_battle_status
        self.actions["get_action_list"] = self.handle_get_available_actions
        self.actions["get_unit_capabilities"] = self.handle_get_unit_capabilities
        self.actions["get_visibility_info"] = self.handle_get_visibility_info
        self.actions["get_strategic_summary"] = self.handle_get_strategic_summary

    # === WebSocket 事件处理方法 ===

    def on_message(self, envelope):
        """处理接收到的消息"""
        print(f"LLMSystem received message")
        try:
            msg_from = envelope.get("msg_from", {})
            msg_data = envelope.get("data", {})
            # instruction = envelope.get("instruction", "")

            # 提取 agent 信息
            agent_id = msg_from.get("agent_id")
            if agent_id:
                self.client.connected_agents[agent_id] = msg_from

            self.exec_action(envelope)

            # if msg_type == "observation":
            #     self.handle_observation(msg_from, msg_data)
            # elif msg_type == "action":
            #     self.handle_action(msg_from, msg_data)
            # else:
            #     # 未知消息类型
            #     self.send_error_response(msg_from, f"Unknown message type: {msg_type}")

        except Exception as e:
            print(f"消息处理错误: {e}")
            if "msg_from" in locals():
                self.send_error_response(msg_from, f"Message processing error: {e}")

    def on_connect(self, message):
        print("LLMSystem connected", message)

    def on_disconnect(self, message):
        print("LLMSystem disconnected", message)

    def on_error(self, error):
        print(f"LLMSystem error: {error}")

    # === WebSocket 客户端方法 ===

    def connect(self):
        """连接到服务器 - 同步方法"""
        return self.client.connect()

    def disconnect(self):
        """断开连接 - 同步方法"""
        return self.client.disconnect()

    def send_message(self, message, instruction=None, target_id=None):
        """发送消息 - 同步方法"""
        return self.client.send_message(instruction or "message", message, target_id)

    def response_to_agent(self, agent_id, action_id, outcome: str, outcome_type="str"):
        """执行动作 - 同步接口"""
        return self.client.response_to_agent(agent_id, action_id, outcome, outcome_type)

    def subscribe_events(self):
        return super().subscribe_events()

    def update(self, dt):
        # print(f"LLMSystem update: {dt}")
        # with patch_stdout():
        #     command = self.session.prompt(
        #         "💬 输入命令 (输入 'quit' 退出): ",
        #         completer=None,
        #         complete_while_typing=True,
        #     )

        # command = command.strip()

        # if not command:
        #     return

        # if command.lower() == "quit":
        #     print("👋 退出交互模式")
        #     return

        # parts = command.split()
        # action = parts[0].lower()

        # print(f"🎯 识别到命令: {action}")
        # print(f"   参数: {parts[1:] if len(parts) > 1 else '无'}")

        # match action:
        #     case "chat":
        #         self.exec_action(
        #             {
        #                 "instruction": "message",
        #                 "data": {"action": "chat", "parameters": "你好聊天么？"},
        #                 "msg_from": {
        #                     "role_type": "agent",
        #                     "env_id": 1,
        #                     "agent_id": 2,
        #                 },
        #                 "msg_to": {
        #                     "role_type": "agent",
        #                     "env_id": 1,
        #                     "agent_id": 1,
        #                 },
        #                 "timestamp": time.time(),
        #             }
        #         )
        #     case _:
        #         print(f"❌ 未知命令: {command}")
        #         print("输入 'quit' 退出，或查看上方的可用命令列表")
        pass

    # === ENV 方法 ===
    def exec_action(self, message):
        """执行动作 - 同步方法"""
        agent_id = message.get("msg_from").get("agent_id")
        data = message.get("data", {})
        action_id = data.get("id")
        action = data.get("action")
        params = data.get("parameters", {})

        try:
            if action in self.actions:
                res = self.actions[action](params)
                print(f"{action} response: {res}")
                self.client.response_to_agent(agent_id, action_id, res, "str")
            else:
                print(f"未知动作: {action}")
                error_msg = {
                    "success": False,
                    "error": f"未知动作: {action}",
                    "supported_actions": list(self.actions.keys()),
                }
                self.client.response_to_agent(agent_id, action_id, error_msg, "str")
        except Exception as e:
            print(f"执行动作 {action} 时出错: {e}")
            error_msg = {
                "success": False,
                "error": f"动作执行失败: {str(e)}",
                "action": action,
            }
            self.client.response_to_agent(agent_id, action_id, error_msg, "str")

    # === 动作处理方法 ===

    def handle_move(self, params: Dict) -> Dict[str, Any]:
        """处理移动动作"""
        return self.action_handler.execute_action("move", params)

    def handle_attack(self, params: Dict) -> Dict[str, Any]:
        """处理攻击动作"""
        return self.action_handler.execute_action("attack", params)

    def handle_defend(self, params: Dict) -> Dict[str, Any]:
        """处理防御动作"""
        return self.action_handler.execute_action("defend", params)

    def handle_scout(self, params: Dict) -> Dict[str, Any]:
        """处理侦察动作"""
        return self.action_handler.execute_action("scout", params)

    def handle_retreat(self, params: Dict) -> Dict[str, Any]:
        """处理撤退动作"""
        return self.action_handler.execute_action("retreat", params)

    def handle_fortify(self, params: Dict) -> Dict[str, Any]:
        """处理驻防动作"""
        return self.action_handler.execute_action("fortify", params)

    def handle_patrol(self, params: Dict) -> Dict[str, Any]:
        """处理巡逻动作"""
        return self.action_handler.execute_action("patrol", params)

    def handle_end_turn(self, params: Dict) -> Dict[str, Any]:
        """处理结束回合动作"""
        return self.action_handler.execute_action("end_turn", params)

    def handle_select_unit(self, params: Dict) -> Dict[str, Any]:
        """处理选择单位动作"""
        return self.action_handler.execute_action("select_unit", params)

    def handle_formation(self, params: Dict) -> Dict[str, Any]:
        """处理阵型动作"""
        return self.action_handler.execute_action("formation", params)

    # === 观测处理方法 ===

    def handle_observation(self, params: Dict) -> Dict[str, Any]:
        """处理通用观测请求"""
        observation_level = params.get("observation_level", ObservationLevel.FACTION)
        faction = params.get("faction")
        unit_id = params.get("unit_id")
        include_hidden = params.get("include_hidden", False)

        # 转换字符串到Faction枚举（如果需要）
        if faction and isinstance(faction, str):
            try:
                from ..prefabs.config import Faction

                faction = Faction(faction.upper())
            except ValueError:
                return {"error": f"Invalid faction: {faction}"}

        return self.observation_system.get_observation(
            observation_level, faction, unit_id, include_hidden
        )

    def handle_unit_observation(self, params: Dict) -> Dict[str, Any]:
        """处理单位观测请求"""
        unit_id = params.get("unit_id")
        if not unit_id:
            return {"error": "Missing unit_id parameter"}

        return self.observation_system.get_observation(
            ObservationLevel.UNIT, unit_id=unit_id
        )

    def handle_faction_observation(self, params: Dict) -> Dict[str, Any]:
        """处理阵营观测请求"""
        faction = params.get("faction")
        include_hidden = params.get("include_hidden", False)

        if not faction:
            return {"error": "Missing faction parameter"}

        # 转换字符串到Faction枚举
        if isinstance(faction, str):
            try:
                from ..prefabs.config import Faction

                faction = Faction(faction.upper())
            except ValueError:
                return {"error": f"Invalid faction: {faction}"}

        return self.observation_system.get_observation(
            ObservationLevel.FACTION, faction=faction, include_hidden=include_hidden
        )

    def handle_godview_observation(self, params: Dict) -> Dict[str, Any]:
        """处理上帝视角观测请求"""
        return self.observation_system.get_observation(ObservationLevel.GODVIEW)

    def handle_limited_observation(self, params: Dict) -> Dict[str, Any]:
        """处理受限观测请求"""
        faction = params.get("faction")

        if not faction:
            return {"success": False, "error": "Missing faction parameter"}

        # 转换字符串到Faction枚举
        if isinstance(faction, str):
            try:
                from ..prefabs.config import Faction

                faction = Faction(faction.upper())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        return self.observation_system.get_observation(
            ObservationLevel.LIMITED, faction=faction
        )

    def handle_tactical_observation(self, params: Dict) -> Dict[str, Any]:
        """处理战术观测请求"""
        return self.action_handler.execute_action("tactical_observation", params)

    # =============================================
    # 状态查询指令处理方法
    # =============================================

    def handle_get_unit_list(self, params: Dict) -> Dict[str, Any]:
        """获取单位列表"""
        return self.action_handler.execute_action("get_unit_list", params)

    def handle_get_unit_info(self, params: Dict) -> Dict[str, Any]:
        """获取指定单位的详细信息"""
        return self.action_handler.execute_action("get_unit_info", params)

    def handle_get_faction_units(self, params: Dict) -> Dict[str, Any]:
        """获取指定阵营的所有单位"""
        return self.action_handler.execute_action("get_faction_units", params)

    def handle_get_game_state(self, params: Dict) -> Dict[str, Any]:
        """获取游戏状态信息"""
        return self.action_handler.execute_action("get_game_state", params)

    def handle_get_map_info(self, params: Dict) -> Dict[str, Any]:
        """获取地图信息"""
        return self.action_handler.execute_action("get_map_info", params)

    def handle_get_battle_status(self, params: Dict) -> Dict[str, Any]:
        """获取战斗状态信息"""
        return self.action_handler.execute_action("get_battle_status", params)

    def handle_get_available_actions(self, params: Dict) -> Dict[str, Any]:
        """获取可用动作列表"""
        return self.action_handler.execute_action("get_available_actions", params)

    def handle_get_unit_capabilities(self, params: Dict) -> Dict[str, Any]:
        """获取单位能力信息"""
        return self.action_handler.execute_action("get_unit_capabilities", params)

    def handle_get_visibility_info(self, params: Dict) -> Dict[str, Any]:
        """获取视野信息"""
        return self.action_handler.execute_action("get_visibility_info", params)

    def handle_get_strategic_summary(self, params: Dict) -> Dict[str, Any]:
        """获取战略摘要"""
        return self.action_handler.execute_action("get_strategic_summary", params)

    def cleanup(self):
        """清理资源"""
        try:
            self.disconnect()
        except Exception as e:
            print(f"断开连接时出错: {e}")
