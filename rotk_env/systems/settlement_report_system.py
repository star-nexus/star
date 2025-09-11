"""
Settlement Report Generator System.
Collects end-of-game data, builds a `SettlementReport`, writes JSON/CSV,
and prints an English summary. Waits briefly for LLM stats before finalizing.
"""

import os
import json
import csv
import datetime
from typing import Dict, Any, Optional, List
from framework import System, World
from ..components.settlement_report import (
    SettlementReport, 
    BattleStatistics, 
    MapStatistics, 
    PerformanceStatistics
)
from ..components import (
    GameState, 
    GameStats, 
    GameTime, 
    MapData, 
    Unit, 
    UnitCount, 
    Terrain,
    TerritoryControl
)
from ..prefabs.config import Faction, TerrainType, GameConfig
from ..components.agent_info import AgentInfo, AgentInfoRegistry


class SettlementReportSystem(System):
    """Generates the settlement report after game over."""
    
    def __init__(self):
        super().__init__(priority=200)  # run late after game over
        self.report_generated = False
        self.game_end_time = None
        self.timeout_seconds = 10.0  # timeout seconds
        
    def initialize(self, world: World) -> None:
        self.world = world
        
    def subscribe_events(self):
        """No subscriptions; polled in update()."""
        pass
        
    def update(self, delta_time: float) -> None:
        """Update: countdown gate then generate report."""
        if self.report_generated:
            return

        game_state = self.world.get_singleton_component(GameState)
        if not (game_state and game_state.game_over):
            return

        game_stats = self.world.get_singleton_component(GameStats)

        # First time seeing game over, print the current collection progress once, and start the real countdown from the next frame
        if self.game_end_time is None:
            import time
            self.game_end_time = time.time()
            try:
                registered = list(getattr(game_stats, 'registered_factions', set())) if game_stats else []
                received = list(getattr(game_stats, 'received_llm_stats_factions', set())) if game_stats else []
                print(f"[SettlementReport] 🏁 Game over detected, waiting for LLM stats or timeout... Progress: {len(received)}/{len(registered)} -> received={[f.value for f in received]} registered={[f.value for f in registered]}")
            except Exception as _e:
                print(f"[SettlementReport] ℹ️ Unable to read registered/received sets: {_e}")
            return

        # Time accounting
        import time
        elapsed = time.time() - self.game_end_time
        remaining = max(0.0, self.timeout_seconds - elapsed)

        # Ready flag: throttle logging; still wait until countdown ends
        if game_stats and getattr(game_stats, 'can_generate_settlement_report', False):
            if int(elapsed) != getattr(self, '_last_ready_second', -1):
                try:
                    registered = list(getattr(game_stats, 'registered_factions', set()))
                    received = list(getattr(game_stats, 'received_llm_stats_factions', set()))
                    print(f"[SettlementReport] 🎯 LLM stats ready (progress: {len(received)}/{len(registered)}), will generate after countdown (remaining {remaining:.1f}s)")
                except Exception:
                    print(f"[SettlementReport] 🎯 LLM stats ready, will generate after countdown (remaining {remaining:.1f}s)")
                self._last_ready_second = int(elapsed)

        # Countdown over: generate report (regardless of readiness)
        if elapsed >= self.timeout_seconds:
            try:
                registered = list(getattr(game_stats, 'registered_factions', set())) if game_stats else []
                received = list(getattr(game_stats, 'received_llm_stats_factions', set())) if game_stats else []
                print(f"[SettlementReport] ⏰ Timeout waiting for LLM stats, generating report... Final progress: {len(received)}/{len(registered)} -> received={[f.value for f in received]} registered={[f.value for f in registered]}")
            except Exception as _e:
                print(f"[SettlementReport] ⏰ Timeout waiting for LLM stats, generating report... (failed to read sets: {_e})")
            self._generate_settlement_report()
            self.report_generated = True
            
    
    def _generate_settlement_report(self) -> None:
        """Generate and persist the settlement report."""
        print("[SettlementReport] 🎯 Begin generating settlement report...")
        
        try:
            # Collect all statistics
            report_data = self._collect_comprehensive_statistics()
            
            # Create settlement report component
            settlement_report = SettlementReport(**report_data)
            self.world.add_singleton_component(settlement_report)
            
            # Persist to files
            self._save_report_to_files(report_data)
            
            # Print to console
            self._print_report_summary(report_data)
            
            print("[SettlementReport] ✅ Settlement report generated!")
            
        except Exception as e:
            print(f"[SettlementReport] ❌ Error while generating settlement report: {e}")
            import traceback
            traceback.print_exc()
    
    def _collect_comprehensive_statistics(self) -> Dict[str, Any]:
        """Collect comprehensive statistics across subsystems."""
        # Use current time as experiment id
        timestamp = datetime.datetime.now()
        experiment_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Base game data
        game_data = self._collect_game_data()
        
        # Units info
        units_info = self._collect_units_info()
        
        # Battle stats (uses units_info to correct casualties)
        battle_stats = self._collect_battle_statistics(units_info)
        
        # Map stats
        map_stats = self._collect_map_statistics()
        
        # Performance stats
        performance_stats = self._collect_performance_statistics()
        
        # Placeholder/agent/model info
        placeholder_data = self._collect_placeholder_data()
        
        return {
            "experiment_id": experiment_id,
            "timestamp": timestamp.isoformat(),
            "map_type": self._get_map_type(),
            **game_data,
            "units_info": units_info,
            "battle_statistics": battle_stats,
            "map_statistics": map_stats,
            "performance_statistics": performance_stats,
            **placeholder_data
        }

    def _format_symmetry(self, symmetry: str) -> str:
        """Return a human-friendly description for symmetry type."""
        mapping = {
            "moba": "MOBA-style (three-lane)",
            "river_split": "River-split diagonal",
            "diagonal": "Diagonal symmetry",
            "square": "Square symmetry",
            "horizontal": "Horizontal symmetry",
            "unknown": "Unknown",
            "": "Unknown",
        }
        return mapping.get(symmetry, f"Custom ({symmetry})")
    
    def _collect_game_data(self) -> Dict[str, Any]:
        """Collect basic game data."""
        game_state = self.world.get_singleton_component(GameState)
        game_time = self.world.get_singleton_component(GameTime)
        
        # Duration
        game_duration = 0.0
        if game_time:
            game_duration = game_time.get_game_elapsed_seconds()
        
        # Victory type
        is_tie = False
        winner_faction = None
        is_half_win = False
        
        if game_state:
            winner_faction = game_state.winner
            if winner_faction:
                # Check if it is a half-win (more surviving units)
                is_half_win = self._check_half_win_condition(winner_faction)
            else:
                is_tie = True
        
        # Detect game mode
        game_mode = self._detect_game_mode()
        
        # Collect progress
        game_progress = self._collect_game_progress(game_state, game_mode)
        
        return {
            "is_tie": is_tie,
            "winner_faction": winner_faction,
            "is_half_win": is_half_win,
            "game_duration_seconds": game_duration,
            "game_duration_formatted": f"{game_duration:.2f}s",
            "game_mode": game_mode,
            **game_progress
        }
    
    def _detect_game_mode(self) -> str:
        """Detect game mode (turn_based/real_time/unknown)."""
        # Check if there is a turn system
        turn_system_exists = False
        realtime_system_exists = False
        
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                turn_system_exists = True
            elif system.__class__.__name__ == "RealtimeSystem":
                realtime_system_exists = True
        
        if turn_system_exists and not realtime_system_exists:
            return "turn_based"
        elif realtime_system_exists:
            return "real_time"
        else:
            # Fallback: read from GameState component
            game_state = self.world.get_singleton_component(GameState)
            if game_state and hasattr(game_state, 'game_mode'):
                return game_state.game_mode.value
            else:
                return "unknown"
    
    def _collect_game_progress(self, game_state, game_mode: str) -> Dict[str, Any]:
        """Collect game progress (turns for turn-based; zero otherwise)."""
        if game_mode == "turn_based":
            # Turn-based: total turns
            total_turns = game_state.turn_number if game_state else 0
            return {
                "total_turns": total_turns
            }
        else:
            # Real-time: no turns
            return {
                "total_turns": 0
            }
    
    def _collect_units_info(self) -> Dict[str, Any]:
        """Collect unit info by faction, with corrected losses."""
        units_info = {}
        
        # Initial unit counts snapshot
        game_stats = self.world.get_singleton_component(GameStats)
        initial_counts = game_stats.initial_unit_counts if game_stats else {}
        
        # Debug information
        print(f"[SettlementReport] 📊 Debug:")
        print(f"  GameStats exists: {game_stats is not None}")
        if game_stats:
            print(f"  Initial unit counts: {initial_counts}")
        else:
            print("  ❌ GameStats is missing!")
        
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_units = []
            surviving_units = 0
            total_health = 0
            
            # Use initial unit counts snapshot instead of live counts
            total_units = initial_counts.get(faction, 0)
            
            # Count surviving units currently in world
            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)
                
                if unit.faction == faction:
                    current_count = unit_count.current_count if unit_count else 0
                    
                    if current_count > 0:
                        surviving_units += 1
                        total_health += current_count
                    
                    # Record unit details (including dead units if still present)
                    unit_info = {
                        "unit_id": entity,
                        "unit_type": unit.unit_type.value,
                        "position": self._get_unit_position(entity),
                        "current_count": current_count,
                        "max_count": unit_count.max_count if unit_count else 100,
                        "health_percentage": current_count / (unit_count.max_count if unit_count else 100) if unit_count else 0
                    }
                    faction_units.append(unit_info)
            
            # Extra debug lines
            print(f"  {faction.value}:")
            print(f"    initial units: {total_units}")
            print(f"    surviving units: {surviving_units}")
            print(f"    unit detail records: {len(faction_units)}")
            
            if total_units > 0: 
                destroyed_units = total_units - surviving_units
                units_info[faction.value] = {
                    "total_units": total_units,
                    "current_units": surviving_units,
                    "surviving_units": surviving_units,
                    "destroyed_units": destroyed_units,
                    "total_health": total_health,
                    "units": faction_units
                }
                print(f"    ✅ added to settlement report")
            else:
                print(f"    ❌ initial units is 0, skip")
        
        return units_info
    
    def _collect_battle_statistics(self, units_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Collect battle statistics and correct losses from units_info."""
        game_stats = self.world.get_singleton_component(GameStats)
        
        battle_stats = {
            "total_battles": 0,
            "faction_battle_stats": {},
            "battle_history": [],
            "casualties": {},
            "victory_types": {}
        }
        
        if game_stats:
            # History and totals from GameStats
            battle_stats["battle_history"] = game_stats.battle_history
            battle_stats["total_battles"] = len(game_stats.battle_history)
            
            # Per-faction casualties
            for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
                faction_stats = game_stats.faction_stats.get(faction, {})
                
                # Correct losses in faction_battle_stats
                if units_info and faction.value in units_info:
                    corrected_losses = units_info[faction.value].get("destroyed_units", 0)
                    # Copy and override losses
                    corrected_faction_stats = faction_stats.copy()
                    corrected_faction_stats["losses"] = corrected_losses
                    battle_stats["faction_battle_stats"][faction.value] = corrected_faction_stats
                    print(f"[SettlementReport] 🔧 corrected {faction.value} faction_battle_stats.losses: {faction_stats.get('losses', 0)} -> {corrected_losses}")
                else:
                    battle_stats["faction_battle_stats"][faction.value] = faction_stats
                
                # Correct casualties using units_info
                if units_info and faction.value in units_info:
                    corrected_units_lost = units_info[faction.value].get("destroyed_units", 0)
                    print(f"[SettlementReport] 🔧 corrected {faction.value} casualties.units_lost: {faction_stats.get('units_lost', 0)} -> {corrected_units_lost}")
                else:
                    # Fallback
                    corrected_units_lost = faction_stats.get("units_lost", 0)
                
                casualties = {
                    "units_lost": corrected_units_lost,
                    "damage_dealt": faction_stats.get("damage_dealt", 0),
                    "damage_taken": faction_stats.get("damage_taken", 0)
                }
                battle_stats["casualties"][faction.value] = casualties
        
        return battle_stats
    
    def _collect_map_statistics(self) -> Dict[str, Any]:
        """Collect map statistics"""
        map_data = self.world.get_singleton_component(MapData)
        
        map_stats = {
            "map_width": 0,
            "map_height": 0,
            "total_tiles": 0,
            "terrain_distribution": {},
            "territory_control": {},
            "symmetry_type": "unknown",
            "special_features": {}
        }
        
        if map_data:
            map_stats["map_width"] = map_data.width
            map_stats["map_height"] = map_data.height
            map_stats["total_tiles"] = len(map_data.tiles)
            
            # Terrain distribution
            terrain_counts = {}
            for tile_entity in map_data.tiles.values():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain:
                    terrain_type = terrain.terrain_type.value
                    terrain_counts[terrain_type] = terrain_counts.get(terrain_type, 0) + 1
            
            map_stats["terrain_distribution"] = terrain_counts
            
            # Territory control per faction
            for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
                controlled_tiles = 0
                fortified_tiles = 0
                
                for tile_entity in map_data.tiles.values():
                    territory = self.world.get_component(tile_entity, TerritoryControl)
                    if territory and territory.controlling_faction == faction:
                        controlled_tiles += 1
                        if territory.fortified:
                            fortified_tiles += 1
                
                if controlled_tiles > 0:
                    map_stats["territory_control"][faction.value] = {
                        "controlled_tiles": controlled_tiles,
                        "fortified_tiles": fortified_tiles
                    }
            
            # Map symmetry type from MapSystem if present
            map_system = None
            for system in self.world.systems:
                if system.__class__.__name__ == "MapSystem":
                    map_system = system
                    break
            
            if map_system:
                map_stats["symmetry_type"] = getattr(map_system, 'symmetry_type', 'unknown')
        
        return map_stats
    
    def _collect_performance_statistics(self) -> Dict[str, Any]:
        """Collect performance statistics (placeholder values)."""
        return {
            "fps_statistics": {
                "average_fps": 60.0,
                "min_fps": 45.0,
                "max_fps": 75.0
            },
            "memory_usage": {
                "total_memory": "128MB",
                "peak_memory": "150MB"
            },
            "rendering_performance": {
                "render_calls_per_frame": 100,
                "texture_memory": "64MB"
            },
            "system_performance": {
                "cpu_usage": "15%",
                "gpu_usage": "25%"
            }
        }
    
    def _collect_placeholder_data(self) -> Dict[str, Any]:
        """Collect agent/model metadata and auxiliary stats."""
        # Agent registry
        registry = self.world.get_singleton_component(AgentInfoRegistry)
        game_stats = self.world.get_singleton_component(GameStats)

        model_info = {}
        agent_endpoints = {}
        # enable_thinking capture
        enable_thinking_by_faction = {}
        response_times: Dict[str, int] = {"wei": 0, "shu": 0, "wu": 0}

        if registry:
            print(f"[SettlementReport] 📋 Agent registry found, registered factions: {list(registry.agents.keys())}")
            
            for faction in ["wei", "shu", "wu"]:
                agent_info = registry.get_agent_info(faction)
                if agent_info:
                    model_info[faction] = agent_info.model_id
                    agent_endpoints[faction] = agent_info.base_url
                    # capture enable_thinking flag
                    enable_thinking_by_faction[faction] = agent_info.enable_thinking
                    print(f"[SettlementReport] ✅ {faction}: {agent_info.provider}:{agent_info.model_id} (thinking: {agent_info.enable_thinking})")
                else:
                    model_info[faction] = "placeholder_model"
                    agent_endpoints[faction] = "unknown"
                    # default for unregistered faction
                    enable_thinking_by_faction[faction] = None
                    print(f"[SettlementReport] ⚠️ {faction}: Agent info not registered, using placeholder")
        else:
            print(f"[SettlementReport] ⚠️ Agent registry not found, using placeholders")
            # placeholders
            for faction in ["wei", "shu", "wu"]:
                model_info[faction] = "placeholder_model"
                agent_endpoints[faction] = "unknown"
                # default
                enable_thinking_by_faction[faction] = None

        # Aggregate response count per faction
        try:
            if game_stats:
                from ..prefabs.config import Faction as _Faction
                for f in [_Faction.WEI, _Faction.SHU, _Faction.WU]:
                    response_times[f.value] = game_stats.response_times_by_faction.get(f, 0)
            else:
                print("[SettlementReport] ⚠️ GameStats missing, response_times default to 0")
        except Exception as e:
            print(f"[SettlementReport] ⚠️ Failed to read response_times: {e}")

        # Strategy scores
        strategy_scores: Dict[str, float] = {"wei": 0.0, "shu": 0.0, "wu": 0.0}
        try:
            if game_stats and hasattr(game_stats, "strategy_scores_by_faction"):
                from ..prefabs.config import Faction as _Faction
                for f in [_Faction.WEI, _Faction.SHU, _Faction.WU]:
                    strategy_scores[f.value] = float(game_stats.strategy_scores_by_faction.get(f, 0.0))
        except Exception as e:
            print(f"[SettlementReport] ⚠️ Failed to read strategy_scores: {e}")

        # LLM API statistics
        llm_api_stats: Dict[str, Dict[str, Any]] = {"wei": {}, "shu": {}, "wu": {}}
        try:
            if game_stats and hasattr(game_stats, "llm_api_stats"):
                from ..prefabs.config import Faction as _Faction
                for f in [_Faction.WEI, _Faction.SHU, _Faction.WU]:
                    if f in game_stats.llm_api_stats:
                        llm_api_stats[f.value] = game_stats.llm_api_stats[f]
                        print(f"[SettlementReport] ✅ {f.value} LLM API stats: {game_stats.llm_api_stats[f]}")
                    else:
                        llm_api_stats[f.value] = {
                            "total_calls": 0,
                            "successful_calls": 0, 
                            "failed_calls": 0,
                            "success_rate": 0.0,
                            "provider": "unknown",
                            "model_id": "unknown"
                        }
            else:
                print("[SettlementReport] ⚠️ llm_api_stats not found in GameStats")
        except Exception as e:
            print(f"[SettlementReport] ⚠️ Failed to read llm_api_stats: {e}")

        return {
            "model_info": model_info,
            "agent_endpoints": agent_endpoints,
            "strategy_scores": {**strategy_scores},
            "enable_thinking": enable_thinking_by_faction,
            "response_times": response_times,
            "llm_api_stats": llm_api_stats
        }
    
    def _get_map_type(self) -> str:
        """获取地图类型"""
        # 检查MapSystem的地图类型
        for system in self.world.systems:
            if system.__class__.__name__ == "MapSystem":
                symmetry_type = getattr(system, 'symmetry_type', 'unknown')
                if symmetry_type == "moba":
                    return "MOBA风格地图"
                elif symmetry_type == "river_split":
                    return "河流分割对角线竞技地图"
                elif symmetry_type == "diagonal":
                    return "对角线对称竞技地图"
                elif symmetry_type == "square":
                    return "正方形竞技地图"
                elif symmetry_type == "horizontal":
                    return "水平轴对称竞技地图"
                else:
                    return f"自定义地图({symmetry_type})"
        
        return "标准随机地图"
    
    def _check_half_win_condition(self, winner_faction: Faction) -> bool:

        # Count both sides' surviving units
        winner_surviving = 0
        loser_surviving = 0
        
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)
            
            if unit_count and unit_count.current_count > 0:
                if unit.faction == winner_faction:
                    winner_surviving += 1
                else:
                    loser_surviving += 1
        
        # If the loser has more surviving units, it is a partial victory
        return loser_surviving > winner_surviving * 0.3  # If the loser has more surviving units, it is a partial victory
    
    def _get_unit_position(self, entity: int) -> Optional[Dict[str, int]]:

        from ..components import HexPosition
        position = self.world.get_component(entity, HexPosition)
        if position:
            return {"col": position.col, "row": position.row}
        return None
    
    def _save_report_to_files(self, report_data: Dict[str, Any]) -> None:

        try:
            # Create report directory
            report_dir = "settlement_reports"
            os.makedirs(report_dir, exist_ok=True)
            
            # Preprocess data, ensure JSON serializable
            json_safe_data = self._prepare_json_safe_data(report_data)
            
            # Validate preprocessed data
            if not self._validate_json_data(json_safe_data):
                print("[SettlementReport] ⚠️ JSON data validation failed, trying to fix...")
                # If validation fails, try more aggressive cleanup
                json_safe_data = self._force_clean_data(report_data)
            
            # Save to JSON file
            json_file = os.path.join(report_dir, f"settlement_{report_data['experiment_id']}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(json_safe_data, f, ensure_ascii=False, indent=2)
            
            # Save to CSV file for statistical analysis
            csv_file = os.path.join(report_dir, "settlement_results.csv")
            csv_exists = os.path.exists(csv_file)
            
            with open(csv_file, "a", encoding="utf-8", newline="") as f:
                if not csv_exists:
                    # CSV header including current_units fields
                    headers = [
                        "experiment_id", "timestamp", "map_type", "game_mode", "is_tie", "winner_faction",
                        "is_half_win", "game_duration_seconds", "total_turns",
                        "wei_total_units", "wei_current_units", "wei_surviving_units", "wei_destroyed_units",
                        "shu_total_units", "shu_current_units", "shu_surviving_units", "shu_destroyed_units",
                        "total_battles", "symmetry"
                    ]
                    f.write(",".join(headers) + "\n")
                
                # Data row
                row_data = [
                    report_data["experiment_id"],
                    report_data["timestamp"],
                    report_data["map_type"],
                    report_data.get("game_mode", "unknown"),
                    str(report_data["is_tie"]),
                    report_data["winner_faction"].value if report_data["winner_faction"] else "tie",
                    str(report_data["is_half_win"]),
                    f"{report_data['game_duration_seconds']:.2f}",
                    str(report_data.get("total_turns", 0)),
                    str(report_data["units_info"].get("wei", {}).get("total_units", 0)),
                    str(report_data["units_info"].get("wei", {}).get("current_units", 0)),  # 🆕
                    str(report_data["units_info"].get("wei", {}).get("surviving_units", 0)),
                    str(report_data["units_info"].get("wei", {}).get("destroyed_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("total_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("current_units", 0)),  # 🆕
                    str(report_data["units_info"].get("shu", {}).get("surviving_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("destroyed_units", 0)),
                    str(report_data["battle_statistics"]["total_battles"]),
                    self._format_symmetry(report_data["map_statistics"].get("symmetry_type", "unknown"))
                ]
                f.write(",".join(row_data) + "\n")
            
            print(f"[SettlementReport] 📁 report saved to: {json_file}")
            print(f"[SettlementReport] 📊 CSV data appended to: {csv_file}")
            
        except Exception as e:
            print(f"[SettlementReport] ❌ error saving report file: {e}")
            import traceback
            traceback.print_exc()
    
    def _prepare_json_safe_data(self, data: Any) -> Any:
        """Prepare JSON-safe data by converting non-serializable objects."""
        try:
            if isinstance(data, dict):
                return {key: self._prepare_json_safe_data(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [self._prepare_json_safe_data(item) for item in data]
            elif hasattr(data, 'value'):  # Enum-like (e.g., Faction)
                return data.value
            elif hasattr(data, '__dict__'):
                return str(data)
            elif isinstance(data, (int, float, str, bool, type(None))):
                return data
            else:
                return str(data)
        except Exception as e:
            print(f"[SettlementReport] ⚠️ Preprocess warning: {type(data)} -> {e}")
            return f"<unserializable: {type(data).__name__}>"
    
    def _validate_json_data(self, data: Any) -> bool:
        """Validate that data can be serialized to JSON."""
        try:
            json.dumps(data, ensure_ascii=False)
            return True
        except (TypeError, ValueError) as e:
            print(f"[SettlementReport] ❌ JSON validation failed: {e}")
            return False
    
    def _force_clean_data(self, data: Any) -> Any:
        """Force-clean data to remove/convert problematic values."""
        try:
            if isinstance(data, dict):
                cleaned_dict = {}
                for key, value in data.items():
                    # Ensure keys are strings
                    safe_key = str(key) if not isinstance(key, str) else key
                    try:
                        cleaned_dict[safe_key] = self._force_clean_data(value)
                    except Exception:
                        # Drop unprocessable values
                        continue
                return cleaned_dict
            elif isinstance(data, list):
                cleaned_list = []
                for item in data:
                    try:
                        cleaned_list.append(self._force_clean_data(item))
                    except Exception:
                        # Drop unprocessable items
                        continue
                return cleaned_list
            elif isinstance(data, (int, float, str, bool, type(None))):
                return data
            elif hasattr(data, 'value'):
                return data.value
            else:
                return str(data)
        except Exception as e:
            print(f"[SettlementReport] ⚠️ Force-clean warning: {type(data)} -> {e}")
            return f"<clean_failed: {type(data).__name__}>"
    
    def _print_report_summary(self, report_data: Dict[str, Any]) -> None:
        """Print report summary to console"""
        print("\n" + "=" * 80)
        print("🎯 Game Settlement Report")
        print("=" * 80)
        print(f"📅 Experiment ID: {report_data['experiment_id']}")
        print(f"⏰ Generated at: {report_data['timestamp']}")
        print(f"🗺️ Map type: {report_data['map_type']}")
        print(f"🎮 Game mode: {report_data.get('game_mode', 'unknown')}")
        print(f"🔄 Symmetry: {self._format_symmetry(report_data['map_statistics']['symmetry_type'])}")
        
        print(f"\n🏆 Game result:")
        if report_data["is_tie"]:
            print("   Result: Draw")
        else:
            winner = report_data["winner_faction"]
            victory_type = "Partial Victory" if report_data["is_half_win"] else "Decisive Victory"
            print(f"   Result: {winner.value} faction — {victory_type}")
        
        print(f"⏱️ Game duration: {report_data['game_duration_formatted']}")
        
        # Mode-specific info
        if report_data.get("game_mode") == "turn_based":
            print(f"🔄 Total turns: {report_data.get('total_turns', 0)}")
        else:
            print(f"⚡ Real-time: no turn limit")
        
        print(f"\n⚔️ Battle statistics:")
        print(f"   Total battles: {report_data['battle_statistics']['total_battles']}")
        
        print(f"\n👥 Unit statistics:")
        for faction_key in ["wei", "shu"]:
            if faction_key in report_data["units_info"]:
                faction_data = report_data["units_info"][faction_key]
                print(f"   {faction_key.upper()} Faction:")
                print(f"     Total units: {faction_data['total_units']}")
                print(f"     Surviving units: {faction_data['surviving_units']}")
                print(f"     Destroyed units: {faction_data['destroyed_units']}")
        
        print(f"\n🗺️ Map statistics:")
        map_stats = report_data["map_statistics"]
        print(f"   Map size: {map_stats['map_width']}x{map_stats['map_height']}")
        print(f"   Total tiles: {map_stats['total_tiles']}")
        
        print(f"   Terrain distribution:")
        for terrain, count in map_stats["terrain_distribution"].items():
            percentage = count / map_stats["total_tiles"] * 100
            print(f"     {terrain}: {count} tiles ({percentage:.1f}%)")
        
        print("=" * 80)
