# """
# LLM系统 - 重新实现版本
# 在同步游戏循环中正确支持异步WebSocket连接
# 直接控制游戏单位并做出决策
# """

# import asyncio
# import time
# import threading
# from typing import Dict, List, Any, Optional, Tuple

# from rich import print_json
# from framework_v2 import System, World
# from ..components import (
#     Unit,
#     MapData,
#     Health,
#     HexPosition,
#     Movement,
#     Combat,
#     Vision,
#     GameState,
#     FogOfWar,
#     Player,
#     AIControlled,
#     GameStats,
#     BattleLog,
#     UnitObservation,
# )
# from ..prefabs.config import Faction, PlayerType, GameMode

# # 导入 Star Client 相关组件
# from llm.star_client import EnvironmentClient
# from llm.star_client.types import ClientInfo, MessageInstruction


# class LLMEnvironmentClient:
#     """
#     游戏环境的 LLM 客户端 - 包装 Star Client EnvironmentClient
#     """

#     def __init__(self, server_url: str, env_id: int, llm_system):
#         # 创建底层客户端
#         self.client = EnvironmentClient(server_url, env_id)
#         self.llm_system = llm_system
#         self.connected_agents = {}

#         # 添加事件监听器
#         self.client.add_event_listener("message", self.on_message)
#         self.client.add_event_listener("connect", self.on_connect)
#         self.client.add_event_listener("disconnect", self.on_disconnect)
#         self.client.add_event_listener("error", self.on_error)

#     async def connect(self):
#         """连接到服务器"""
#         return await self.client.connect()

#     async def disconnect(self):
#         """断开连接"""
#         return await self.client.disconnect()

#     async def send_message(self, message, instruction=None, target_id=None):
#         """发送消息"""
#         return await self.client.send_message(message, instruction, target_id)

#     @property
#     def connected(self):
#         """获取连接状态"""
#         return getattr(self.client, "connected", False)

#     @property
#     def client_info(self):
#         """获取客户端信息"""
#         return getattr(self.client, "client_info", None)

#     async def on_connect(self, data):
#         """连接成功事件"""
#         print(f"✅ LLM Environment Client connected")
#         print_json(data=data)

#         # # 发送环境就绪消息
#         # ready_message = {
#         #     "type": "environment_ready",
#         #     "env_id": (
#         #         self.client_info.env_id if self.client_info else self.client.env_id
#         #     ),
#         #     "game_mode": "turn_based",
#         #     "supported_actions": [
#         #         "move_unit",
#         #         "attack_unit",
#         #         "end_turn",
#         #         "set_strategy",
#         #     ],
#         #     "timestamp": time.time(),
#         # }

#         # try:
#         #     await self.send_message(ready_message)
#         # except Exception as e:
#         #     print(f"❌ 发送就绪消息失败: {e}")

#     async def on_disconnect(self, data):
#         """断开连接事件"""
#         print(f"🔌 LLM Environment Client disconnected: {data}")

#         # 清理连接的agent记录
#         disconnected_agents = list(self.connected_agents.keys())
#         for agent_id in disconnected_agents:
#             del self.connected_agents[agent_id]

#         print(f"🧹 清理了 {len(disconnected_agents)} 个agent会话")

#     async def on_error(self, data):
#         """错误事件"""
#         print(f"❌ LLM Environment Client error:")
#         print_json(data=data)

#     async def on_message(self, envelope):
#         """处理接收到的消息"""
#         try:
#             msg_from = envelope.get("msg_from", {})
#             msg_data = envelope.get("data", {})
#             msg_type = msg_data.get("type")

#             print(f"📨 收到消息类型: {msg_type}")

#             if msg_type == "action":
#                 data_action = msg_data.get("action")
#                 data_parameters = msg_data.get("parameters", {})
#                 print(f"data_action: {data_action}, data_parameters: {data_parameters}")
#                 if data_action == "add":

#                     def add(x: int, y: int) -> int:
#                         return int(x) + int(y)

#                     result = add(*data_parameters)
#                     print(f"📦 发送消息: {result}")
#                     await self.client.send_message(
#                         data={
#                             "type": "outcome",
#                             "outcome": result,
#                             "timestamp": time.time(),
#                         },
#                         instruction=MessageInstruction.MESSAGE.value,
#                         target=msg_from,
#                     )
#                 if data_action == "observe":

#                     def observe() -> str:
#                         return f"观察到位置 ({2}, {2})"

#                     result = observe()
#                     print(f"obs result: ", result)
#                     await self.client.send_message(
#                         data={
#                             "type": "outcome",
#                             "outcome": result,
#                             "timestamp": time.time(),
#                         },
#                         instruction=MessageInstruction.MESSAGE.value,
#                         target=msg_from,
#                     )
#                 if data_action == "move":
#                     movement_system = self.llm_system._get_movement_system()
#                     entity = int(data_parameters[0])
#                     pos = data_parameters[1][1:-1].split(",")
#                     pos = (int(pos[0]), int(pos[1]))
#                     if movement_system:
#                         movement_system.move_unit(entity, pos)

#                     await self.client.send_message(
#                         data={
#                             "type": "outcome",
#                             "outcome": "正在移动",
#                             "timestamp": time.time(),
#                         },
#                         instruction=MessageInstruction.MESSAGE.value,
#                         target=msg_from,
#                     )
#             elif msg_type == "outcome":
#                 data_outcome = msg_data.get("outcome")
#                 print(f"data_outcome: {data_outcome}")
#             else:
#                 raise ValueError(f"未知消息类型: {msg_type}")

#             # # 根据消息类型分发处理
#             # if msg_type == "session_init":
#             #     await self.handle_session_init(msg_from, msg_data)
#             # elif msg_type == "observation_request":
#             #     await self.handle_observation_request(msg_from, msg_data)
#             # elif msg_type == "action_command":
#             #     await self.handle_action_command(msg_from, msg_data)
#             # elif msg_type == "strategy_query":
#             #     await self.handle_strategy_query(msg_from, msg_data)
#             # else:
#             #     await self.send_error_response(msg_from, f"未知消息类型: {msg_type}")

#         except Exception as e:
#             print(f"❌ 处理消息时出错: {e}")
#             await self.send_error_response(envelope.get("from", {}), str(e))

#     async def handle_session_init(self, msg_from: Dict, msg_data: Dict):
#         """处理会话初始化"""
#         result = await self.llm_system.handle_session_init_async(msg_from, msg_data)
#         response = {"type": "session_response", **result}
#         await self.send_to_agent(msg_from.get("agent_id"), response)

#     async def handle_observation_request(self, msg_from: Dict, msg_data: Dict):
#         """处理观测请求"""
#         observation_data = await self.llm_system.handle_observation_request_async(
#             msg_from, msg_data
#         )
#         response = {"type": "observation_response", **observation_data}
#         await self.send_to_agent(msg_from.get("agent_id"), response)

#     async def handle_action_command(self, msg_from: Dict, msg_data: Dict):
#         """处理动作指令"""
#         action_result = await self.llm_system.handle_action_command_async(
#             msg_from, msg_data
#         )
#         response = {
#             "type": "action_result",
#             "action_type": msg_data.get("action_type"),
#             "result": action_result,
#         }
#         await self.send_to_agent(msg_from.get("agent_id"), response)

#     async def handle_strategy_query(self, msg_from: Dict, msg_data: Dict):
#         """处理策略查询"""
#         strategy_data = await self.llm_system.handle_strategy_query_async(
#             msg_from, msg_data
#         )
#         response = {"type": "strategy_response", **strategy_data}
#         await self.send_to_agent(msg_from.get("agent_id"), response)

#     async def send_error_response(self, msg_from: Dict, error_message: str):
#         """发送错误响应"""
#         response = {
#             "type": "error",
#             "error_message": error_message,
#             "timestamp": time.time(),
#         }
#         agent_id = msg_from.get("agent_id")
#         if agent_id:
#             await self.send_to_agent(agent_id, response)

#     async def send_to_agent(self, agent_id: int, message_data: Dict):
#         """向指定Agent发送消息"""
#         try:
#             await self.send_message(
#                 message_data, instruction=MessageInstruction.MESSAGE, target_id=agent_id
#             )
#         except Exception as e:
#             print(f"❌ 发送消息到Agent {agent_id} 失败: {e}")


# class LLMSystem(System):
#     """
#     LLM系统 - 重新实现版本

#     核心设计原则:
#     1. 使用专门的线程运行异步事件循环
#     2. 通过线程安全的队列在同步和异步代码间通信
#     3. 在同步的update方法中处理队列消息
#     """

#     def __init__(self):
#         super().__init__(priority=5)

#         # WebSocket服务器配置
#         self.server_url = "ws://localhost:8000/ws/metaverse"
#         self.env_id = 1

#         # 连接状态管理
#         self.connection_status = (
#             "disconnected"  # disconnected, connecting, connected, error
#         )
#         self.environment_client = None

#         # 异步线程和事件循环
#         self.async_thread = None
#         self.async_loop = None
#         self.should_stop = False

#         # 线程安全的消息队列
#         self.incoming_messages = None  # 将在线程中初始化
#         self.outgoing_messages = None  # 将在线程中初始化
#         self.sync_message_queue = []  # 同步线程的消息队列

#         # LLM会话管理
#         self.active_sessions = {}
#         self.connected_agents = {}

#         # 观测数据缓存
#         self.last_observation = {}
#         self.observation_cache_time = 0.0
#         self.cache_duration = 0.5

#         # 动作执行
#         self.pending_actions = []
#         self.action_results = {}

#     def initialize(self, world: World) -> None:
#         """初始化LLM系统"""
#         self.world = world
#         print("🚀 初始化LLM系统...")

#         # 启动异步线程
#         self._start_async_thread()

#         # 初始化观测系统
#         self._initialize_observation_system()

#     def _start_async_thread(self):
#         """启动异步处理线程"""
#         print("🧵 启动异步WebSocket线程...")

#         self.should_stop = False
#         self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
#         self.async_thread.start()

#         # 等待一下确保线程启动
#         time.sleep(0.1)

#     def _run_async_loop(self):
#         """在专门线程中运行异步事件循环"""
#         try:
#             # 创建新的事件循环
#             self.async_loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(self.async_loop)

#             # 在异步上下文中初始化队列
#             self.incoming_messages = asyncio.Queue()
#             self.outgoing_messages = asyncio.Queue()

#             print("🔄 异步事件循环已启动")

#             # 运行主要的异步任务
#             self.async_loop.run_until_complete(self._async_main())

#         except Exception as e:
#             print(f"❌ 异步线程出错: {e}")
#             self.connection_status = "error"
#         finally:
#             print("🔄 异步事件循环已关闭")

#     async def _async_main(self):
#         """异步主函数"""
#         try:
#             # 创建环境客户端
#             self.environment_client = LLMEnvironmentClient(
#                 self.server_url, self.env_id, self
#             )

#             # 启动连接任务
#             connection_task = asyncio.create_task(self._maintain_connection())

#             # 启动消息处理任务
#             message_task = asyncio.create_task(self._process_messages())

#             # 等待任务完成或停止信号
#             while not self.should_stop:
#                 await asyncio.sleep(0.1)

#                 # 检查任务状态
#                 if connection_task.done():
#                     try:
#                         await connection_task
#                     except Exception as e:
#                         print(f"❌ 连接任务异常: {e}")
#                         # 重启连接任务
#                         connection_task = asyncio.create_task(
#                             self._maintain_connection()
#                         )

#                 if message_task.done():
#                     try:
#                         await message_task
#                     except Exception as e:
#                         print(f"❌ 消息处理任务异常: {e}")
#                         # 重启消息任务
#                         message_task = asyncio.create_task(self._process_messages())

#             # 清理
#             connection_task.cancel()
#             message_task.cancel()

#             # 等待任务清理完成
#             await asyncio.gather(connection_task, message_task, return_exceptions=True)

#         except Exception as e:
#             print(f"❌ 异步主函数异常: {e}")

#     async def _maintain_connection(self):
#         """维护WebSocket连接"""
#         retry_count = 0
#         max_retries = 5

#         while not self.should_stop and retry_count < max_retries:
#             try:
#                 print(
#                     f"🔌 尝试连接到WebSocket服务器... (尝试 {retry_count + 1}/{max_retries})"
#                 )
#                 self.connection_status = "connecting"

#                 # 连接到服务器
#                 await self.environment_client.connect()

#                 print("✅ WebSocket连接成功建立")
#                 self.connection_status = "connected"
#                 retry_count = 0  # 重置重试计数

#                 # 保持连接
#                 while not self.should_stop and self.environment_client.connected:
#                     await asyncio.sleep(1)

#                 print("🔌 WebSocket连接已断开")
#                 self.connection_status = "disconnected"

#             except Exception as e:
#                 print(f"❌ WebSocket连接失败: {e}")
#                 self.connection_status = "error"
#                 retry_count += 1

#                 if retry_count < max_retries:
#                     wait_time = min(2**retry_count, 30)  # 指数退避，最多30秒
#                     print(f"⏰ {wait_time}秒后重试连接...")
#                     await asyncio.sleep(wait_time)
#                 else:
#                     print("❌ 达到最大重试次数，停止连接尝试")
#                     break

#     async def _process_messages(self):
#         """处理消息队列"""
#         while not self.should_stop:
#             try:
#                 # 处理发出的消息
#                 if not self.outgoing_messages.empty():
#                     message = await asyncio.wait_for(
#                         self.outgoing_messages.get(), timeout=0.1
#                     )
#                     if self.environment_client and self.environment_client.connected:
#                         await self.environment_client.send_message(message)

#                 # 检查是否有新的传入消息（这里主要是为了保持队列处理的结构）
#                 await asyncio.sleep(0.1)

#             except asyncio.TimeoutError:
#                 # 正常的超时，继续循环
#                 continue
#             except Exception as e:
#                 print(f"❌ 消息处理出错: {e}")
#                 await asyncio.sleep(1)

#     def update(self, delta_time: float) -> None:
#         """更新LLM系统（在主游戏线程中调用）"""
#         # 1. 检查连接状态
#         self._check_connection_status()

#         # 2. 处理同步消息队列
#         self._process_sync_messages()

#         # 3. 执行待处理的动作
#         self._execute_pending_actions(delta_time)

#         # 4. 发送游戏状态更新
#         self._send_game_state_updates()

#     def _check_connection_status(self):
#         """检查连接状态"""
#         # 检查异步线程是否还在运行
#         if self.async_thread and not self.async_thread.is_alive():
#             print("⚠️ 异步线程已停止，尝试重启...")
#             self._start_async_thread()

#     def _process_sync_messages(self):
#         """处理同步消息队列"""
#         # 这里可以处理从异步线程传递过来的消息
#         # 当前版本中暂时为空，后续可以扩展
#         pass

#     def _execute_pending_actions(self, delta_time: float):
#         """执行待处理的动作"""
#         if not self.pending_actions:
#             return

#         # 处理所有待处理的动作
#         actions_to_remove = []
#         for i, action in enumerate(self.pending_actions):
#             try:
#                 result = self._execute_action(action)
#                 self.action_results[action.get("id", i)] = result
#                 actions_to_remove.append(i)
#             except Exception as e:
#                 print(f"❌ 执行动作失败: {e}")
#                 actions_to_remove.append(i)

#         # 移除已处理的动作
#         for i in reversed(actions_to_remove):
#             del self.pending_actions[i]

#     def _send_game_state_updates(self):
#         """发送游戏状态更新"""
#         # 如果有连接的代理，发送状态更新
#         if (
#             self.connection_status == "connected"
#             and self.connected_agents
#             and time.time() - self.observation_cache_time > self.cache_duration
#         ):

#             # 生成新的观测数据
#             self._update_observation_cache()

#     # =============================================
#     # 异步消息处理方法
#     # =============================================

#     async def handle_session_init_async(
#         self, msg_from: Dict, msg_data: Dict
#     ) -> Dict[str, Any]:
#         """异步处理会话初始化"""
#         agent_id = msg_from.get("agent_id")
#         faction = msg_data.get("player_faction", "WEI")

#         # 创建会话数据
#         session_data = {
#             "agent_id": agent_id,
#             "faction": faction,
#             "control_level": msg_data.get("control_level", "full"),
#             "capabilities": msg_data.get("capabilities", []),
#             "created_at": time.time(),
#             "active": True,
#         }

#         self.active_sessions[agent_id] = session_data

#         # 生成初始观测
#         initial_observation = self._generate_full_observation(faction)

#         return {
#             "status": "success",
#             "assigned_faction": faction,
#             "game_state": "turn_based",
#             "current_turn": self._get_current_turn(),
#             "permissions": session_data["capabilities"],
#             "initial_observation": initial_observation,
#         }

#     async def handle_observation_request_async(
#         self, msg_from: Dict, msg_data: Dict
#     ) -> Dict[str, Any]:
#         """异步处理观测请求"""
#         agent_id = msg_from.get("agent_id")
#         faction = msg_data.get("faction", "WEI")
#         observation_type = msg_data.get("observation_type", "full")

#         if observation_type == "full":
#             observation_data = self._generate_full_observation(faction)
#         elif observation_type == "partial":
#             observation_data = self._generate_partial_observation(
#                 faction, msg_data.get("focus_area", {})
#             )
#         elif observation_type == "tactical":
#             observation_data = self._generate_tactical_observation(
#                 faction, msg_data.get("target_units", [])
#             )
#         else:
#             observation_data = self._generate_basic_observation(faction)

#         return observation_data

#     async def handle_action_command_async(
#         self, msg_from: Dict, msg_data: Dict
#     ) -> Dict[str, Any]:
#         """异步处理动作指令"""
#         agent_id = msg_from.get("agent_id")
#         action_type = msg_data.get("action_type")
#         action_params = msg_data.get("params", {})

#         # 验证动作合法性
#         if not self._validate_action(action_type, action_params, agent_id):
#             return {"status": "error", "message": "动作验证失败"}

#         # 添加到待执行队列
#         action = {
#             "type": action_type,
#             "params": action_params,
#             "agent_id": agent_id,
#             "timestamp": time.time(),
#             "id": f"{agent_id}_{int(time.time() * 1000)}",
#         }
#         self.pending_actions.append(action)

#         return {"status": "queued", "action_id": action["id"]}

#     async def handle_strategy_query_async(
#         self, msg_from: Dict, msg_data: Dict
#     ) -> Dict[str, Any]:
#         """异步处理策略查询"""
#         query_type = msg_data.get("query_type", "tactical_analysis")

#         # 这里返回模拟的策略数据
#         return {
#             "query_type": query_type,
#             "analysis": "战术分析结果",
#             "recommendations": ["建议1", "建议2"],
#             "timestamp": time.time(),
#         }

#     # =============================================
#     # 观测系统实现
#     # =============================================

#     def _initialize_observation_system(self):
#         """初始化观测系统"""
#         self.last_observation = {}
#         self.observation_cache_time = 0.0

#     def _update_observation_cache(self):
#         """更新观测缓存"""
#         self.observation_cache_time = time.time()
#         # 这里可以更新观测数据缓存

#     def _generate_full_observation(self, faction: Faction) -> Dict[str, Any]:
#         """生成完整观测"""
#         return {
#             "type": "full_observation",
#             "faction": faction,
#             "timestamp": time.time(),
#             "game_state": self._collect_game_state(),
#             "units": self._collect_unit_information(faction),
#             "map": self._collect_map_information(faction),
#         }

#     def _generate_partial_observation(
#         self, faction: Faction, focus_area: Dict
#     ) -> Dict[str, Any]:
#         """生成部分观测"""
#         return {
#             "type": "partial_observation",
#             "faction": faction,
#             "focus_area": focus_area,
#             "timestamp": time.time(),
#         }

#     def _generate_tactical_observation(
#         self, faction: Faction, target_units: List[int]
#     ) -> Dict[str, Any]:
#         """生成战术观测"""
#         return {
#             "type": "tactical_observation",
#             "faction": faction,
#             "target_units": target_units,
#             "timestamp": time.time(),
#         }

#     def _generate_basic_observation(self, faction: Faction) -> Dict[str, Any]:
#         """生成基本观测"""
#         return {
#             "type": "basic_observation",
#             "faction": faction,
#             "timestamp": time.time(),
#         }

#     # =============================================
#     # 动作执行系统
#     # =============================================

#     def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
#         """执行具体动作"""
#         action_type = action["type"]
#         params = action["params"]

#         if action_type == "move_unit":
#             return self._execute_move_unit(params)
#         elif action_type == "attack_unit":
#             return self._execute_attack_unit(params)
#         elif action_type == "end_turn":
#             return self._execute_end_turn(params)
#         elif action_type == "set_strategy":
#             return self._execute_set_strategy(params)
#         else:
#             return {"status": "error", "message": f"未知动作类型: {action_type}"}

#     def _execute_move_unit(self, params: Dict[str, Any]) -> Dict[str, Any]:
#         """执行移动单位"""
#         return {"status": "success", "message": "单位移动完成"}

#     def _execute_attack_unit(self, params: Dict[str, Any]) -> Dict[str, Any]:
#         """执行攻击单位"""
#         return {"status": "success", "message": "攻击执行完成"}

#     def _execute_end_turn(self, params: Dict[str, Any]) -> Dict[str, Any]:
#         """执行结束回合"""
#         return {"status": "success", "message": "回合结束"}

#     def _execute_set_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
#         """执行设置策略"""
#         return {"status": "success", "message": "策略设置完成"}

#     # =============================================
#     # 辅助方法
#     # =============================================

#     def _validate_action(
#         self, action_type: str, params: Dict[str, Any], agent_id: str
#     ) -> bool:
#         """验证动作合法性"""
#         return True  # 简化版本，总是返回True

#     def _collect_game_state(self) -> Dict[str, Any]:
#         """收集游戏状态"""
#         return {"current_turn": 1, "phase": "movement"}

#     def _collect_unit_information(self, faction: Faction) -> Dict[str, Any]:
#         """收集单位信息"""
#         return {"units": []}

#     def _collect_map_information(self, faction: Faction) -> Dict[str, Any]:
#         """收集地图信息"""
#         return {"map_size": [10, 10]}

#     def _get_current_turn(self) -> str:
#         """获取当前回合"""
#         return "Turn 1"

#     # =============================================
#     # 公共接口
#     # =============================================

#     def get_connection_status(self) -> str:
#         """获取连接状态"""
#         return self.connection_status

#     def get_connected_agents(self) -> List[Dict[str, Any]]:
#         """获取连接的代理列表"""
#         return list(self.connected_agents.values())

#     def shutdown(self):
#         """关闭LLM系统"""
#         print("🛑 关闭LLM系统...")

#         # 设置停止标志
#         self.should_stop = True

#         # 等待异步线程结束
#         if self.async_thread and self.async_thread.is_alive():
#             self.async_thread.join(timeout=5)

#         print("✅ LLM系统已关闭")

#     def subscribe_events(self) -> None:
#         """订阅游戏事件"""
#         pass

#     def _get_movement_system(self):
#         """获取移动系统"""
#         for system in self.world.systems:
#             if system.__class__.__name__ == "MovementSystem":
#                 return system
#         return None


"""
LLM系统 - 通过Star Client WebSocket框架与外部LLM通信，执行观测和动作
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple

from rich import print_json
from framework_v2 import System, World
from ..components import (
    Unit,
    Health,
    HexPosition,
    Movement,
    Combat,
    Vision,
    GameState,
    FogOfWar,
    Player,
    AIControlled,
    GameStats,
    BattleLog,
    UnitObservation,
)
from ..prefabs.config import Faction, PlayerType, GameMode

from llm.star_client import SyncWebSocketClient, ClientInfo

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
        # self.actions["move"] = self.move
        self.actions["observation"] = self.handle_observation
        self.actions["move"] = self.handle_move

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
        params = data.get("parameters")
        if action == "observation":
            res = self.handle_observation(params)
            print(f"Observation response: {res}")
            self.client.response_to_agent(agent_id, action_id, res, "str")
        elif action == "move":
            res = self.handle_move(params)
            print(f"Move response: {res}")
            self.client.response_to_agent(agent_id, action_id, res, "str")
        else:
            print(f"未知动作: {action}")
            self.client.response_to_agent(
                agent_id, action_id, f"未知动作: {action}", "str"
            )

    def handle_observation(self, data: Dict) -> Dict[str, Any]:
        """异步处理观测请求"""
        faction = data.get("faction", "WEI")
        observation_type = data.get("observation_type", "full")

        # # TODO: 根据请求类型生成观测数据
        # if observation_type == "full":  # 完整观测
        #     observation_data = self._generate_full_observation(faction)
        # elif observation_type == "partial":  # 部分观测
        #     observation_data = self._generate_partial_observation(
        #         faction, data.get("focus_area")  # 关注区域
        #     )
        # elif observation_type == "tactical":
        #     observation_data = self._generate_tactical_observation(
        #         faction, data.get("target_units")
        #     )
        # else:
        observation_data = self._generate_basic_observation(faction)

        return observation_data

    def _generate_basic_observation(self, faction: Faction) -> Dict[str, Any]:
        """生成基本观测数据"""
        # TODO: 实现基本观测
        return {
            "game_state": self._collect_game_state(),
            "faction": faction,
            "timestamp": time.time(),
        }

    def _collect_game_state(self) -> Dict[str, Any]:
        """收集游戏状态信息"""
        game_state = self.world.get_singleton_component(GameState)

        if not game_state:
            return {"error": "Game state not available"}

        return {
            "current_player": (
                game_state.current_player.value
                if hasattr(game_state.current_player, "value")
                else str(game_state.current_player)
            ),
            "game_mode": (
                game_state.game_mode.value
                if hasattr(game_state.game_mode, "value")
                else str(game_state.game_mode)
            ),
            "turn_number": getattr(game_state, "turn_number", 1),
            "phase": getattr(game_state, "phase", "action"),
            "time_limit": getattr(game_state, "time_limit", None),
            "victory_condition": getattr(
                game_state, "victory_condition", "elimination"
            ),
        }

    def handle_move(self, data: Dict) -> Dict[str, Any]:
        """处理移动指令"""
        agent_id = data.get("msg_from", {}).get("agent_id")
        action_type = data.get("action_type")
        action_params = data.get("parameters", {})

        # TODO: 验证动作合法性
        # if not self._validate_action(action_type, action_params, agent_id):
        #     return {"success": False, "error": "Invalid action"}

        # 添加到待执行队列
        # action = {
        #     "type": action_type,
        #     "params": action_params,
        #     "agent_id": agent_id,
        #     "timestamp": time.time(),
        # }
        # self.pending_actions.append(action)

        # # 立即执行 (或返回待执行状态)
        # result = self._execute_action(action)
        # return result

        return {
            "success": True,
            "message": f"Agent {agent_id} moved with action {action_type}",
        }

    def cleanup(self):
        """清理资源"""
        try:
            self.disconnect()
        except Exception as e:
            print(f"断开连接时出错: {e}")
