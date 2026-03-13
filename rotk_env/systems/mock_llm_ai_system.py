"""
Mock LLM AI system - uses rule-based AI logic but executes actions via the LLM Action Handler V3 API.

It does not call a real LLM; instead it generates API action commands using heuristic rules.
"""

import random
import time
from typing import Set, List, Tuple, Optional, Dict, Any
from framework import System, World
from ..components import (
    Player,
    AIControlled,
    Unit,
    HexPosition,
    MovementPoints,
    Combat,
    UnitCount,
    UnitStatus,
    GameState,
    MapData,
    Terrain,
    GameModeComponent,
    ActionPoints,
)
from ..prefabs.config import GameConfig, TerrainType, ActionType, Faction
from ..utils.hex_utils import HexMath, PathFinding
from .llm_action_handler_v3 import LLMActionHandlerV3


class MockLLMAISystem(System):
    """Mock LLM AI system using the LLM Action Handler V3 API."""

    def __init__(self):
        super().__init__(required_components={Player, AIControlled})
        self.decision_timer = 0.0
        self.decision_interval = 2.0  # AI decision interval (seconds)
        self.unit_last_action = {}  # Unit -> last action timestamp
        self.llm_handler = None  # LLM Action Handler instance
        self.ai_memory = {}  # AI memory: previous decisions/results
        self.failed_actions = {}  # Failed actions to avoid repeats

    def initialize(self, world: World) -> None:
        """Initialize the mock LLM AI system."""
        self.world = world
        # Create LLM Action Handler instance
        self.llm_handler = LLMActionHandlerV3(world)
        print("Mock LLM AI System initialized with LLM Action Handler V3")

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update the mock LLM AI system."""
        game_state = self.world.get_singleton_component(GameState)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not game_state or game_state.game_over or game_state.paused:
            return

        # Determine game mode
        is_realtime = game_mode and game_mode.is_real_time()

        self.decision_timer += delta_time

        if self.decision_timer >= self.decision_interval:
            if is_realtime:
                # Real-time: all AI players act concurrently
                self._make_realtime_ai_decisions()
            else:
                # Turn-based: only the current player acts
                current_player = self._get_current_player()
                if current_player:
                    ai_controlled = self.world.get_component(
                        current_player, AIControlled
                    )
                    if ai_controlled:
                        self._execute_ai_turn(current_player, is_realtime=False)

            self.decision_timer = 0.0

    def _make_realtime_ai_decisions(self):
        """Real-time AI decision logic."""
        # Collect AI players
        ai_players = []
        for entity in self.world.query().with_all(Player, AIControlled).entities():
            ai_players.append(entity)

        # Execute decisions per AI player
        for player_entity in ai_players:
            self._execute_ai_turn(player_entity, is_realtime=True)

    def _get_current_player(self) -> Optional[int]:
        """Get current player entity id."""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return None

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == game_state.current_player:
                return entity
        return None

    def _execute_ai_turn(self, player_entity: int, is_realtime: bool = False):
        """Execute an AI turn via the LLM Action Handler V3."""
        player = self.world.get_component(player_entity, Player)
        if not player:
            return

        print(
            f"\n=== Mock LLM AI Turn: {player.faction.value} ({'realtime' if is_realtime else 'turn-based'}) ==="
        )

        # Clean up expired failure records (>30s)
        self._cleanup_old_failed_actions()

        # Check victory conditions
        if self._check_victory_conditions():
            return  # Game already ended

        # 1) Get faction state
        faction_state = self._get_faction_state(player.faction)
        if not faction_state.get("success"):
            print(f"❌ Failed to get faction state: {faction_state.get('message')}")
            if not is_realtime:  # End turn only in turn-based mode
                self._end_turn(player.faction)
            return

        alive_units = faction_state.get("alive_units", 0)
        actionable_units = faction_state.get("actionable_units", 0)

        print(
            f"📊 Faction State: {alive_units} alive units, {actionable_units} actionable units"
        )

        if actionable_units == 0:
            print(f"⏭️ No actionable units")

            # If no units are alive, trigger defeat.
            if alive_units == 0:
                print(f"💀 {player.faction.value} has no surviving units - defeat!")
                self._trigger_game_over(player.faction, "defeat")
                return

            if not is_realtime:  # End turn only in turn-based mode
                print(f"⏭️ Ending turn")
                self._end_turn(player.faction)
            return

        # 2) Plan and execute actions per unit
        units_info = faction_state.get("units", [])
        actions_executed = 0
        max_actions_per_turn = 3 if is_realtime else 5  # Fewer actions in real-time mode

        for unit_info in units_info:
            if actions_executed >= max_actions_per_turn:
                break

            unit_id = unit_info.get("unit_id")
            if not unit_id:
                continue

            # Per-unit cooldown in real-time mode
            if is_realtime:
                current_time = time.time()
                last_action_time = self.unit_last_action.get(unit_id, 0)
                if current_time - last_action_time < 1.0:  # 1s cooldown
                    continue

            # Execute unit strategy
            action_taken = self._execute_unit_strategy(
                unit_id, unit_info, player.faction, is_realtime
            )
            if action_taken:
                actions_executed += 1
                if is_realtime:
                    self.unit_last_action[unit_id] = time.time()
                else:
                    time.sleep(0.3)  # Turn-based delay for clearer visuals

        # 3) End-of-turn handling
        print(f"✅ {player.faction.value} executed {actions_executed} actions")

        if not is_realtime:  # End turn only in turn-based mode
            print(f"⏭️ Ending turn")
            self._end_turn(player.faction)
        else:
            print(f"🔄 Continuing in realtime mode")

    def _get_faction_state(self, faction: Faction) -> Dict[str, Any]:
        """Get faction state via the LLM Action Handler."""
        return self.llm_handler.handle_faction_state({"faction": faction.value})

    def _execute_unit_strategy(
        self,
        unit_id: int,
        unit_info: Dict[str, Any],
        faction: Faction,
        is_realtime: bool = False,
    ) -> bool:
        """Execute strategy for a unit via the LLM Action Handler V3."""

        capabilities = unit_info.get("capabilities", {})
        unit_resources = capabilities.get("unit_resources", {})
        properties = capabilities.get("properties", {})
        position = unit_info.get("position", {})
        unit_status = unit_info.get("unit_status", {})

        action_points = unit_resources.get("action_points", 0)
        movement_points = unit_resources.get("movement_points", 0)
        health_percentage = unit_status.get("health_percentage", 0)

        print(
            f"🤖 Processing unit {unit_id}: AP={action_points}, MP={movement_points}, HP={health_percentage:.1f}%"
        )

        # Check whether the unit can act
        if action_points <= 0:
            print(f"  ⏸️ Unit {unit_id} has no action points")
            return False

        if health_percentage <= 10:
            print(f"  💀 Unit {unit_id} is too weak to act ({health_percentage:.1f}%)")
            return False

        # Get unit observation
        observation = self._get_unit_observation(unit_id)
        if not observation.get("success"):
            print(f"  ❌ Failed to get observation for unit {unit_id}")
            return False

        visible_environment = observation.get("visible_environment", [])

        # Analyze surroundings: enemies and opportunities
        enemy_targets = []
        strategic_positions = []

        for tile in visible_environment:
            tile_units = tile.get("units", [])
            tile_position = tile.get("position", {})
            terrain = tile.get("terrain", "plain")

            for tile_unit in tile_units:
                if tile_unit.get("faction") != faction.value:
                    enemy_targets.append(
                        {
                            "unit_id": tile_unit.get("unit_id"),
                            "position": tile_position,
                            "unit_type": tile_unit.get("unit_type"),
                            "faction": tile_unit.get("faction"),
                        }
                    )

            # Collect strategic positions (city/hill/mountain)
            if terrain in ["city", "hill", "mountain"]:
                strategic_positions.append(
                    {
                        "position": tile_position,
                        "terrain": terrain,
                        "territory_control": tile.get("territory_control", {}),
                    }
                )

        # Decide strategy
        strategy_result = self._decide_strategy(
            unit_id,
            position,
            enemy_targets,
            strategic_positions,
            action_points,
            movement_points,
            properties,
        )

        return self._execute_strategy(strategy_result, faction)

    def _get_unit_observation(self, unit_id: int) -> Dict[str, Any]:
        """Get unit observation."""
        return self.llm_handler.handle_observation_action(
            {"unit_id": unit_id, "observation_level": "detailed"}
        )

    def _decide_strategy(
        self,
        unit_id: int,
        position: Dict[str, Any],
        enemy_targets: List[Dict],
        strategic_positions: List[Dict],
        action_points: int,
        movement_points: int,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Decide strategy (simulated LLM-style reasoning)."""

        current_pos = (position.get("col", 0), position.get("row", 0))
        attack_range = properties.get("attack_range", 1)

        print(f"  🧠 Analyzing strategy for unit {unit_id} at {current_pos}")
        print(
            f"     Found {len(enemy_targets)} enemies, {len(strategic_positions)} strategic positions"
        )

        # Priority 1: attack if an enemy is in range
        for enemy in enemy_targets:
            enemy_pos = (
                enemy["position"].get("col", 0),
                enemy["position"].get("row", 0),
            )
            distance = HexMath.hex_distance(current_pos, enemy_pos)

            if distance <= attack_range and action_points >= 1:
                print(
                    f"     ⚔️ Enemy {enemy['unit_id']} in attack range (distance: {distance})"
                )
                return {
                    "action": "attack",
                    "params": {"unit_id": unit_id, "target_id": enemy["unit_id"]},
                    "reason": f"Attack enemy {enemy['unit_type']} at distance {distance}",
                }

        # Priority 2: move closer to the nearest enemy
        if enemy_targets and movement_points > 0:
            nearest_enemy = min(
                enemy_targets,
                key=lambda e: HexMath.hex_distance(
                    current_pos,
                    (e["position"].get("col", 0), e["position"].get("row", 0)),
                ),
            )

            enemy_pos = (
                nearest_enemy["position"].get("col", 0),
                nearest_enemy["position"].get("row", 0),
            )
            distance = HexMath.hex_distance(current_pos, enemy_pos)

            if distance > attack_range:
                # Compute a move target (towards enemy)
                target_pos = self._calculate_move_towards_enemy(
                    current_pos, enemy_pos, movement_points
                )

                if target_pos and target_pos != current_pos:
                    print(
                        f"     🏃 Moving towards enemy {nearest_enemy['unit_id']} at {enemy_pos}"
                    )
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Move towards enemy {nearest_enemy['unit_type']} (distance: {distance})",
                    }

        # Priority 3: occupy strategic positions
        if strategic_positions and action_points >= 1:
            # Get the unit's current faction
            unit_obj = self.world.get_component(unit_id, Unit)
            current_faction = unit_obj.faction.value if unit_obj else None

            for strategic_pos in strategic_positions:
                pos = strategic_pos["position"]
                target_pos = (pos.get("col", 0), pos.get("row", 0))
                distance = HexMath.hex_distance(current_pos, target_pos)

                # If at or adjacent to the target, try to occupy
                if distance <= 1:
                    territory_control = strategic_pos.get("territory_control", {})
                    controlled_by = territory_control.get("controlled_by")

                    # Skip if we previously failed to occupy this position
                    action_key = f"occupy_{target_pos[0]}_{target_pos[1]}"
                    if (
                        unit_id in self.failed_actions
                        and action_key in self.failed_actions[unit_id]
                    ):
                        continue  # Skip previously failed actions

                    # Only attempt occupy if not controlled by our faction
                    if controlled_by != current_faction:
                        print(f"     🏰 Occupying strategic position {target_pos}")
                        return {
                            "action": "occupy",
                            "params": {
                                "unit_id": unit_id,
                                "position": {
                                    "col": target_pos[0],
                                    "row": target_pos[1],
                                },
                            },
                            "reason": f"Occupy strategic {strategic_pos['terrain']} position",
                        }

        # Priority 4: if no enemies, explore towards the map center or other areas
        if not enemy_targets and movement_points > 0:
            # Collect occupied positions to avoid collisions
            occupied_positions = set()
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                pos = self.world.get_component(entity, HexPosition)
                if pos:
                    occupied_positions.add((pos.col, pos.row))

            # Candidate exploration targets (choose an unoccupied one)
            potential_targets = [
                (0, 0),  # map center
                (2, 2),  # upper-right
                (-2, -2),  # lower-left
                (3, 0),  # right
                (-3, 0),  # left
                (0, 3),  # up
                (0, -3),  # down
            ]

            # Choose the nearest unoccupied target (with a minimum distance)
            best_target = None
            min_distance = float("inf")

            for target in potential_targets:
                if target not in occupied_positions:
                    distance = HexMath.hex_distance(current_pos, target)
                    if (
                        distance > 2 and distance < min_distance
                    ):
                        min_distance = distance
                        best_target = target

            if best_target:
                target_pos = self._calculate_move_towards_position(
                    current_pos, best_target, movement_points
                )
                if (
                    target_pos
                    and target_pos != current_pos
                    and target_pos not in occupied_positions
                ):
                    print(f"     🎯 Exploring towards {best_target}")
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Explore towards strategic area (distance: {min_distance})",
                    }

        # Priority 6: move towards strategic positions
        if strategic_positions and movement_points > 0:
            # Collect occupied positions
            occupied_positions = set()
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                pos = self.world.get_component(entity, HexPosition)
                if pos:
                    occupied_positions.add((pos.col, pos.row))

            # Find nearest unoccupied strategic position
            unoccupied_strategic = []
            for strategic_pos in strategic_positions:
                pos = strategic_pos["position"]
                target_pos = (pos.get("col", 0), pos.get("row", 0))
                if target_pos not in occupied_positions:
                    unoccupied_strategic.append(strategic_pos)

            if unoccupied_strategic:
                nearest_strategic = min(
                    unoccupied_strategic,
                    key=lambda s: HexMath.hex_distance(
                        current_pos,
                        (s["position"].get("col", 0), s["position"].get("row", 0)),
                    ),
                )

                strategic_pos = (
                    nearest_strategic["position"].get("col", 0),
                    nearest_strategic["position"].get("row", 0),
                )

                target_pos = self._calculate_move_towards_position(
                    current_pos, strategic_pos, movement_points
                )

                if (
                    target_pos
                    and target_pos != current_pos
                    and target_pos not in occupied_positions
                ):
                    print(f"     🎯 Moving towards strategic position {strategic_pos}")
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Move towards strategic {nearest_strategic['terrain']} position",
                    }

        # Priority 7: fortify current position
        if action_points >= 1:
            print(f"     🔨 Attempting to fortify current position")
            return {
                "action": "fortify",
                "params": {
                    "unit_id": unit_id,
                    "position": {"col": current_pos[0], "row": current_pos[1]},
                },
                "reason": "Fortify current position for defense",
            }

        # Last resort: rest
        print(f"     😴 No better options, resting")
        return {
            "action": "rest",
            "params": {"unit_id": unit_id},
            "reason": "Rest and recover",
        }

    def _calculate_move_towards_enemy(
        self,
        current_pos: Tuple[int, int],
        enemy_pos: Tuple[int, int],
        movement_points: int,
    ) -> Optional[Tuple[int, int]]:
        """Compute a target position when moving toward an enemy."""
        # Simple heuristic: move 1 step toward the enemy.
        dx = enemy_pos[0] - current_pos[0]
        dy = enemy_pos[1] - current_pos[1]

        # Normalize direction
        if abs(dx) > abs(dy):
            move_x = 1 if dx > 0 else -1
            move_y = 0
        elif abs(dy) > abs(dx):
            move_x = 0
            move_y = 1 if dy > 0 else -1
        else:
            # Diagonal move
            move_x = 1 if dx > 0 else -1
            move_y = 1 if dy > 0 else -1

        target_pos = (current_pos[0] + move_x, current_pos[1] + move_y)

        # Ensure the move is within movement range
        if HexMath.hex_distance(current_pos, target_pos) <= movement_points:
            return target_pos

        return current_pos

    def _calculate_move_towards_position(
        self,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        movement_points: int,
    ) -> Optional[Tuple[int, int]]:
        """Compute a target position when moving toward a target."""
        distance = HexMath.hex_distance(current_pos, target_pos)

        if distance <= movement_points:
            return target_pos

        # Move 1 step toward the target
        return self._calculate_move_towards_enemy(
            current_pos, target_pos, movement_points
        )

    def _execute_strategy(self, strategy: Dict[str, Any], faction: Faction) -> bool:
        """Execute the chosen strategy via the LLM Action Handler V3."""
        action = strategy.get("action")
        params = strategy.get("params", {})
        reason = strategy.get("reason", "")

        print(f"     🎮 Executing {action}: {reason}")

        try:
            if action == "attack":
                result = self.llm_handler.handle_attack_action(params)
            elif action == "move":
                result = self.llm_handler.handle_move_action(params)
            elif action == "occupy":
                result = self.llm_handler.handle_occupy_action(params)
            elif action == "fortify":
                result = self.llm_handler.handle_fortify_action(params)
            elif action == "rest":
                result = self.llm_handler.handle_rest_action(params)
            elif action == "skill":
                result = self.llm_handler.handle_skill_action(params)
            else:
                print(f"     ❌ Unknown action: {action}")
                return False

            success = result.get("success", False)
            message = result.get("message", "")

            if success:
                print(f"     ✅ {action} succeeded: {message}")

                # Record successful action to AI memory
                unit_id = params.get("unit_id")
                if unit_id:
                    self.ai_memory[unit_id] = {
                        "last_action": action,
                        "last_success": True,
                        "last_reason": reason,
                        "timestamp": time.time(),
                    }

                    # On success, clear failure record for this action
                    if unit_id in self.failed_actions:
                        action_key = self._get_action_key(action, params)
                        if action_key in self.failed_actions[unit_id]:
                            del self.failed_actions[unit_id][action_key]

                return True
            else:
                print(f"     ❌ {action} failed: {message}")

                # Record failed action to memory and failure list
                unit_id = params.get("unit_id")
                if unit_id:
                    self.ai_memory[unit_id] = {
                        "last_action": action,
                        "last_success": False,
                        "last_reason": reason,
                        "last_error": message,
                        "timestamp": time.time(),
                    }

                    # Track failures to avoid repeated attempts
                    if unit_id not in self.failed_actions:
                        self.failed_actions[unit_id] = {}
                    action_key = self._get_action_key(action, params)
                    self.failed_actions[unit_id][action_key] = time.time()

                return False

        except Exception as e:
            print(f"     💥 Exception executing {action}: {e}")
            return False

    def _get_action_key(self, action: str, params: Dict[str, Any]) -> str:
        """Generate a unique key for an action (to track failures)."""
        if action == "occupy":
            pos = params.get("position", {})
            return f"occupy_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "fortify":
            pos = params.get("position", {})
            return f"fortify_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "move":
            pos = params.get("target_position", {})
            return f"move_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "attack":
            target_id = params.get("target_id", 0)
            return f"attack_{target_id}"
        else:
            return f"{action}_general"

    def _cleanup_old_failed_actions(self):
        """Clear failure records older than 30 seconds."""
        current_time = time.time()
        for unit_id in list(self.failed_actions.keys()):
            unit_failed_actions = self.failed_actions[unit_id]
            # Remove records older than 30 seconds
            expired_keys = [
                key
                for key, timestamp in unit_failed_actions.items()
                if current_time - timestamp > 30.0
            ]
            for key in expired_keys:
                del unit_failed_actions[key]

            # If no failures remain for the unit, remove the entry
            if not unit_failed_actions:
                del self.failed_actions[unit_id]

    def _end_turn(self, faction: Faction):
        """End the AI turn."""
        try:
            # Try ending via the LLM Action Handler first
            result = self.llm_handler.handle_end_turn({"faction": faction.value})
            if result.get("success"):
                print(f"✅ {faction.value} turn ended successfully")
                return True
            else:
                print(f"⚠️ LLM Handler failed to end turn: {result.get('message')}")

            # If handler fails, try calling the turn system directly
            turn_system = self._get_turn_system()
            if turn_system:
                # Check for end_turn method
                if hasattr(turn_system, "end_turn"):
                    turn_system.end_turn()
                    print(f"✅ {faction.value} turn ended via TurnSystem")
                    return True
                elif hasattr(turn_system, "agent_end_turn"):
                    turn_system.agent_end_turn()
                    print(
                        f"✅ {faction.value} turn ended via TurnSystem.agent_end_turn"
                    )
                    return True
                else:
                    print(f"⚠️ TurnSystem found but no end_turn method")
            else:
                print(f"⚠️ No TurnSystem available")

            # If all fail, at least record the attempt
            print(f"⚠️ Could not end turn for {faction.value}, but continuing")
            return False

        except Exception as e:
            print(f"💥 Exception ending turn: {e}")
            return False

    def _get_turn_system(self):
        """Get the turn system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _trigger_game_over(self, losing_faction: Faction, reason: str):
        """Trigger game over."""
        print(f"🏁 Game Over! {losing_faction.value} {reason}")

        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            game_state.game_over = True
            # Winner/finalization can be set here if needed
            print(f"🎉 Game marked as over")

    def _check_victory_conditions(self):
        """Check victory conditions."""
        faction_status = {}

        # Count alive units per faction
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            alive_units = 0
            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if (
                    unit
                    and unit.faction == faction
                    and unit_count
                    and unit_count.current_count > 0
                ):
                    alive_units += 1

            faction_status[faction] = alive_units

        # Determine eliminated factions
        eliminated_factions = [
            faction for faction, count in faction_status.items() if count == 0
        ]
        surviving_factions = [
            faction for faction, count in faction_status.items() if count > 0
        ]

        if len(surviving_factions) <= 1:
            if len(surviving_factions) == 1:
                winner = surviving_factions[0]
                print(f"🎉 {winner.value} wins! All other factions eliminated.")
            else:
                print(f"🤝 Draw! All factions eliminated.")

            self._trigger_game_over(
                eliminated_factions[0] if eliminated_factions else Faction.WEI,
                "eliminated",
            )
            return True

        return False

    def get_ai_memory_summary(self) -> Dict[str, Any]:
        """Get AI memory summary (debug)."""
        return {
            "total_units_tracked": len(self.ai_memory),
            "recent_actions": {
                unit_id: {
                    "action": memory.get("last_action"),
                    "success": memory.get("last_success"),
                    "reason": memory.get("last_reason", memory.get("last_error", "")),
                }
                for unit_id, memory in self.ai_memory.items()
            },
        }
