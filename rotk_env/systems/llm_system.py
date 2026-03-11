"""
LLM System - Global game control interface
Provides full game operation capabilities: system control + delegated unit actions + delegated observation queries
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass

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


# ==================== Action Request Data Structure ====================

@dataclass
class ActionRequest:
    """Encapsulates an action request from an LLM agent"""
    agent_id: Optional[str]
    action_id: Union[int, str]
    action_name: str
    parameters: Dict[str, Any]
    timestamp: float


# ==================== Action Executor ====================

class ActionExecutor:
    """
    Handles the execution logic for LLM actions.
    Decouples action reception from action execution.
    """
    
    def __init__(self, llm_system):
        """
        Initialize the ActionExecutor with a reference to the LLMSystem.
        
        Args:
            llm_system: Reference to the parent LLMSystem instance
        """
        self.llm_system = llm_system
        self.world = llm_system.world
        
    def execute(self, request: ActionRequest) -> Dict[str, Any]:
        """
        Execute a single action request and return the result.
        
        Args:
            request: The ActionRequest to execute
            
        Returns:
            Dict containing the execution result
        """
        action = request.action_name
        params = request.parameters
        
        # 1. Check if this is a system-level action
        if action in self.llm_system.system_actions:
            result = self.llm_system.system_actions[action](params)
            
        # 2. Check if this is a unit action (delegate to ActionHandler)
        elif action in self.llm_system.action_handler.action_handlers:
            result = self.llm_system.action_handler.execute_action(action, params)
            
        # 3. Check if this is an observation action (delegate to ObservationSystem)
        elif self.llm_system._is_observation_action(action):
            result = self.llm_system._handle_observation_action(action, params)
            
        # 4. Unknown action
        else:
            result = self.llm_system._create_system_error_response(
                action, f"UNKNOWN ACTION: {action}", 2010
            )
            
        return result


class SyncEnvClient(SyncWebSocketClient):
    """Synchronous environment client"""

    def __init__(self, server_url: str, env_id: str):
        client_info = ClientInfo(type=ClientType.ENVIRONMENT, id=env_id)
        super().__init__(server_url, client_info)
        self.connected_agents = {}

    def url(self) -> str:
        """Build the environment connection URL"""
        return f"{self.server_url}/env/{self.client_info.id}"

    def response_to_agent(
        self, agent_id: str, action_id: int, outcome: str, outcome_type: str = "str"
    ):
        """Send a response to an Agent - synchronous interface"""
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
    """LLM System - Global game control interface"""

    def __init__(self):
        super().__init__()
        self.name = "LLMSystem"
        
        # Game-end notification state
        self.game_end_notified = False
        # Message-level cooldown (encourages batch sending)
        self.message_cooldown_seconds: float = 0
        self._agent_last_message_ts: Dict[str, float] = {}
        # Reliable turn_start delivery: wait for ACK or retry. key=agent_id, value={turn_number, faction_key, next_retry_time, retry_count, notification}
        self._pending_turn_start_ack: Dict[str, dict] = {}
        self._turn_start_retry_interval: float = 8.0
        self._turn_start_max_retries: int = 5

        # System-level error codes
        self.system_error_codes = {
            2001: "Game not initialized",
            2002: "Game already finished",
            2003: "Operation not supported in current game mode",
            2004: "Insufficient system resources",
            2005: "Insufficient permissions",
            2006: "Operation timed out",
            2007: "Parameter validation failed",
            2008: "Invalid system state",
            2009: "Network connection error",
            2010: "Internal service error",
            2011: "Operation rate limit exceeded",
        }

    def initialize(self, world):
        self.world = world

        # Initialize delegation objects
        self.action_handler = LLMActionHandler(world)
        self.observation_system = LLMObservationSystem(world)

        # Initialize ActionExecutor
        self.action_executor = ActionExecutor(self)

        # Use synchronous client
        # env_id: read from ENV_ID environment variable for multi-process isolation in auto_test; default env_1
        _env_id = os.environ.get("ENV_ID", "env_1")
        self.client = SyncEnvClient(
            server_url="ws://localhost:8000/ws/metaverse",
            env_id=_env_id,
        )
        self.add_listener()

        # Initialize system-level action mapping
        self.system_actions = self._init_system_actions()

        self.connect()
        return

    def _init_system_actions(self) -> Dict[str, callable]:
        """Initialize system-level action mapping"""
        return {
            "strategy_ping": self.handle_strategy_ping,
            "report_llm_stats": self.handle_report_llm_stats,
            "retrieve_game_status": self.handle_retrieve_game_status,
            "register_agent_info": self.handle_register_agent_info,
        }

    def add_listener(self):
        # Add event listeners
        self.client.add_hub_listener("message", self.on_message)
        self.client.add_hub_listener("connect", self.on_connect)
        self.client.add_hub_listener("disconnect", self.on_disconnect)
        self.client.add_hub_listener("error", self.on_error)

    # === WebSocket event handler methods ===

    def on_message(self, envelope):
        """Handle a received message"""
        print(f"LLMSystem received message")
        try:
            # Parse the new Envelope structure
            sender = envelope.get("sender", {})
            recipient = envelope.get("recipient", {})
            payload = envelope.get("payload", {})
            message_type = envelope.get("type", "")
            now = time.time()
            if payload.get("type") == "action":
                # Handle action message

                print(f"[LLM SYSTEM] Handling action message: {payload}")

                # Extract agent info
                agent_id = sender.get("id") if sender.get("type") == "agent" else None
                if agent_id:
                    self.client.connected_agents[agent_id] = sender
                # Record one message-level interaction (single-action message)

                last_ts = self._agent_last_message_ts.get(agent_id)
                if last_ts is not None:
                    elapsed = now - last_ts
                    print(f"[LLMSystem] Agent ID: {agent_id} action sending interval: {elapsed}")
                self._agent_last_message_ts[agent_id] = now
                
                self.exec_action(envelope)
                self._record_message(agent_id, payload.get("parameters"))
                return
            elif payload.get("type") == "action_batch":
                # Handle batch action message
                actions = payload.get("actions", [])
                batch_id = payload.get("id") or int(time.time() * 1e9)
                agent_id = sender.get("id") if sender.get("type") == "agent" else None
                if agent_id:
                    self.client.connected_agents[agent_id] = sender
                # Message-level cooldown check (only applies when the batch contains non-system actions; skip cooldown for purely system actions)
                try:
                    has_non_system_action = False
                    for _item in (actions or []):
                        _act = (_item or {}).get("action")
                        if not _act or _act not in self.system_actions:
                            has_non_system_action = True
                            break
                except Exception:
                    has_non_system_action = True
                if has_non_system_action:
                    if not self._enforce_message_cooldown(agent_id, batch_id):
                        return

                # After passing the cooldown check, record one message-level interaction (batch messages counted once)
                self._record_message(agent_id, None)

                try:
                    size = len(actions)
                except Exception:
                    size = 0
                print(f"[LLM SYSTEM] Handling batched actions: count={size}")

                batch_results: List[Dict[str, Any]] = []
                for idx, item in enumerate(actions):
                    action_name = item.get("action")
                    action_request_id = item.get("id") or f"{batch_id}_{idx}"
                    if not action_name:
                        error_result = self._create_system_error_response(
                            "unknown",
                            "Missing action name in batch item",
                            2007,
                        )
                        batch_results.append(
                            {
                                "id": action_request_id,
                                "action": action_name,
                                "response": error_result,
                                "success": False,
                            }
                        )
                        continue

                    params = self._prepare_parameters(item.get("parameters", {}))

                    result = self._process_action_request(
                        agent_id=agent_id,
                        action_id=action_request_id,
                        action=action_name,
                        params=params,
                        send_response=False,
                    )
                    success_flag = True
                    if isinstance(result, dict):
                        success_flag = result.get("success", True)
                    batch_results.append(
                        {
                            "id": action_request_id,
                            "action": action_name,
                            "response": result,
                            "success": success_flag,
                        }
                    )

                if agent_id:
                    batch_outcome = {
                        "results": batch_results,
                        "count": len(batch_results),
                    }
                    self.client.response_to_agent(
                        agent_id,
                        batch_id,
                        batch_outcome,
                        "json",
                    )
                return
            else:
                # Handle other message types
                print(f"[LLM SYSTEM] Handling other message type: {payload}")

        except Exception as e:
            print(f"[LLM SYSTEM] Error while handling message: {e}")
            if "sender" in locals():
                self.send_error_response(sender, f"Message processing error: {e}")
    
    def _enforce_message_cooldown(self, agent_id: Optional[str], message_id: Union[int, str]) -> bool:
        """Simple message-level cooldown: limits how often the same Agent can send messages, encouraging batching multiple actions into one message."""
        try:
            if not agent_id:
                return True
            now = time.time()
            last_ts = self._agent_last_message_ts.get(agent_id)
            if last_ts is not None:
                elapsed = now - last_ts
                if elapsed < self.message_cooldown_seconds:
                    remaining = max(0.0, self.message_cooldown_seconds - elapsed)
                    error_result = self._create_system_error_response(
                        "message",
                        (
                            f"Message frequency too high. Cooldown {self.message_cooldown_seconds:.2f}s; "
                            f"please batch multiple actions into one message. Retry in {remaining:.2f}s."
                        ),
                        2011,
                    )
                    print(
                        f"[LLMSystem] ⏱️ Message rejected due to cooldown: agent_id={agent_id}, remaining={remaining:.2f}s"
                    )
                    # Reply with message ID
                    self.client.response_to_agent(agent_id, message_id, error_result, "str")
                    # Unified count
                    # self._record_interaction(agent_id, None)
                    return False
            # Passed - record timestamp
            self._agent_last_message_ts[agent_id] = now
            return True
        except Exception as _e:
            print(f"[LLMSystem] Cooldown check error: {_e}")
            return True

    def on_connect(self, message):
        print("LLMSystem connected", message)

    def on_disconnect(self, message):
        print("LLMSystem disconnected", message)

    def on_error(self, error):
        print(f"LLMSystem error: {error}")

    # === WebSocket client methods ===

    def connect(self):
        """Connect to server - synchronous method"""
        return self.client.connect()

    def disconnect(self):
        """Disconnect - synchronous method"""
        return self.client.disconnect()

    def send_message(self, message, instruction=None, target=None):
        """Send message - synchronous method"""
        return self.client.send_message(
            instruction or MessageType.MESSAGE.value, message, target
        )

    def response_to_agent(
        self, agent_id: str, action_id: int, outcome: str, outcome_type: str = "str"
    ):
        """Execute action - synchronous interface"""
        return self.client.response_to_agent(agent_id, action_id, outcome, outcome_type)

    def _get_or_create_stats(self) -> GameStats:
        stats = self.world.get_singleton_component(GameStats)
        if stats is None:
            stats = GameStats()
            self.world.add_singleton_component(stats)
        return stats

    def _resolve_agent_faction(self, stats: GameStats, agent_id: Optional[str]) -> Optional[Faction]:
        if not agent_id:
            return None
        return stats.agent_id_to_faction.get(agent_id)

    def _record_action(self, agent_id: str | None, params: Dict[str, Any] | None) -> None:
        """Record one processed action (Agent -> ENV)."""
        try:
            stats = self._get_or_create_stats()

            if agent_id:
                stats.action_counts_by_agent[agent_id] = (
                    stats.action_counts_by_agent.get(agent_id, 0) + 1
                )

            mapped_faction = self._resolve_agent_faction(stats, agent_id)
            if mapped_faction:
                stats.action_counts_by_faction[mapped_faction] = (
                    stats.action_counts_by_faction.get(mapped_faction, 0) + 1
                )
            elif agent_id:
                raise ValueError(
                    f"[LLMSystem. _record_action] Missing faction mapping for agent {agent_id}. "
                    "Agents must call register_agent_info before issuing actions."
                )
        except Exception as _e:
            raise RuntimeError(f"[LLMSystem. _record_action] Record ENV <-> Agent action error: {_e}") from _e

    def _record_message(self, agent_id: Optional[str], _params: Dict[str, Any] | None) -> None:
        """Record one inbound message (Agent -> ENV interaction)."""
        try:
            stats = self._get_or_create_stats()

            if agent_id:
                stats.interaction_counts_by_agent[agent_id] = (
                    stats.interaction_counts_by_agent.get(agent_id, 0) + 1
                )

            mapped_faction = self._resolve_agent_faction(stats, agent_id)
            if mapped_faction:
                stats.interaction_counts_by_faction[mapped_faction] = (
                    stats.interaction_counts_by_faction.get(mapped_faction, 0) + 1
                )
            elif agent_id:
                raise ValueError(
                    f"[LLMSystem. _record_message] Missing faction mapping for agent {agent_id}. "
                    "Agents must register before sending messages."
                )
        except Exception as _e:
            raise RuntimeError(f"[LLMSystem. _record_message] Record Agent -> ENV message error: {_e}") from _e

    @staticmethod
    def _prepare_parameters(raw_params: Any) -> Dict[str, Any]:
        """Normalize parameters payload into a dictionary."""
        if isinstance(raw_params, dict):
            return raw_params
        if isinstance(raw_params, str):
            if raw_params == "":
                return {}
            try:
                return json.loads(raw_params)
            except Exception:
                print(f"Parse params error: {raw_params}")
                print("Use empty params instead.")
                return {}
        if raw_params is None:
            return {}
        # Fallback: attempt to cast to dict if possible
        try:
            return dict(raw_params)
        except Exception:
            return {}

    # === Strategy scoring: Agent-side ping ===
    def handle_strategy_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Receive a strategy thinking hit ping from the Agent side for scoring and rate limiting.

        Expected parameters:
          - faction: str (wei/shu/wu) Required
          - score: float (default 0.5, 0 < score ≤ 1.0)
          - evidence: str (optional, brief strategy summary)
        Limits:
          - Only one count per faction within the throttle interval (default 2 seconds)
          - Per-faction per-minute cap (default 6 pings = 3 points)
        """
        try:
            faction_key = params.get("faction")
            score = params.get("score", 0.5)
            evidence = params.get("evidence", None)

            if not faction_key:
                return {"success": False, "message": "Missing faction"}
            try:
                from ..prefabs.config import Faction as _Faction
                faction = _Faction(faction_key)
            except Exception:
                return {"success": False, "message": f"Invalid faction: {faction_key}"}

            # Validate score
            try:
                score = float(score)
            except Exception:
                return {"success": False, "message": "Invalid score"}
            if not (0.0 < score <= 1.0):
                return {"success": False, "message": "Score out of range (0, 1]"}

            # Get statistics component
            stats = self.world.get_singleton_component(GameStats)
            if stats is None:
                stats = GameStats()
                self.world.add_singleton_component(stats)

            import time as _time
            now = _time.time()

            # Rate limit: minimum interval per faction
            min_interval_sec = 2.0
            last_ts = stats.last_strategy_ping_ts.get(faction)
            if last_ts is not None and (now - last_ts) < min_interval_sec:
                return {"success": False, "message": "Strategy ping throttled"}

            # Per-minute cap
            per_minute_cap = 6  # count
            window_sec = 60.0
            # Simple: use ping_count and last_ts for rough control; reject if cap reached within the last minute
            count = stats.strategy_ping_count_by_faction.get(faction, 0)
            # Optional finer control: maintain a timestamp queue; kept simple for now
            if count >= per_minute_cap and last_ts and (now - last_ts) < window_sec:
                return {"success": False, "message": "Per-minute cap reached"}

            # Passed - accumulate score
            current_score = stats.strategy_scores_by_faction.get(faction, 0.0)
            stats.strategy_scores_by_faction[faction] = round(current_score + score, 4)

            # Update count and timestamp
            stats.strategy_ping_count_by_faction[faction] = count + 1
            stats.last_strategy_ping_ts[faction] = now

            # Record evidence (keep the most recent 10 entries)
            if evidence:
                ev_list = stats.strategy_evidence.get(faction, [])
                # Truncate evidence
                try:
                    evidence = str(evidence)
                    if len(evidence) > 120:
                        evidence = evidence[:117] + "..."
                except Exception:
                    evidence = "<invalid evidence>"
                ev_list.append(evidence)
                if len(ev_list) > 10:
                    ev_list = ev_list[-10:]
                stats.strategy_evidence[faction] = ev_list
            
            return {
                "success": True,
                "message": "Strategy score accepted",
                "new_score": stats.strategy_scores_by_faction[faction],
                "pings": stats.strategy_ping_count_by_faction[faction],
            }
        except Exception as e:
            return {"success": False, "message": f"Strategy ping failed: {e}"}

    def handle_report_llm_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report LLM API interaction statistics from Agent to ENV
        
        Expected parameters:
          - faction: str (wei/shu/wu) Required
          - api_stats: Dict - LLM API statistics data
            - total_calls: int - Total number of calls
            - successful_calls: int - Number of successful calls  
            - failed_calls: int - Number of failed calls
            - success_rate: float - Success rate
          - toolcall_error_total: int - Total tool call generation errors
          - http_error_total: int - Total HTTP errors
          - spatial_awareness_error: int - Spatial awareness errors (LLM capability)
          - provider: str - LLM provider
          - model_id: str - Model ID
        """
        try:
            faction_key = params.get("faction")
            api_stats = params.get("api_stats", {})
            toolcall_error_total = params.get("toolcall_error_total", 0)
            http_error_total = params.get("http_error_total", 0)
            spatial_awareness_error = params.get("spatial_awareness_error", 0)
            provider = params.get("provider", "unknown")
            model_id = params.get("model_id", "unknown")

            if not faction_key:
                return {"success": False, "message": "Missing faction"}
            
            try:
                from ..prefabs.config import Faction as _Faction
                faction = _Faction(faction_key)
            except Exception:
                return {"success": False, "message": f"Invalid faction: {faction_key}"}
            
            if not isinstance(api_stats, dict):
                return {"success": False, "message": "Invalid api_stats format"}
            
            # Get statistics component
            stats = self.world.get_singleton_component(GameStats)
            if stats is None:
                stats = GameStats()
                self.world.add_singleton_component(stats)
            
            # Reject stats from unregistered agents immediately
            try:
                from ..components.agent_info import AgentInfoRegistry
                registry = self.world.get_singleton_component(AgentInfoRegistry)
                if not registry or not registry.has_agent(faction_key):
                    return {"success": False, "message": "Agent not registered. Please register before reporting LLM stats."}
            except Exception:
                return {"success": False, "message": "Registration status unavailable"}

            # Ensure llm_api_stats field exists
            if not hasattr(stats, 'llm_api_stats'):
                stats.llm_api_stats = {}
            
            # Store LLM API statistics data
            stats.llm_api_stats[faction] = {
                "total_calls": api_stats.get("total_calls", 0),
                "successful_calls": api_stats.get("successful_calls", 0),
                "toolcall_error_total": toolcall_error_total,
                "http_error_total": http_error_total,
                "spatial_awareness_error": spatial_awareness_error,
                "failed_calls": api_stats.get("failed_calls", 0),
                "success_rate": api_stats.get("success_rate", 0.0),
                "provider": provider,
                "model_id": model_id,
                "timestamp": time.time()
            }
            
            print(f"[LLMSystem] ✅ Received LLM API stats for faction {faction_key}: {api_stats}")
            print(f"[LLMSystem] 📊 Error stats - HTTP errors: {http_error_total}, Tool-call errors: {toolcall_error_total}, spatial-awareness errors: {spatial_awareness_error}")

            # 🆕 基于集合的收齐判断
            try:
                stats.received_llm_stats_factions.add(faction)
                registered = stats.registered_factions if hasattr(stats, 'registered_factions') else set()
                received = stats.received_llm_stats_factions
                print(f"[LLMSystem] 📊 Stats progress: {len(received)}/{len(registered)} -> received={[f.value for f in received]}, registered={[f.value for f in registered]}")
                if not stats.can_generate_settlement_report and len(received) >= len(registered) and len(registered) > 0:
                    stats.can_generate_settlement_report = True
                    print(f"[LLMSystem] 🎯 All LLM stats received; settlement report generation flag set")
                # Sync count-based fields for backward compatibility
                stats.received_llm_stats_count = len(received)
                stats.expected_llm_stats_count = len(registered)
            except Exception as _e:
                print(f"[LLMSystem] ⚠️ Failed to update set-based stats progress: {_e}")
            
            return {
                "success": True,
                "message": "LLM stats received",
                "faction": faction_key,
                "stats": api_stats,
                "toolcall_error_total": toolcall_error_total,
                "http_error_total": http_error_total,
                "spatial_awareness_error": spatial_awareness_error
            }
            
        except Exception as e:
            return {"success": False, "message": f"Report LLM stats failed: {e}"}

    def handle_retrieve_game_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return system-level status information to the Agent (read-only, no game-state changes).

        Includes:
          - current turn number, current player faction, whether the game is running/paused/finished
          - winner (if any) and maximum number of turns
          - registered factions and number of connected agents
          - LLM statistics collection progress (received vs expected)
        """
        try:
            game_state = self.world.get_singleton_component(GameState)
            stats = self.world.get_singleton_component(GameStats)

            turn = getattr(game_state, "turn_number", None) if game_state else None
            current_player = (
                getattr(getattr(game_state, "current_player", None), "value", None)
                if game_state else None
            )

            registered = []
            if stats and hasattr(stats, 'registered_factions'):
                try:
                    registered = [f.value for f in stats.registered_factions]
                except Exception:
                    registered = []

            connected_agents = len(self.client.connected_agents) if hasattr(self, 'client') else 0

            payload = {
                "turn": turn,
                "current_player": current_player,
                "registered_factions": registered,
                "connected_agents": connected_agents,
                "timestamp": time.time()
            }

            return {
                "success": True,
                "message": "Game status reported",
                "data": payload
            }
        except Exception as e:
            return {"success": False, "message": f"Report game status failed: {e}"}

    def handle_register_agent_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Register agent information for a faction (provider/model/base_url/etc)."""
        try:
            # Validate required parameters
            required_params = ["faction", "provider", "model_id", "base_url"]
            for param in required_params:
                if param not in params:
                    return {
                        "success": False,
                        "result": False,
                        "message": f"Missing required parameter: {param}",
                        "details": f"Missing required parameter: {param}",
                    }

            faction = params["faction"]
            provider = params["provider"]
            model_id = params["model_id"]
            base_url = params["base_url"]
            # Optional features
            enable_thinking = params.get("enable_thinking", False)

            # Create AgentInfo
            from ..components.agent_info import AgentInfo, AgentInfoRegistry

            agent_info = AgentInfo(
                provider=provider,
                model_id=model_id,
                base_url=AgentInfoRegistry.sanitize_url(base_url),
                agent_id=params.get("agent_id"),
                version=params.get("version"),
                note=params.get("note"),
                # pass through optional thinking flag
                enable_thinking=enable_thinking,
            )

            # Get or create registry
            registry = self.world.get_singleton_component(AgentInfoRegistry)
            if not registry:
                registry = AgentInfoRegistry()
                self.world.add_singleton_component(registry)

            # Register
            success = registry.register_agent(faction, agent_info)

            # Maintain registered_factions set in GameStats
            try:
                from ..components.state import GameStats

                stats = self.world.get_singleton_component(GameStats)
                if stats is None:
                    stats = GameStats()
                    self.world.add_singleton_component(stats)
                from ..prefabs.config import Faction as _Faction

                reg_faction = _Faction(faction)
                stats.registered_factions.add(reg_faction)
            except Exception as _e:
                print(
                    f"[LLMActionHandlerV3] ⚠️ Failed to update registered_factions after registration: {_e}"
                )

            if success:
                return {
                    "success": True,
                    "result": True,
                    "details": f"Agent info registered for faction: {faction}",
                    "message": f"Agent info registered for faction: {faction}",
                    "registered_info": {
                        "faction": faction,
                        "provider": provider,
                        "model_id": model_id,
                        "base_url_sanitized": agent_info.base_url,
                        # include thinking flag in response
                        "enable_thinking": enable_thinking,
                    },
                }
            else:
                return {
                    "success": False,
                    "result": False,
                    "message": "Failed to register agent info",
                    "details": "Failed to register agent info",
                }

        except Exception as e:
            return {
                "success": False,
                "result": False,
                "details": f"Error registering agent info: {str(e)}",
                "message": f"Error registering agent info: {str(e)}",
            }

    def send_error_response(self, sender: Dict[str, Any], error_message: str):
        """Send an error response to the originating agent (if any)."""
        agent_id = sender.get("id") if sender.get("type") == "agent" else None
        if agent_id:
            error_response = {
                "success": False,
                "error": error_message,
                "timestamp": time.time(),
            }
            self.send_message(error_response, target={"type": "agent", "id": agent_id})
            # Unified place for interaction counting: explicit error responses could also be counted here.
            # self._record_interaction(agent_id, None)

    def notify_game_end_to_all_agents(self, winner: Optional[Faction] = None, reason: str = "game_completed"):
        """Send a game-end notification to all connected agents."""
        try:
            game_end_notification = {
                "type": "game_end_notification",
                "winner": winner.value if winner else None,
                "reason": reason,
                "timestamp": time.time(),
                "message": "Game has ended. Please report your LLM statistics."
            }
            
            # Set expected number of LLM stats (prefer registered factions over raw connection count).
            stats = self.world.get_singleton_component(GameStats)
            if stats:
                try:
                    registered_count = len(getattr(stats, 'registered_factions', set()))
                except Exception:
                    registered_count = 0
                connected_count = len(self.client.connected_agents)
                expected = registered_count if registered_count > 0 else connected_count
                # Sync set-based tracking to count-based fields for backward compatibility.
                stats.expected_llm_stats_count = expected
                stats.received_llm_stats_count = len(getattr(stats, 'received_llm_stats_factions', set())) if registered_count > 0 else 0
                print(f"[LLMSystem] ℹ️ Expected stats={expected} (registered={registered_count}, connected={connected_count})")

                # If nothing is expected, allow report generation immediately.
                if expected == 0:
                    stats.can_generate_settlement_report = True
                    raise Exception("[LLMSystem] ⚠️ No stats expected; allowing settlement report generation directly")


            # Only notify agents mapped to registered factions.
            agent_count = 0
            try:
                stats = self.world.get_singleton_component(GameStats)
                registered = getattr(stats, 'registered_factions', set()) if stats else set()
                id_to_faction = getattr(stats, 'agent_id_to_faction', {}) if stats else {}

                # Filter via mapping: only notify agents whose faction is in the registered set.
                for agent_id, agent_info in self.client.connected_agents.items():
                    mapped_faction = id_to_faction.get(agent_id)
                    if mapped_faction not in registered:
                        print(f"[LLMSystem] ⏭️ Skipping agent not mapped to a registered faction: {agent_id}")
                        continue
                    try:
                        self.send_message(
                            game_end_notification,
                            target={"type": "agent", "id": agent_id}
                        )
                        agent_count += 1
                        print(f"[LLMSystem] ✅ Sent game-end notification to agent {agent_id} (faction={mapped_faction.value})")
                    except Exception as e:
                        print(f"[LLMSystem] ❌ Failed to send game-end notification to agent {agent_id}: {e}")

                print(f"[LLMSystem] 📢 Game-end notification sent to {agent_count} registered agents (registered={[f.value for f in registered]})")
            except Exception as _e:
                print(f"[LLMSystem] ⚠️ Failed to filter registered agents for notification; falling back to no notifications: {_e}")
                agent_count = 0
            return agent_count
            
        except Exception as e:
            print(f"[LLMSystem] ❌ Error while sending game-end notifications: {e}")
            return 0

    def subscribe_events(self):
        return super().subscribe_events()

    def update(self, dt):
        # Check whether the game has ended; if so and not yet notified, send game-end notification.
        if not self.game_end_notified:
            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.game_over:
                print("[LLMSystem] 🏁 Game over detected, sending game-end notifications to all agents")
                agent_count = self.notify_game_end_to_all_agents(
                    winner=game_state.winner,
                    reason="game_completed"
                )
                self.game_end_notified = True
                self._pending_turn_start_ack.clear()
                print(f"[LLMSystem] ✅ Game-end notifications completed; {agent_count} agents notified")

        # Reliable turn_start delivery: if ACK not received by deadline, retry until max retries reached.
        game_state = self.world.get_singleton_component(GameState) if self.world else None
        if game_state and not getattr(game_state, "game_over", False):
            now = time.time()
            for agent_id in list(self._pending_turn_start_ack.keys()):
                entry = self._pending_turn_start_ack.get(agent_id)
                if not entry or now < entry.get("next_retry_time", 0):
                    continue
                entry["retry_count"] = entry.get("retry_count", 0) + 1
                if entry["retry_count"] > self._turn_start_max_retries:
                    print(f"[LLMSystem] ⚠️ Giving up on resending turn_start to {agent_id} after {self._turn_start_max_retries} retries")
                    self._pending_turn_start_ack.pop(agent_id, None)
                    continue
                try:
                    self.send_message(
                        entry["notification"],
                        target={"type": "agent", "id": agent_id},
                    )
                    entry["next_retry_time"] = now + self._turn_start_retry_interval
                    print(f"[LLMSystem] 🔄 Resending turn_start to {agent_id} (retry {entry['retry_count']})")
                except Exception as _e:
                    print(f"[LLMSystem] ❌ Failed to resend turn_start to {agent_id}: {_e}")
        
        # Legacy interactive console code kept for reference:
        # print(f"LLMSystem update: {dt}")
        # with patch_stdout():
        #     command = self.session.prompt("💬 Enter command (type 'quit' to exit): ", completer=None, complete_while_typing=True)
        pass

    # === ENV 方法 ===
    def _process_action_request(
        self,
        agent_id: Optional[str],
        action_id: Union[int, str],
        action: Optional[str],
        params: Dict[str, Any],
        *,
        send_response: bool,
    ) -> Dict[str, Any]:
        """Core routine to validate, execute and optionally respond to an action."""
        start_time = time.time()
        standardized_result: Dict[str, Any] | None = None

        stats = self.world.get_singleton_component(GameStats)
        if stats is None:
            stats = GameStats()
            self.world.add_singleton_component(stats)
        if not hasattr(stats, "agent_id_to_faction"):
            stats.agent_id_to_faction = {}
        if not hasattr(stats, "registered_factions"):
            stats.registered_factions = set()

        if not action:
            error_result = self._create_system_error_response(
                "unknown", "Missing action name", 2007
            )
            if send_response and agent_id:
                self.client.response_to_agent(agent_id, action_id, error_result, "str")
            return error_result

        # 🆕 turn_start 可靠投递：Agent 收到 turn_start 后发 ACK，ENV 清除重发等待
        if action == "turn_start_ack":
            self._pending_turn_start_ack.pop(agent_id, None)
            if send_response and agent_id:
                self.client.response_to_agent(agent_id, action_id, {"success": True}, "str")
            return {"success": True}

        try:
            # 收到该 agent 的任意业务 action 视为已活跃，清除其 turn_start 重发等待
            self._pending_turn_start_ack.pop(agent_id, None)
            if action != "register_agent_info":
                mapped_faction = stats.agent_id_to_faction.get(agent_id) if agent_id else None
                if mapped_faction is None:
                    error_result = self._create_system_error_response(
                        action,
                        "Agent not registered. Please call register_agent_info first.",
                        2005,
                    )
                    print(
                        f"[LLMSystem] ❌ Action rejected due to unregistered Agent_ID: action={action}, agent_id={agent_id}"
                    )
                    if send_response and agent_id:
                        self.client.response_to_agent(agent_id, action_id, error_result, "str")
                    return error_result

                if isinstance(params, dict) and "faction" in params:
                    if action == "get_faction_state":
                        try:
                            from ..prefabs.config import Faction as _Faction

                            reported_faction = _Faction(params["faction"])
                            if mapped_faction != reported_faction:
                                print(
                                    f"[LLMSystem] ℹ️ Intelligence gathering: agent_id={agent_id} (registered={mapped_faction.value}) queries {reported_faction.value} faction info"
                                )
                        except Exception as _e:
                            print(
                                f"[LLMSystem] ⚠️ Faction parsing failed in get_faction_state: {_e}"
                            )
                    else:
                        try:
                            from ..prefabs.config import Faction as _Faction

                            reported_faction = _Faction(params["faction"])
                            if mapped_faction != reported_faction:
                                error_result = self._create_system_error_response(
                                    action,
                                    (
                                        f"Agent {agent_id} is registered to {mapped_faction.value} faction, "
                                        f"but action specifies {reported_faction.value}. "
                                        "Please use your registered faction or re-register."
                                    ),
                                    2005,
                                )
                                print(
                                    f"[LLMSystem] ❌ Action rejected due to faction mismatch: action={action}, agent_id={agent_id}, registered={mapped_faction.value}, reported={reported_faction.value}"
                                )
                                if send_response and agent_id:
                                    self.client.response_to_agent(
                                        agent_id, action_id, error_result, "str"
                                    )
                                return error_result
                        except Exception as _e:
                            print(f"[LLMSystem] ⚠️ Faction consistency check failed: {_e}")

            request = ActionRequest(
                agent_id=agent_id,
                action_id=action_id,
                action_name=action,
                parameters=params,
                timestamp=start_time,
            )

            result = self.action_executor.execute(request)
            standardized_result = result

            if action == "end_turn" and isinstance(result, dict) and result.get("success"):
                try:
                    game_state = self.world.get_singleton_component(GameState)
                    if game_state:
                        current_faction = getattr(game_state, "current_player", None)
                        if current_faction is not None:
                            faction_key = (
                                current_faction.value
                                if hasattr(current_faction, "value")
                                else str(current_faction)
                            )

                            # 收集目标 agent_id 列表
                            target_agent_ids = set()

                            # 1) 从注册表获取（可能只有一个）
                            try:
                                from ..components.agent_info import AgentInfoRegistry

                                registry = self.world.get_singleton_component(AgentInfoRegistry)
                                if registry:
                                    agent_info = registry.get_agent_info(faction_key)
                                    if agent_info and getattr(agent_info, "agent_id", None):
                                        target_agent_ids.add(agent_info.agent_id)
                            except Exception as _e:
                                print(f"[LLMSystem] 获取AgentInfoRegistry失败: {_e}")

                            # 2) 通过统计映射收集所有注册到该阵营的 agent_id
                            if stats and getattr(stats, "agent_id_to_faction", None):
                                try:
                                    for mapped_agent_id, mapped_faction in (
                                        stats.agent_id_to_faction.items()
                                    ):
                                        if mapped_faction == current_faction:
                                            target_agent_ids.add(mapped_agent_id)
                                except Exception as _e:
                                    print(f"[LLMSystem] 通过统计映射查找agent_id失败: {_e}")

                            # 仅向当前已连接的 agent 发送
                            connected_ids = set(self.client.connected_agents.keys())
                            target_agent_ids = [
                                aid for aid in target_agent_ids if aid in connected_ids
                            ]

                            if target_agent_ids:
                                turn_number = getattr(game_state, "turn_number", None)
                                notification = {
                                    "type": "turn_start",
                                    "faction": faction_key,
                                    "turn_number": turn_number,
                                    "timestamp": time.time(),
                                    "message": "Your turn starts.",
                                }
                                now = time.time()
                                for target_agent_id in target_agent_ids:
                                    try:
                                        self.send_message(
                                            notification,
                                            target={"type": "agent", "id": target_agent_id},
                                        )
                                        # 可靠投递：等待 ACK 或按间隔重发，直至收到 ack/任意 action 或超过最大重试
                                        self._pending_turn_start_ack[target_agent_id] = {
                                            "turn_number": turn_number,
                                            "faction_key": faction_key,
                                            "next_retry_time": now + self._turn_start_retry_interval,
                                            "retry_count": 0,
                                            "notification": notification,
                                        }
                                        print(
                                            f"[LLMSystem] ✅ 已通知 {faction_key} 阵营 (agent_id={target_agent_id}) 开始新回合"
                                        )
                                    except Exception as _e:
                                        print(f"[LLMSystem] ❌ 发送回合开始通知失败: {_e}")
                            else:
                                print(f"[LLMSystem] ⚠️ 未找到阵营 {faction_key} 的在线 agent_id，跳过通知")
                except Exception as _e:
                    print(f"[LLMSystem] ⚠️ end_turn 后通知当前玩家失败: {_e}")

            if (
                action == "register_agent_info"
                and isinstance(result, dict)
                and result.get("success")
            ):
                try:
                    reg_faction_key = params.get("faction")
                    if reg_faction_key:
                        from ..prefabs.config import Faction as _Faction

                        reg_faction = _Faction(reg_faction_key)
                        if agent_id:
                            stats.agent_id_to_faction[agent_id] = reg_faction
                        stats.registered_factions.add(reg_faction)
                        stats.expected_llm_stats_count = len(stats.registered_factions)
                        print(
                            f"[LLMSystem] 📝 已注册阵营集合: {[f.value for f in stats.registered_factions]} (期望统计数={stats.expected_llm_stats_count})"
                        )
                except Exception as _e:
                    print(f"[LLMSystem] ⚠️ 注册后维护集合失败: {_e}")

            # print(f"{action} response: {standardized_result}")
            if send_response and agent_id:
                self.client.response_to_agent(
                    agent_id, action_id, standardized_result, "str"
                )

            # Count action
            self._record_action(agent_id, params)

            return standardized_result
        except Exception as e:
            print(f"[LLMSystem] Error while executing action {action}: {e}")
            error_result = self._create_system_error_response(action, str(e), 2010)
            if send_response and agent_id:
                try:
                    self.client.response_to_agent(agent_id, action_id, error_result, "str")
                except Exception as response_error:
                    print(f"[LLMSystem] Failed to send error response: {response_error}")
            return error_result

    def exec_action(self, message):
        """Intelligently delegate and execute an action – unified entry point."""
        sender = message.get("sender", {})
        payload = message.get("payload", {})

        agent_id = sender.get("id") if sender.get("type") == "agent" else None
        action_id = payload.get("id") or int(time.time() * 1e9)
        action = payload.get("action")
        params = self._prepare_parameters(payload.get("parameters", {}))

        self._process_action_request(
            agent_id=agent_id,
            action_id=action_id,
            action=action,
            params=params,
            send_response=True,
        )

    def _is_observation_action(self, action: str) -> bool:
        """Return True if the given action is an observation-related action."""
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
        """Route observation actions to the appropriate handler."""
        # For known observation actions, route to specific handlers.
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
            # Generic observation action: delegate directly to the observation_system.
            return self.observation_system.get_observation_by_action(action, params)

    def _standardize_response(
        self, result: Dict, action: str, params: Dict, execution_time: float
    ) -> Dict:
        """Normalize/standardize the response format."""
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
            # Successful response: merge payload fields.
            base_response.update({k: v for k, v in result.items() if k != "success"})
        else:
            # Error response: attach error metadata.
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
        """Create a standardized system-level error response."""
        return {
            "success": False,
            "error": self.system_error_codes.get(error_code, "Unknown system error"),
            "error_code": error_code,
            "message": f"Action {action} failed: {error_message}",
            "api_version": "v1.0",
            "metadata": {"action": action, "timestamp": time.time()},
        }

    # ==================== System-level control methods ====================

    # === Game lifecycle control ===
    def handle_start_game(self, params: Dict) -> Dict:
        """Start the game."""
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
        """Pause the game."""
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
        """Resume the game."""
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
        """Reset the game state to its initial configuration."""
        try:
            # 重置游戏状态
            game_state = self.world.get_singleton_component(GameState)
            if game_state:
                game_state.game_over = False
                game_state.paused = False
                game_state.turn_number = 1
                game_state.winner = None
                game_state.current_player = Faction.WEI  # Default starting faction: WEI

            return {"success": True, "message": "Game reset successfully"}
        except Exception as e:
            return {
                "success": False,
                "error_code": 2010,
                "message": f"Failed to reset game: {str(e)}",
            }

    def handle_save_game(self, params: Dict) -> Dict:
        """Persist the current game state (not yet implemented)."""
        # TODO: Implement game save logic
        return {
            "success": False,
            "error_code": 2004,
            "message": "Save game not implemented yet",
        }

    def handle_load_game(self, params: Dict) -> Dict:
        """Load a previously saved game (not yet implemented)."""
        # TODO: Implement game load logic
        return {
            "success": False,
            "error_code": 2004,
            "message": "Load game not implemented yet",
        }

    # === Turn and time management ===
    def handle_end_turn(self, params: Dict) -> Dict:
        """End the current turn."""
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
        """Skip the current turn for a specific faction (logical placeholder)."""
        faction_str = params.get("faction")
        if not faction_str:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing faction parameter",
            }

        try:
            faction = Faction(faction_str)
            # TODO: Implement logic to actually skip the specified faction's turn.
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
        """Force the game to advance to the next turn."""
        target_faction = params.get("target_faction")
        turn_system = self._get_turn_system()

        if turn_system:
            try:
                # If a target faction is specified, keep advancing until that faction becomes current.
                if target_faction:
                    target = Faction(target_faction)
                    game_state = self.world.get_singleton_component(GameState)
                    while game_state and game_state.current_player != target:
                        turn_system.end_turn()
                else:
                    # Otherwise, advance by a single turn.
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
        """Advance in-game time by a given number of seconds (simplified)."""
        seconds = params.get("seconds", 1.0)
        game_time_system = self._get_game_time_system()

        if game_time_system:
            try:
                game_time_system.advance_turn()  # Simplified implementation
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
        """Configure the turn timer duration (not fully implemented)."""
        duration = params.get("duration", 30.0)
        # TODO: Implement actual turn-timer wiring to the TurnSystem.
        return {"success": True, "message": f"Turn timer set to {duration} seconds"}

    # === Game mode control ===
    def handle_set_game_mode(self, params: Dict) -> Dict:
        """Set the game mode (e.g., turn-based vs real-time)."""
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
                # Create game mode component if missing.
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
        """Set the global time scale for the game."""
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
        """Set the maximum allowed number of turns."""
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

    # === Camera, view, and UI control ===
    def handle_set_view_faction(self, params: Dict) -> Dict:
        """Set which faction the UI is currently observing."""
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
                # Create UIState component if missing.
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
        """Set the camera position (world offset)."""
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
        """Toggle god mode (omniscient view)."""
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
        """Toggle the fog-of-war visualization."""
        enabled = params.get("enabled")
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if fog_of_war:
            if enabled is not None:
                # If explicit enabled state is provided, apply it directly.
                fog_enabled = bool(enabled)
            else:
                # Otherwise toggle the current state.
                fog_enabled = not getattr(fog_of_war, "enabled", True)

            # TODO: Wire fog_enabled into the actual FogOfWar logic.
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
        """Show a specific UI panel."""
        panel_name = params.get("panel")
        if not panel_name:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing panel parameter",
            }

        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            # Set visibility based on the requested panel.
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
        """Hide a specific UI panel."""
        panel_name = params.get("panel")
        if not panel_name:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing panel parameter",
            }

        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            # Set visibility to hidden based on the requested panel.
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
        """Toggle the grid overlay display."""
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

    # === Selection and grouping control ===
    def handle_select_unit(self, params: Dict) -> Dict:
        """Select a single unit by ID."""
        unit_id = params.get("unit_id")
        if not unit_id:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_id parameter",
            }

        # Delegate real selection logic to ActionHandler.
        return self.action_handler.execute_action("select_unit", params)

    def handle_select_multiple_units(self, params: Dict) -> Dict:
        """Select multiple units by ID (placeholder implementation)."""
        unit_ids = params.get("unit_ids", [])
        if not unit_ids:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_ids parameter",
            }

        # TODO: Implement multi-selection logic.
        return {
            "success": True,
            "message": f"Selected {len(unit_ids)} units",
            "selected_units": unit_ids,
        }

    def handle_deselect_units(self, params: Dict) -> Dict:
        """Deselect all currently selected units (placeholder)."""
        # TODO: Implement actual deselection logic.
        return {"success": True, "message": "Units deselected"}

    def handle_group_units(self, params: Dict) -> Dict:
        """Assign selected units to a logical control group (placeholder)."""
        unit_ids = params.get("unit_ids", [])
        group_id = params.get("group_id", 1)

        if not unit_ids:
            return {
                "success": False,
                "error_code": 2007,
                "message": "Missing unit_ids parameter",
            }

        # TODO: Implement persistent unit grouping logic.
        return {
            "success": True,
            "message": f"Grouped {len(unit_ids)} units into group {group_id}",
        }

    # === System information and diagnostics ===
    def handle_get_system_status(self, params: Dict) -> Dict:
        """Return high-level system status."""
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
        """Return a capability matrix for this system."""
        capabilities = {
            "game_control": True,
            "unit_control": True,
            "observation": True,
            "real_time": False,  # Currently only turn-based is supported
            "multiplayer": True,
            "save_load": False,  # Not yet implemented
            "ai_integration": True,
            "error_recovery": True,
        }

        return {
            "success": True,
            "message": "System capabilities retrieved",
            "data": capabilities,
        }

    def handle_get_performance_info(self, params: Dict) -> Dict:
        """Return basic performance information (placeholder)."""
        # TODO: Implement real performance monitoring.
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
        """Validate core invariants of the current game state."""
        try:
            game_state = self.world.get_singleton_component(GameState)
            if not game_state:
                return {
                    "success": False,
                    "error_code": 2001,
                    "message": "Game state not found",
                }

            # Basic validation checks.
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
        """Return aggregated game statistics (placeholder)."""
        # TODO: Implement real game statistics collection.
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

    # === Observation handling methods ===

    def handle_observation(self, params: Dict) -> Dict[str, Any]:
        """Handle a generic observation request."""
        observation_level = params.get("observation_level", ObservationLevel.FACTION)
        faction = params.get("faction")
        unit_id = params.get("unit_id")
        include_hidden = params.get("include_hidden", False)

        # Convert string faction to Faction enum if necessary.
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
