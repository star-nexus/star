"""
LLM系统 - 游戏全局控制接口
提供完整的游戏操作能力：系统控制 + 委托单位动作 + 委托观测查询
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple

from rich import print_json
from framework import System, World
from ..prefabs.config import Faction, PlayerType, GameMode, UnitState
from rotk_env.components import (
    GameState,
    HexPosition,
    Unit,
    MovementPoints,
    Combat,
    Renderable,
    Player,
    TurnManager,
    FogOfWar,
    MapData,
    Camera,
    UIState,
    GameModeComponent,
    GameStats,
)
from rotk_env.prefabs.config import Faction, UnitType, GameMode
from rotk_env.systems.llm_observation_system import ObservationLevel

from protocol.star_client_v2 import (
    SyncWebSocketClient,
    ClientInfo,
    ClientType,
    MessageType,
)

# from .llm_action_handler_v2 import LLMActionHandlerV2 as LLMActionHandler
from .llm_action_handler_v3 import LLMActionHandlerV3 as LLMActionHandler
from .llm_observation_system import LLMObservationSystem, ObservationLevel


class SyncEnvClient(SyncWebSocketClient):
    """同步环境客户端"""

    def __init__(self, server_url: str, env_id: str):
        client_info = ClientInfo(type=ClientType.ENVIRONMENT, id=env_id)
        super().__init__(server_url, client_info)
        self.connected_agents = {}

    def url(self) -> str:
        """构建环境连接 URL"""
        return f"{self.server_url}/env/{self.client_info.id}"

    def response_to_agent(
        self, agent_id: str, action_id: int, outcome: str, outcome_type: str = "str"
    ):
        """向Agent发送响应 - 同步接口"""
        return self.send_message(
            MessageType.MESSAGE.value,
            {
                "type": "outcome",
                "id": action_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
            target={
                "type": "agent",
                "id": agent_id,
            },
        )


class LLMSystem(System):
    """LLM系统 - 游戏全局控制接口"""

    def __init__(self):
        super().__init__()
        self.name = "LLMSystem"

        # 系统级错误代码
        self.system_error_codes = {
            2001: "游戏未初始化",
            2002: "游戏已结束",
            2003: "操作不被当前游戏模式支持",
            2004: "系统资源不足",
            2005: "权限不足",
            2006: "操作超时",
            2007: "参数验证失败",
            2008: "系统状态异常",
            2009: "网络连接错误",
            2010: "内部服务错误",
        }

    def initialize(self, world):
        self.world = world

        # 初始化委托对象
        self.action_handler = LLMActionHandler(world)
        self.observation_system = LLMObservationSystem(world)

        # 使用同步客户端
        self.client = SyncEnvClient(
            server_url="ws://localhost:8000/ws/metaverse",
            env_id="env_1",
        )
        self.add_listener()

        # 初始化系统级动作映射
        self.system_actions = self._init_system_actions()

        self.connect()
        return

    def _init_system_actions(self) -> Dict[str, callable]:
        """初始化系统级动作映射"""
        return {}

    def add_listener(self):
        # 添加事件监听器
        self.client.add_hub_listener("message", self.on_message)
        self.client.add_hub_listener("connect", self.on_connect)
        self.client.add_hub_listener("disconnect", self.on_disconnect)
        self.client.add_hub_listener("error", self.on_error)

    # === WebSocket 事件处理方法 ===

    def on_message(self, envelope):
        """处理接收到的消息"""
        print(f"LLMSystem received message")
        try:
            # 解析新的Envelope结构
            sender = envelope.get("sender", {})
            recipient = envelope.get("recipient", {})
            payload = envelope.get("payload", {})
            message_type = envelope.get("type", "")

            if payload.get("type") == "action":
                # 处理动作消息

                print(f"处理动作消息: {payload}")

                # 提取 agent 信息
                agent_id = sender.get("id") if sender.get("type") == "agent" else None
                if agent_id:
                    self.client.connected_agents[agent_id] = sender
                self.exec_action(envelope)
                return
            else:
                # 处理其他消息类型
                print(f"处理其他消息类型: {payload}")

        except Exception as e:
            print(f"消息处理错误: {e}")
            if "sender" in locals():
                self.send_error_response(sender, f"Message processing error: {e}")

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

    def send_message(self, message, instruction=None, target=None):
        """发送消息 - 同步方法"""
        return self.client.send_message(
            instruction or MessageType.MESSAGE.value, message, target
        )

    def response_to_agent(
        self, agent_id: str, action_id: int, outcome: str, outcome_type: str = "str"
    ):
        """执行动作 - 同步接口"""
        return self.client.response_to_agent(agent_id, action_id, outcome, outcome_type)

    def _record_interaction(self, agent_id: str | None, params: Dict[str, Any] | None) -> None:
        """记录一次 ENV -> Agent 响应交互。

        - 按 agent 维度累计
        - 通过 agent -> faction 映射进行阵营累计；若本次参数提供了 faction 则建立映射
        """
        try:
            stats = self.world.get_singleton_component(GameStats)
            if stats is None:
                stats = GameStats()
                self.world.add_singleton_component(stats)

            # 按 agent 统计
            if agent_id:
                stats.response_times_by_agent[agent_id] = (
                    stats.response_times_by_agent.get(agent_id, 0) + 1
                )

            # 阵营聚合：优先使用既有映射；否则尝试从本次参数中解析 faction 并建立映射
            from ..prefabs.config import Faction as _Faction
            mapped_faction = None

            if agent_id and agent_id in stats.agent_id_to_faction:
                mapped_faction = stats.agent_id_to_faction.get(agent_id)
            else:
                faction_key = None
                if isinstance(params, dict):
                    faction_key = params.get("faction")
                if faction_key:
                    try:
                        mapped_faction = _Faction(faction_key)
                        if agent_id:
                            stats.agent_id_to_faction[agent_id] = mapped_faction
                    except Exception:
                        mapped_faction = None

            if mapped_faction:
                stats.response_times_by_faction[mapped_faction] = (
                    stats.response_times_by_faction.get(mapped_faction, 0) + 1
                )
        except Exception as _e:
            # 统计失败不影响主流程
            print(f"[LLMSystem] 记录交互次数时发生非致命错误: {_e}")

    def send_error_response(self, sender: Dict[str, Any], error_message: str):
        """发送错误响应"""
        agent_id = sender.get("id") if sender.get("type") == "agent" else None
        if agent_id:
            error_response = {
                "success": False,
                "error": error_message,
                "timestamp": time.time(),
            }
            self.send_message(error_response, target={"type": "agent", "id": agent_id})
            # 统一位置计数：显式错误响应也计数
            self._record_interaction(agent_id, None)

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
        """智能委托执行动作 - 统一动作入口"""
        sender = message.get("sender", {})
        payload = message.get("payload", {})

        agent_id = sender.get("id") if sender.get("type") == "agent" else None
        action_id = payload.get("id")
        action = payload.get("action")
        params = payload.get("parameters", {})
        if isinstance(params, dict):
            params = params
        elif isinstance(params, str):
            if params == "":
                params = {}
            else:
                params = json.loads(params)

        start_time = time.time()

        try:
            # 1. 检查是否为系统级动作
            if action in self.system_actions:
                result = self.system_actions[action](params)

            # 2. 检查是否为单位动作 (委托给ActionHandler)
            elif action in self.action_handler.action_handlers:
                result = self.action_handler.execute_action(action, params)

            # 3. 检查是否为观测动作 (委托给ObservationSystem)
            elif self._is_observation_action(action):
                result = self._handle_observation_action(action, params)

            # 4. 未知动作
            else:
                result = self._create_system_error_response(
                    action, f"Unknown action: {action}", 2010
                )

            # 标准化响应格式
            execution_time = time.time() - start_time
            # standardized_result = self._standardize_response(
            #     result, action, params, execution_time
            # )
            standardized_result = result

            print(f"{action} response: {standardized_result}")
            self.client.response_to_agent(
                agent_id, action_id, standardized_result, "str"
            )
            # 统一位置计数：正常响应
            self._record_interaction(agent_id, params)

        except Exception as e:
            print(f"执行动作 {action} 时出错: {e}")
            error_result = self._create_system_error_response(action, str(e), 2010)
            self.client.response_to_agent(agent_id, action_id, error_result, "str")
            # 统一位置计数：异常时的错误响应也计数
            self._record_interaction(agent_id, params)

    def _is_observation_action(self, action: str) -> bool:
        """判断是否为观测动作"""
        observation_actions = [
            "observation",
            "unit_observation",
            "faction_observation",
            "godview_observation",
            "limited_observation",
            "tactical_observation",
            "get_unit_list",
            "get_unit_info",
            "get_faction_units",
            "get_game_state",
            "get_map_info",
            "get_battle_status",
            "get_unit_capabilities",
            "get_visibility_info",
            "get_strategic_summary",
        ]
        return (
            action in observation_actions
            or action.startswith("get_")
            or action.endswith("_observation")
        )

    def _handle_observation_action(self, action: str, params: Dict) -> Dict:
        """处理观测动作的路由"""
        # 对于已知的观测动作，路由到对应的处理方法
        if action == "observation":
            return self.handle_observation(params)
        elif action == "unit_observation":
            return self.handle_unit_observation(params)
        elif action == "faction_observation":
            return self.handle_faction_observation(params)
        elif action == "godview_observation":
            return self.handle_godview_observation(params)
        elif action == "limited_observation":
            return self.handle_limited_observation(params)
        elif action == "tactical_observation":
            return self.handle_tactical_observation(params)
        else:
            # 通用观测动作，直接委托给observation_system
            return self.observation_system.get_observation_by_action(action, params)

    def _standardize_response(
        self, result: Dict, action: str, params: Dict, execution_time: float
    ) -> Dict:
        """标准化响应格式"""
        base_response = {
            "success": result.get("success", True),
            "api_version": "v1.0",
            "metadata": {
                "action": action,
                "timestamp": time.time(),
                "execution_time": execution_time,
            },
        }

        if result.get("success", True):
            # 成功响应，合并数据
            base_response.update({k: v for k, v in result.items() if k != "success"})
        else:
            # 错误响应
            base_response.update(
                {
                    "error": result.get("error", "Unknown error"),
                    "error_code": result.get("error_code", "UNKNOWN_ERROR"),
                    "message": result.get("message", ""),
                }
            )

        return base_response

    def _create_system_error_response(
        self, action: str, error_message: str, error_code: int = 2010
    ) -> Dict:
        """创建系统级错误响应"""
        return {
            "success": False,
            "error": self.system_error_codes.get(error_code, "Unknown system error"),
            "error_code": error_code,
            "message": f"Action {action} failed: {error_message}",
            "api_version": "v1.0",
            "metadata": {"action": action, "timestamp": time.time()},
        }

    # ==================== 系统级控制方法 ====================

    # === 游戏生命周期控制 ===
    def handle_start_game(self, params: Dict) -> Dict:
        """启动游戏"""
        game_state = self.world.get_singleton_component(GameState)
        if game_state and not game_state.game_over:
            return {
                "success": False,
                "error_code": 2001,
                "message": "Game already running",
            }

        try:
            # 重置游戏状态
            if game_state:
                game_state.game_over = False
                game_state.paused = False
                game_state.turn_number = 1
                game_state.winner = None

            return {"success": True, "message": "Game started successfully"}
        except Exception as e:
            return {
                "success": False,
                "error_code": 2010,
                "message": f"Failed to start game: {str(e)}",
            }

    def handle_pause_game(self, params: Dict) -> Dict:
        """暂停游戏"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return {
                "success": False,
                "error_code": 2001,
                "message": "Game not initialized",
            }

        if game_state.game_over:
            return {
                "success": False,
                "error_code": 2002,
                "message": "Game already ended",
            }

        game_state.paused = True
        return {"success": True, "message": "Game paused", "paused": True}

    def handle_resume_game(self, params: Dict) -> Dict:
        """恢复游戏"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return {
                "success": False,
                "error_code": 2001,
                "message": "Game not initialized",
            }

        if game_state.game_over:
            return {
                "success": False,
                "error_code": 2002,
                "message": "Game already ended",
            }

        game_state.paused = False
        return {"success": True, "message": "Game resumed", "paused": False}

    def handle_reset_game(self, params: Dict) -> Dict:
        """重置游戏"""
        try:
            # 重置游戏状态
            game_state = self.world.get_singleton_component(GameState)
            if game_state:
                game_state.game_over = False
                game_state.paused = False
                game_state.turn_number = 1
                game_state.winner = None
                game_state.current_player = Faction.WEI  # 默认从魏国开始

            return {"success": True, "message": "Game reset successfully"}
        except Exception as e:
            return {
                "success": False,
                "error_code": 2010,
                "message": f"Failed to reset game: {str(e)}",
            }

    def handle_save_game(self, params: Dict) -> Dict:
        """保存游戏"""
        # TODO: 实现游戏保存逻辑
        return {
            "success": False,
            "error_code": 2004,
            "message": "Save game not implemented yet",
        }

    def handle_load_game(self, params: Dict) -> Dict:
        """加载游戏"""
        # TODO: 实现游戏加载逻辑
        return {
            "success": False,
            "error_code": 2004,
            "message": "Load game not implemented yet",
        }

    # === 回合和时间管理 ===
    def handle_end_turn(self, params: Dict) -> Dict:
        """结束回合"""
        turn_system = self._get_turn_system()
        if turn_system:
            try:
                turn_system.end_turn()
                game_state = self.world.get_singleton_component(GameState)
                return {
                    "success": True,
                    "message": "Turn ended successfully",
                    "current_turn": game_state.turn_number if game_state else 0,
                    "current_player": (
                        game_state.current_player.value if game_state else "unknown"
                    ),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error_code": 2010,
                    "message": f"Failed to end turn: {str(e)}",
                }
        return {
            "success": False,
            "error_code": 2008,
            "message": "Turn system not available",
        }

    def handle_skip_turn(self, params: Dict) -> Dict:
        """跳过回合"""
        faction_str = params.get("faction")
        if not faction_str:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing faction parameter",
            }

        try:
            faction = Faction(faction_str)
            # TODO: 实现跳过指定阵营回合的逻辑
            return {
                "success": True,
                "message": f"Skipped turn for faction {faction.value}",
            }
        except ValueError:
            return {
                "success": False,
                "error_code": 2007,
                "message": f"Invalid faction: {faction_str}",
            }

    def handle_force_next_turn(self, params: Dict) -> Dict:
        """强制推进到下一回合"""
        target_faction = params.get("target_faction")
        turn_system = self._get_turn_system()

        if turn_system:
            try:
                # 如果指定了目标阵营，持续推进直到到达该阵营
                if target_faction:
                    target = Faction(target_faction)
                    game_state = self.world.get_singleton_component(GameState)
                    while game_state and game_state.current_player != target:
                        turn_system.end_turn()
                else:
                    # 否则只推进一个回合
                    turn_system.end_turn()

                game_state = self.world.get_singleton_component(GameState)
                return {
                    "success": True,
                    "message": "Forced to next turn",
                    "current_player": (
                        game_state.current_player.value if game_state else "unknown"
                    ),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error_code": 2010,
                    "message": f"Failed to force next turn: {str(e)}",
                }

        return {
            "success": False,
            "error_code": 2008,
            "message": "Turn system not available",
        }

    def handle_advance_time(self, params: Dict) -> Dict:
        """推进游戏时间"""
        seconds = params.get("seconds", 1.0)
        game_time_system = self._get_game_time_system()

        if game_time_system:
            try:
                game_time_system.advance_turn()  # 简化实现
                return {
                    "success": True,
                    "message": f"Advanced time by {seconds} seconds",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error_code": 2010,
                    "message": f"Failed to advance time: {str(e)}",
                }

        return {
            "success": False,
            "error_code": 2008,
            "message": "Game time system not available",
        }

    def handle_set_turn_timer(self, params: Dict) -> Dict:
        """设置回合计时器"""
        duration = params.get("duration", 30.0)
        # TODO: 实现回合计时器设置
        return {"success": True, "message": f"Turn timer set to {duration} seconds"}

    # === 游戏模式控制 ===
    def handle_set_game_mode(self, params: Dict) -> Dict:
        """设置游戏模式"""
        mode_str = params.get("mode")
        if not mode_str:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing mode parameter",
            }

        try:
            mode = GameMode(mode_str)
            game_mode_component = self.world.get_singleton_component(GameModeComponent)
            if game_mode_component:
                game_mode_component.mode = mode
                return {"success": True, "message": f"Game mode set to {mode.value}"}
            else:
                # 创建游戏模式组件
                game_mode_component = GameModeComponent(mode=mode)
                self.world.add_singleton_component(game_mode_component)
                return {"success": True, "message": f"Game mode set to {mode.value}"}
        except ValueError:
            return {
                "success": False,
                "error_code": 2007,
                "message": f"Invalid game mode: {mode_str}",
            }

    def handle_set_time_scale(self, params: Dict) -> Dict:
        """设置时间缩放"""
        scale = params.get("scale", 1.0)
        game_time_system = self._get_game_time_system()

        if game_time_system:
            try:
                game_time_system.set_time_scale(scale)
                return {"success": True, "message": f"Time scale set to {scale}"}
            except Exception as e:
                return {
                    "success": False,
                    "error_code": 2010,
                    "message": f"Failed to set time scale: {str(e)}",
                }

        return {
            "success": False,
            "error_code": 2008,
            "message": "Game time system not available",
        }

    def handle_set_max_turns(self, params: Dict) -> Dict:
        """设置最大回合数"""
        max_turns = params.get("max_turns", 50)
        game_state = self.world.get_singleton_component(GameState)

        if game_state:
            game_state.max_turns = max_turns
            return {"success": True, "message": f"Max turns set to {max_turns}"}

        return {
            "success": False,
            "error_code": 2001,
            "message": "Game state not available",
        }

    # === 视角和UI控制 ===
    def handle_set_view_faction(self, params: Dict) -> Dict:
        """设置观察视角"""
        faction_str = params.get("faction")
        try:
            faction = Faction(faction_str) if faction_str else None
            ui_state = self.world.get_singleton_component(UIState)
            if ui_state:
                ui_state.view_faction = faction
                return {
                    "success": True,
                    "message": f"View faction set to {faction_str}",
                    "view_faction": faction_str,
                }
            else:
                # 创建UI状态组件
                ui_state = UIState(view_faction=faction)
                self.world.add_singleton_component(ui_state)
                return {
                    "success": True,
                    "message": f"View faction set to {faction_str}",
                    "view_faction": faction_str,
                }
        except ValueError:
            return {
                "success": False,
                "error_code": 2007,
                "message": f"Invalid faction: {faction_str}",
            }

    def handle_set_camera_position(self, params: Dict) -> Dict:
        """设置摄像机位置"""
        x = params.get("x", 0.0)
        y = params.get("y", 0.0)
        camera = self.world.get_singleton_component(Camera)

        if camera:
            camera.set_offset(x, y)
            return {
                "success": True,
                "message": f"Camera position set to ({x}, {y})",
                "position": {"x": x, "y": y},
            }

        return {
            "success": False,
            "error_code": 2008,
            "message": "Camera component not available",
        }

    def handle_toggle_god_mode(self, params: Dict) -> Dict:
        """切换上帝模式"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.god_mode = not ui_state.god_mode
            return {
                "success": True,
                "message": f"God mode {'enabled' if ui_state.god_mode else 'disabled'}",
                "god_mode": ui_state.god_mode,
            }

        return {
            "success": False,
            "error_code": 2008,
            "message": "UI state not available",
        }

    def handle_toggle_fog_of_war(self, params: Dict) -> Dict:
        """切换战争迷雾"""
        enabled = params.get("enabled")
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if fog_of_war:
            if enabled is not None:
                # 如果指定了启用状态，直接设置
                fog_enabled = bool(enabled)
            else:
                # 否则切换当前状态
                fog_enabled = not getattr(fog_of_war, "enabled", True)

            # TODO: 实现战争迷雾启用/禁用逻辑
            return {
                "success": True,
                "message": f"Fog of war {'enabled' if fog_enabled else 'disabled'}",
                "fog_enabled": fog_enabled,
            }

        return {
            "success": False,
            "error_code": 2008,
            "message": "Fog of war component not available",
        }

    def handle_show_ui_panel(self, params: Dict) -> Dict:
        """显示UI面板"""
        panel_name = params.get("panel")
        if not panel_name:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing panel parameter",
            }

        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            # 根据面板名称设置显示状态
            if panel_name == "help":
                ui_state.show_help = True
            elif panel_name == "stats":
                ui_state.show_stats = True
            elif panel_name == "grid":
                ui_state.show_grid = True
            else:
                return {
                    "success": False,
                    "error_code": 2007,
                    "message": f"Unknown panel: {panel_name}",
                }

            return {"success": True, "message": f"Panel {panel_name} shown"}

        return {
            "success": False,
            "error_code": 2008,
            "message": "UI state not available",
        }

    def handle_hide_ui_panel(self, params: Dict) -> Dict:
        """隐藏UI面板"""
        panel_name = params.get("panel")
        if not panel_name:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing panel parameter",
            }

        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            # 根据面板名称设置隐藏状态
            if panel_name == "help":
                ui_state.show_help = False
            elif panel_name == "stats":
                ui_state.show_stats = False
            elif panel_name == "grid":
                ui_state.show_grid = False
            else:
                return {
                    "success": False,
                    "error_code": 2007,
                    "message": f"Unknown panel: {panel_name}",
                }

            return {"success": True, "message": f"Panel {panel_name} hidden"}

        return {
            "success": False,
            "error_code": 2008,
            "message": "UI state not available",
        }

    def handle_toggle_grid_display(self, params: Dict) -> Dict:
        """切换网格显示"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.show_grid = not ui_state.show_grid
            return {
                "success": True,
                "message": f"Grid display {'enabled' if ui_state.show_grid else 'disabled'}",
                "show_grid": ui_state.show_grid,
            }

        return {
            "success": False,
            "error_code": 2008,
            "message": "UI state not available",
        }

    # === 选择和分组控制 ===
    def handle_select_unit(self, params: Dict) -> Dict:
        """选择单位"""
        unit_id = params.get("unit_id")
        if not unit_id:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_id parameter",
            }

        # 委托给ActionHandler处理具体的选择逻辑
        return self.action_handler.execute_action("select_unit", params)

    def handle_select_multiple_units(self, params: Dict) -> Dict:
        """选择多个单位"""
        unit_ids = params.get("unit_ids", [])
        if not unit_ids:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_ids parameter",
            }

        # TODO: 实现多选逻辑
        return {
            "success": True,
            "message": f"Selected {len(unit_ids)} units",
            "selected_units": unit_ids,
        }

    def handle_deselect_units(self, params: Dict) -> Dict:
        """取消选择单位"""
        # TODO: 实现取消选择逻辑
        return {"success": True, "message": "Units deselected"}

    def handle_group_units(self, params: Dict) -> Dict:
        """组编单位"""
        unit_ids = params.get("unit_ids", [])
        group_id = params.get("group_id", 1)

        if not unit_ids:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_ids parameter",
            }

        # TODO: 实现单位分组逻辑
        return {
            "success": True,
            "message": f"Grouped {len(unit_ids)} units into group {group_id}",
        }

    # === 系统信息和诊断 ===
    def handle_get_system_status(self, params: Dict) -> Dict:
        """获取系统状态"""
        return {
            "success": True,
            "message": "System status retrieved",
            "data": {
                "system_name": self.name,
                "initialized": hasattr(self, "world"),
                "action_handler_ready": hasattr(self, "action_handler"),
                "observation_system_ready": hasattr(self, "observation_system"),
                "game_status": self._get_game_status(),
                "supported_actions": len(self.system_actions),
                "timestamp": time.time(),
            },
        }

    def handle_get_api_info(self, params: Dict) -> Dict:
        """获取API信息"""
        return {
            "success": True,
            "message": "API information retrieved",
            "data": {
                "version": "2.0",
                "system_actions": list(self.system_actions.keys()),
                "unit_actions": (
                    list(self.action_handler.action_handlers.keys())
                    if hasattr(self, "action_handler")
                    else []
                ),
                "observation_actions": ["observation", "get_observation_by_action"],
                "total_endpoints": len(self.system_actions)
                + (
                    len(self.action_handler.action_handlers)
                    if hasattr(self, "action_handler")
                    else 0
                )
                + 2,
            },
        }

    def handle_get_system_capabilities(self, params: Dict) -> Dict:
        """获取系统能力"""
        capabilities = {
            "game_control": True,
            "unit_control": True,
            "observation": True,
            "real_time": False,  # 目前只支持回合制
            "multiplayer": True,
            "save_load": False,  # 尚未实现
            "ai_integration": True,
            "error_recovery": True,
        }

        return {
            "success": True,
            "message": "System capabilities retrieved",
            "data": capabilities,
        }

    def handle_get_performance_info(self, params: Dict) -> Dict:
        """获取性能信息"""
        # TODO: 实现性能监控
        return {
            "success": True,
            "message": "Performance information retrieved",
            "data": {
                "memory_usage": "N/A",
                "cpu_usage": "N/A",
                "action_execution_time": "N/A",
                "error_rate": "N/A",
            },
        }

    def handle_validate_game_state(self, params: Dict) -> Dict:
        """验证游戏状态"""
        try:
            game_state = self.world.get_singleton_component(GameState)
            if not game_state:
                return {
                    "success": False,
                    "error_code": 2001,
                    "message": "Game state not found",
                }

            # 基本验证
            validation_results = {
                "game_state_exists": bool(game_state),
                "current_player_valid": hasattr(game_state, "current_player"),
                "turn_number_valid": hasattr(game_state, "turn_number")
                and game_state.turn_number > 0,
                "game_over_flag": game_state.game_over,
                "paused_flag": game_state.paused,
            }

            all_valid = all(validation_results.values())

            return {
                "success": True,
                "message": f"Game state validation {'passed' if all_valid else 'failed'}",
                "data": {"valid": all_valid, "details": validation_results},
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": 2010,
                "message": f"Validation error: {str(e)}",
            }

    def handle_get_game_statistics(self, params: Dict) -> Dict:
        """获取游戏统计"""
        # TODO: 实现游戏统计收集
        return {
            "success": True,
            "message": "Game statistics retrieved",
            "data": {
                "total_turns": 0,
                "total_actions": 0,
                "battles_fought": 0,
                "units_created": 0,
                "territories_captured": 0,
            },
        }

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

    def handle_action_list(self, params: Dict) -> Dict[str, Any]:
        """获取动作列表"""
        return self.action_handler.execute_action("action_list", params)

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

    # ==================== 系统辅助方法 ====================

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.get_systems():
            if hasattr(system, "end_turn"):
                return system
        return None

    def _get_game_time_system(self):
        """获取游戏时间系统"""
        for system in self.world.get_systems():
            if (
                hasattr(system, "advance_turn")
                or "time" in system.__class__.__name__.lower()
            ):
                return system
        return None

    def _get_rendering_system(self):
        """获取渲染系统"""
        for system in self.world.get_systems():
            if "render" in system.__class__.__name__.lower():
                return system
        return None

    def _get_camera_system(self):
        """获取摄像机系统"""
        for system in self.world.get_systems():
            if "camera" in system.__class__.__name__.lower():
                return system
        return None

    def _get_ui_system(self):
        """获取UI系统"""
        for system in self.world.get_systems():
            if "ui" in system.__class__.__name__.lower():
                return system
        return None

    def _get_available_factions(self) -> List[str]:
        """获取所有可用阵营"""
        return [faction.value for faction in Faction]

    def _get_available_unit_types(self) -> List[str]:
        """获取所有可用单位类型"""
        return [unit_type.value for unit_type in UnitType]

    def _validate_faction(self, faction_str: str) -> bool:
        """验证阵营有效性"""
        try:
            Faction(faction_str)
            return True
        except ValueError:
            return False

    def _validate_position(self, position: Dict) -> bool:
        """验证位置坐标有效性"""
        if not isinstance(position, dict):
            return False
        required_keys = ["q", "r"]
        return all(
            key in position and isinstance(position[key], int) for key in required_keys
        )

    def _normalize_position(self, position: Dict) -> Dict:
        """标准化位置坐标（确保包含s坐标）"""
        q, r = position["q"], position["r"]
        return {"q": q, "r": r, "s": -q - r}

    def _validate_unit_id(self, unit_id: Any) -> bool:
        """验证单位ID有效性"""
        return isinstance(unit_id, int) and unit_id > 0

    def _get_game_status(self) -> Dict:
        """获取当前游戏状态摘要"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return {"initialized": False}

        return {
            "initialized": True,
            "running": not game_state.game_over,
            "paused": game_state.paused,
            "turn": game_state.turn_number,
            "current_player": game_state.current_player.value,
            "winner": game_state.winner.value if game_state.winner else None,
            "max_turns": getattr(game_state, "max_turns", None),
        }

    # === 统计和分析 ===
    def handle_get_battle_history(self, params: Dict) -> Dict:
        """获取战斗历史"""
        # TODO: 实现战斗历史收集
        return {
            "success": True,
            "message": "Battle history retrieved",
            "data": {"battles": [], "total_battles": 0, "recent_battles": []},
        }

    def handle_export_game_data(self, params: Dict) -> Dict:
        """导出游戏数据"""
        # TODO: 实现游戏数据导出
        return {
            "success": False,
            "error_code": 2004,
            "message": "Game data export not implemented yet",
        }

    # === 调试功能 ===
    def handle_execute_debug_command(self, params: Dict) -> Dict:
        """执行调试命令"""
        command = params.get("command")
        if not command:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing command parameter",
            }

        # TODO: 实现调试命令执行
        return {
            "success": True,
            "message": f"Debug command '{command}' executed",
            "result": "Debug functionality not fully implemented",
        }

    def handle_toggle_debug_mode(self, params: Dict) -> Dict:
        """切换调试模式"""
        # TODO: 实现调试模式切换
        return {"success": True, "message": "Debug mode toggled", "debug_mode": True}

    def handle_get_component_info(self, params: Dict) -> Dict:
        """获取组件信息"""
        entity_id = params.get("entity_id")
        if entity_id:
            # TODO: 获取指定实体的组件信息
            return {
                "success": True,
                "message": f"Component info for entity {entity_id}",
                "data": {"components": []},
            }
        else:
            # 获取所有组件类型信息
            return {
                "success": True,
                "message": "All component types retrieved",
                "data": {
                    "singleton_components": [
                        "GameState",
                        "MapData",
                        "FogOfWar",
                        "Camera",
                        "UIState",
                    ],
                    "entity_components": [
                        "Unit",
                        "HexPosition",
                        "Movement",
                        "Combat",
                        "Renderable",
                    ],
                },
            }
