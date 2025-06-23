"""
LLM客户端示例和消息协议文档 - 基于 Star Client 框架
"""

# =============================================
# 消息协议定义 (Star Client 格式)
# =============================================

"""
Star Client WebSocket消息格式 (JSON):
{
    "instruction": "message_instruction",
    "msg_from": {
        "role_type": "agent",
        "env_id": 1,
        "agent_id": 1
    },
    "msg_to": {
        "role_type": "env", 
        "env_id": 1
    },
    "data": { ... },
    "timestamp": 1234567890.123
}

支持的消息指令:
1. connect - 连接初始化
2. message - 普通消息传递
3. heartbeat - 心跳包
4. disconnect - 断开连接
5. error - 错误消息

支持的数据类型 (data字段):
1. session_init - 初始化会话
2. observation_request - 请求观测数据  
3. action_command - 执行动作指令
4. strategy_query - 策略查询
5. game_state_update - 游戏状态更新
"""

# =============================================
# 1. 连接初始化 (Star Client格式)
# =============================================

# Agent (LLM) 连接到游戏环境
connect_message = {
    "instruction": "connect",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {},
    "timestamp": 1234567890.123,
}

# 会话初始化请求
session_init_message = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "session_init",
        "llm_model": "gpt-4",
        "player_faction": "WEI",  # 控制的阵营
        "control_level": "full",  # full, partial, advisory
        "observation_frequency": 1.0,  # 观测频率(秒)
        "capabilities": ["move", "attack", "strategy", "end_turn"],
    },
    "timestamp": 1234567890.123,
}

# 会话初始化响应
session_init_response = {
    "instruction": "message",
    "msg_from": {"role_type": "env", "env_id": 1},
    "msg_to": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "data": {
        "type": "session_response",
        "status": "success",
        "assigned_faction": "WEI",
        "game_state": "turn_based",
        "current_turn": "WEI",
        "permissions": ["move", "attack", "end_turn"],
        "initial_observation": {...},  # 初始游戏状态
    },
    "timestamp": 1234567890.123,
}

# =============================================
# 2. 观测请求 (Star Client格式)
# =============================================

observation_request = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "observation_request",
        "observation_type": "full",  # full, partial, tactical, strategic
        "faction": "WEI",
        "focus_area": {  # 可选，用于partial观测
            "center": {"col": 10, "row": 8},
            "radius": 5,
        },
        "target_units": [101, 102, 103],  # 可选，用于tactical观测
        "include_predictions": True,  # 是否包含AI预测
        "detail_level": "high",  # low, medium, high
    },
    "timestamp": 1234567890.123,
}

observation_response = {
    "instruction": "message",
    "msg_from": {"role_type": "env", "env_id": 1},
    "msg_to": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "data": {
        "type": "observation_response",
        "game_state": {
            "current_turn": "WEI",
            "turn_number": 15,
            "game_mode": "turn_based",
            "time_remaining": 120.5,
            "phase": "action",  # action, combat, end
        },
        "map_info": {
            "size": {"width": 20, "height": 15},
            "visible_tiles": [
                {"col": 5, "row": 3, "terrain": "plains", "visibility": "visible"},
                {"col": 6, "row": 3, "terrain": "forest", "visibility": "fog_of_war"},
            ],
            "strategic_points": [
                {
                    "type": "city",
                    "position": {"col": 10, "row": 5},
                    "controlled_by": "WEI",
                }
            ],
        },
        "units": {
            "own_units": [
                {
                    "id": 101,
                    "type": "infantry",
                    "position": {"col": 8, "row": 4},
                    "health": {"current": 80, "maximum": 100},
                    "movement": {"remaining": 3, "maximum": 4},
                    "combat": {"attack": 15, "defense": 12, "range": 1},
                    "status": ["healthy"],
                    "can_act": True,
                }
            ],
            "enemy_units": [
                {
                    "id": 201,
                    "type": "cavalry",
                    "position": {"col": 12, "row": 6},
                    "health": {"current": 90, "maximum": 100},
                    "estimated_threat": "high",
                    "visibility": "visible",
                }
            ],
        },
        "visibility": {
            "vision_range": 6,
            "fog_of_war_tiles": [...],
            "scouted_areas": [...],
            "enemy_activity": [
                {
                    "position": {"col": 15, "row": 10},
                    "last_seen": 1234567880.0,
                    "unit_type": "unknown",
                }
            ],
        },
        "battle_log": {
            "recent_events": [
                {
                    "timestamp": 1234567885.0,
                    "type": "combat",
                    "attacker": {"id": 101, "faction": "WEI"},
                    "target": {"id": 202, "faction": "SHU"},
                    "damage": 25,
                    "result": "hit",
                }
            ]
        },
        "statistics": {
            "faction_stats": {
                "WEI": {"units": 8, "total_health": 720, "territories": 3},
                "SHU": {"units": 6, "total_health": 540, "territories": 2},
            },
            "resource_status": {"gold": 150, "supplies": 80},
        },
        "ai_predictions": {  # 可选，如果请求了AI预测
            "enemy_likely_moves": [...],
            "strategic_recommendations": [...],
            "threat_assessment": {...},
        },
    },
    "timestamp": 1234567890.123,
}

# =============================================
# 3. 动作指令 (Star Client格式)
# =============================================

# 移动单位
move_action = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "action_command",
        "action_type": "move_unit",
        "params": {
            "unit_id": 101,
            "target_position": {"col": 9, "row": 5},
            "path": [  # 可选，指定路径
                {"col": 8, "row": 4},
                {"col": 8, "row": 5},
                {"col": 9, "row": 5},
            ],
            "move_type": "normal",  # normal, forced_march, cautious
        },
    },
    "timestamp": 1234567890.123,
}

# 攻击单位
attack_action = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "action_command",
        "action_type": "attack_unit",
        "params": {
            "attacker_id": 101,
            "target_id": 201,
            "attack_type": "normal",  # normal, charge, defensive
            "use_special_ability": False,
        },
    },
    "timestamp": 1234567890.123,
}

# 结束回合
end_turn_action = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "action_command",
        "action_type": "end_turn",
        "params": {"faction": "WEI", "confirm": True},
    },
    "timestamp": 1234567890.123,
}

# 设置策略
strategy_action = {
    "instruction": "message",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {
        "type": "action_command",
        "action_type": "set_strategy",
        "params": {
            "strategy_type": "defensive",  # aggressive, defensive, balanced
            "target_areas": [{"col": 10, "row": 8}],
            "priority_targets": [201, 202],
            "formation": "turtle",  # line, turtle, wedge, scattered
        },
    },
    "timestamp": 1234567890.123,
}

# 动作执行结果
action_result = {
    "instruction": "message",
    "msg_from": {"role_type": "env", "env_id": 1},
    "msg_to": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "data": {
        "type": "action_result",
        "action_type": "move_unit",
        "result": {
            "success": True,
            "unit_id": 101,
            "final_position": {"col": 9, "row": 5},
            "movement_used": 2,
            "movement_remaining": 1,
            "triggered_events": [
                {"type": "visibility_change", "new_visible_tiles": [...]}
            ],
            "status_changes": ["moved"],
        },
    },
    "timestamp": 1234567890.123,
}

# =============================================
# 4. 策略查询
# =============================================

strategy_query = {
    "type": "strategy_query",
    "session_id": "llm_session_001",
    "client_id": "gpt4_client",
    "data": {
        "query_type": "tactical_analysis",  # tactical_analysis, strategic_advice, threat_assessment
        "context": {
            "situation": "enemy_approaching",
            "target_area": {"col": 10, "row": 8, "radius": 3},
            "time_horizon": "short_term",  # short_term, medium_term, long_term
            "risk_tolerance": "medium",  # low, medium, high
        },
    },
}

strategy_response = {
    "type": "strategy_response",
    "session_id": "llm_session_001",
    "timestamp": 1234567890.123,
    "data": {
        "query_type": "tactical_analysis",
        "analysis": {
            "current_situation": "Enemy cavalry unit advancing on eastern flank",
            "threats": [
                {"type": "flanking_attack", "probability": 0.7, "severity": "high"},
                {"type": "supply_line_cut", "probability": 0.4, "severity": "medium"},
            ],
            "opportunities": [
                {"type": "counter_attack", "success_chance": 0.6, "benefit": "high"}
            ],
            "recommendations": [
                {
                    "action": "move_unit",
                    "params": {"unit_id": 102, "target": {"col": 11, "row": 7}},
                    "reason": "Block enemy advance route",
                    "priority": "high",
                },
                {
                    "action": "attack_unit",
                    "params": {"attacker_id": 101, "target_id": 201},
                    "reason": "Eliminate key threat",
                    "priority": "medium",
                },
            ],
            "alternative_strategies": [
                {
                    "name": "defensive_fallback",
                    "description": "Retreat to defensive positions",
                    "pros": ["Reduced casualties", "Better positioning"],
                    "cons": ["Lost territory", "Initiative lost"],
                }
            ],
        },
    },
}

# =============================================
# 5. 错误处理
# =============================================

error_response = {
    "type": "error",
    "session_id": "llm_session_001",
    "timestamp": 1234567890.123,
    "data": {
        "error_code": "INVALID_ACTION",
        "error_message": "Unit 101 cannot move to position (15, 20) - out of range",
        "error_details": {
            "unit_id": 101,
            "current_position": {"col": 8, "row": 4},
            "target_position": {"col": 15, "row": 20},
            "movement_remaining": 3,
            "required_movement": 12,
        },
        "suggestions": [
            "Try a position within movement range",
            "Use multiple turns to reach the destination",
            "Consider using forced march ability",
        ],
        "original_message": {...},  # 导致错误的原始消息
    },
}

# =============================================
# 6. 心跳和连接管理 (Star Client格式)
# =============================================

heartbeat = {
    "instruction": "heartbeat",
    "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": 1},
    "msg_to": {"role_type": "env", "env_id": 1},
    "data": {"status": "active", "latency": 45.2},  # 毫秒
    "timestamp": 1234567890.123,
}

connection_status = {
    "type": "connection_status",
    "data": {
        "status": "connected",  # connected, disconnected, reconnecting
        "session_count": 1,
        "server_load": "low",  # low, medium, high
        "game_state": "active",
    },
}

# =============================================
# 使用示例 (基于 Star Client 框架)
# =============================================

"""
# LLM客户端连接示例 (使用 Star Client):

import asyncio
from llm.star_client import AgentClient

class LLMGameClient(AgentClient):
    def __init__(self, server_url: str, env_id: int, agent_id: int):
        super().__init__(server_url, env_id, agent_id)
        
        # 添加事件监听器
        self.add_event_listener("message", self.on_message)
        self.add_event_listener("connect", self.on_connect)
        self.add_event_listener("disconnect", self.on_disconnect)
        
    async def on_connect(self, data):
        # 连接成功后初始化会话
        await self.initialize_session()
        
    async def on_message(self, data):
        msg_data = data.get("data", {})
        msg_type = msg_data.get("type")
        
        if msg_type == "observation_response":
            # 处理观测数据
            await self.process_observation(msg_data)
            
        elif msg_type == "action_result":
            # 处理动作结果
            await self.process_action_result(msg_data)
            
        elif msg_type == "session_response":
            # 处理会话响应
            await self.process_session_response(msg_data)
    
    async def initialize_session(self):
        # 发送会话初始化请求
        await self.send_message(
            "message",
            {
                "type": "session_init",
                "llm_model": "gpt-4",
                "player_faction": "WEI",
                "control_level": "full",
                "capabilities": ["move", "attack", "strategy", "end_turn"]
            },
            target={"role_type": "env", "env_id": self.client_info.env_id}
        )
    
    async def request_observation(self, observation_type="full"):
        # 请求观测数据
        await self.send_message(
            "message",
            {
                "type": "observation_request",
                "observation_type": observation_type,
                "faction": "WEI",
                "detail_level": "high"
            },
            target={"role_type": "env", "env_id": self.client_info.env_id}
        )
    
    async def perform_game_action(self, action_type, params):
        # 执行游戏动作
        await self.send_message(
            "message",
            {
                "type": "action_command",
                "action_type": action_type,
                "params": params
            },
            target={"role_type": "env", "env_id": self.client_info.env_id}
        )
    
    async def process_observation(self, observation_data):
        # 基于观测数据做决策
        game_state = observation_data.get("game_state", {})
        units = observation_data.get("units", {})
        
        # LLM决策逻辑 (这里是示例)
        if game_state.get("current_turn") == "WEI":
            # 分析当前状态并决定动作
            action = self.decide_action(observation_data)
            if action:
                await self.perform_game_action(action["type"], action["params"])
    
    def decide_action(self, observation_data):
        # 简单的决策逻辑 (实际应该调用LLM)
        own_units = observation_data.get("units", {}).get("own_units", [])
        for unit in own_units:
            if unit.get("can_act") and unit.get("movement", {}).get("remaining", 0) > 0:
                # 简单移动示例
                current_pos = unit.get("position", {})
                target_pos = {"col": current_pos.get("col", 0) + 1, "row": current_pos.get("row", 0)}
                return {
                    "type": "move_unit",
                    "params": {
                        "unit_id": unit["id"],
                        "target_position": target_pos
                    }
                }
        return None

# 使用示例
async def main():
    client = LLMGameClient("ws://localhost:8765", env_id=1, agent_id=1)
    
    try:
        await client.connect()
        
        # 保持连接并处理消息
        while client.connected:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
"""
