"""
LLM Observation System - 为LLM系统提供观测信息收集功能
支持不同级别的观测：阵营视角、单个单位视角、上帝视角等
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from framework import World
from ..components import (
    Unit,
    UnitCount,
    HexPosition,
    MovementPoints,
    Combat,
    Vision,
    Player,
    GameState,
    FogOfWar,
    Terrain,
    Tile,
    UnitStatus,
    GameStats,
    BattleLog,
)
from ..prefabs.config import Faction, TerrainType
from ..utils.hex_utils import HexMath


class ObservationLevel:
    """观测级别定义"""

    UNIT = "unit"  # 单个单位视角
    FACTION = "faction"  # 阵营视角
    GODVIEW = "godview"  # 上帝视角（全知）
    LIMITED = "limited"  # 受限视角（基于雾战）


class LLMObservationSystem:
    """LLM观测系统 - 收集和提供不同级别的游戏观测信息"""

    def __init__(self, world: World):
        self.world = world
        self.cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 1.0  # 缓存1秒

    def get_observation(
        self,
        observation_level: str,
        faction: Optional[Faction] = None,
        unit_id: Optional[int] = None,
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """获取观测信息

        Args:
            observation_level: 观测级别 (unit/faction/godview/limited)
            faction: 阵营（faction级别时必需）
            unit_id: 单位ID（unit级别时必需）
            include_hidden: 是否包含隐藏信息（仅godview支持）

        Returns:
            Dict with 'success' field and either 'data' or 'error' information
        """
        try:
            import time

            current_time = time.time()

            # 参数验证
            if not observation_level:
                return {
                    "success": False,
                    "error": "Missing required parameter: observation_level",
                    "error_code": "MISSING_PARAM",
                    "operation": "get_observation",
                }

            if observation_level not in [
                ObservationLevel.UNIT,
                ObservationLevel.FACTION,
                ObservationLevel.GODVIEW,
                ObservationLevel.LIMITED,
            ]:
                return {
                    "success": False,
                    "error": f"Invalid observation_level: {observation_level}",
                    "error_code": "INVALID_PARAM",
                    "operation": "get_observation",
                    "valid_levels": [
                        ObservationLevel.UNIT,
                        ObservationLevel.FACTION,
                        ObservationLevel.GODVIEW,
                        ObservationLevel.LIMITED,
                    ],
                }

            # 特定级别的参数验证
            if observation_level == ObservationLevel.UNIT:
                if unit_id is None:
                    return {
                        "success": False,
                        "error": "unit_id is required for UNIT observation level",
                        "error_code": "MISSING_REQUIRED_PARAM",
                        "operation": "get_observation",
                        "observation_level": observation_level,
                    }
                try:
                    unit_id = int(unit_id)
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                        "error_code": "INVALID_TYPE",
                        "operation": "get_observation",
                    }

            elif observation_level in [
                ObservationLevel.FACTION,
                ObservationLevel.LIMITED,
            ]:
                if faction is None:
                    return {
                        "success": False,
                        "error": f"faction is required for {observation_level} observation level",
                        "error_code": "MISSING_REQUIRED_PARAM",
                        "operation": "get_observation",
                        "observation_level": observation_level,
                    }

            # 检查缓存
            cache_key = f"{observation_level}_{faction}_{unit_id}_{include_hidden}"
            if (
                cache_key in self.cache
                and current_time - self.cache_timestamp < self.cache_duration
            ):
                cached_result = self.cache[cache_key]
                cached_result["from_cache"] = True
                return cached_result

            # 生成新的观测数据
            observation_data = None
            if observation_level == ObservationLevel.UNIT:
                observation_data = self._get_unit_observation(unit_id)
            elif observation_level == ObservationLevel.FACTION:
                observation_data = self._get_faction_observation(
                    faction, include_hidden
                )
            elif observation_level == ObservationLevel.GODVIEW:
                observation_data = self._get_godview_observation()
            elif observation_level == ObservationLevel.LIMITED:
                observation_data = self._get_limited_observation(faction)

            # 检查观测数据是否有错误
            if observation_data and "error" in observation_data:
                result = {
                    "success": False,
                    "error": observation_data["error"],
                    "error_code": observation_data.get(
                        "error_code", "OBSERVATION_ERROR"
                    ),
                    "operation": "get_observation",
                    "observation_level": observation_level,
                }
            else:
                # 成功获取观测数据
                result = {
                    "success": True,
                    "data": observation_data,
                    "metadata": {
                        "timestamp": current_time,
                        "observation_level": observation_level,
                        "faction": (
                            faction.value
                            if faction and hasattr(faction, "value")
                            else str(faction) if faction else None
                        ),
                        "unit_id": unit_id,
                        "include_hidden": include_hidden,
                        "game_state": self._get_game_state_info(),
                    },
                    "operation": "get_observation",
                }

            # 更新缓存
            self.cache[cache_key] = result
            self.cache_timestamp = current_time

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in get_observation: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "operation": "get_observation",
                "params": {
                    "observation_level": observation_level,
                    "faction": faction,
                    "unit_id": unit_id,
                    "include_hidden": include_hidden,
                },
            }

    def _get_unit_observation(self, unit_id: int) -> Dict[str, Any]:
        """获取单个单位的观测信息"""
        try:
            if unit_id is None or not self.world.has_entity(unit_id):
                return {
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                }

            unit = self.world.get_component(unit_id, Unit)
            position = self.world.get_component(unit_id, HexPosition)
            unit_count = self.world.get_component(unit_id, UnitCount)
            movement = self.world.get_component(unit_id, MovementPoints)
            combat = self.world.get_component(unit_id, Combat)
            vision = self.world.get_component(unit_id, Vision)

            if not unit or not position:
                return {
                    "error": f"Unit {unit_id} missing essential components (Unit or HexPosition)",
                    "error_code": "COMPONENT_MISSING",
                }

            # 单位自身信息
            unit_info = {
                "id": unit_id,
                "name": unit.name,
                "faction": (
                    unit.faction.value
                    if hasattr(unit.faction, "value")
                    else str(unit.faction)
                ),
                "type": (
                    unit.unit_type.value
                    if hasattr(unit.unit_type, "value")
                    else str(unit.unit_type)
                ),
                "position": {"col": position.col, "row": position.row},
            }

            # 添加属性信息
            if unit_count:
                unit_info["unit_count"] = {
                    "current": unit_count.current_count,
                    "max": unit_count.max_count,
                    "percentage": (
                        unit_count.current_count / unit_count.max_count
                        if unit_count.max_count > 0
                        else 0
                    ),
                    "is_alive": unit_count.current_count > 0,
                }

            if movement:
                unit_info["movement"] = {
                    "current": movement.current_mp,
                    "max": movement.max_mp,
                    "has_moved": movement.has_moved,
                    "can_move": movement.current_mp > 0 and not movement.has_moved,
                }

            if combat:
                unit_info["combat"] = {
                    "attack": combat.base_attack,
                    "defense": combat.base_defense,
                    "range": combat.attack_range,
                    "has_attacked": (
                        combat.has_attacked
                        if hasattr(combat, "has_attacked")
                        else False
                    ),
                }

            # 单位视野内的信息
            visible_area = self._get_visible_area(unit_id)
            visible_units = self._get_visible_units(unit_id, visible_area)
            visible_terrain = self._get_visible_terrain(visible_area)

            return {
                "unit": unit_info,
                "visible_area": visible_area,
                "visible_units": visible_units,
                "visible_terrain": visible_terrain,
                "action_options": self._get_unit_action_options(unit_id),
            }

        except Exception as e:
            return {
                "error": f"Error getting unit observation: {str(e)}",
                "error_code": "OBSERVATION_ERROR",
            }

    def _get_faction_observation(
        self, faction: Faction, include_hidden: bool = False
    ) -> Dict[str, Any]:
        """获取阵营观测信息"""
        try:
            if not faction:
                return {
                    "error": "Faction not specified",
                    "error_code": "MISSING_FACTION",
                }

            # 获取阵营所有单位
            faction_units = []
            for entity in self.world.query().with_all(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                if unit and unit.faction == faction:
                    unit_obs = self._get_unit_summary(entity, include_hidden)
                    faction_units.append(unit_obs)

            # 获取已知敌方单位
            enemy_units = []
            visible_positions = set()

            # 收集所有友方单位的视野
            for entity in (
                self.world.query().with_all(Unit, Vision, HexPosition).entities()
            ):
                unit = self.world.get_component(entity, Unit)
                if unit and unit.faction == faction:
                    visible_area = self._get_visible_area(entity)
                    visible_positions.update(visible_area)

            # 获取视野内的敌方单位
            for entity in self.world.query().with_all(Unit, HexPosition).entities():
                unit = self.world.get_component(entity, Unit)
                position = self.world.get_component(entity, HexPosition)
                if (
                    unit
                    and position
                    and unit.faction != faction
                    and (position.col, position.row) in visible_positions
                ):
                    enemy_info = self._get_unit_summary(
                        entity, False
                    )  # 敌方单位不显示隐藏信息
                    enemy_units.append(enemy_info)

            # 战略信息
            strategic_info = self._get_strategic_info(faction)

            return {
                "faction": faction.value if hasattr(faction, "value") else str(faction),
                "own_units": faction_units,
                "known_enemy_units": enemy_units,
                "strategic_info": strategic_info,
                "territory_control": self._get_territory_control(faction),
                "resources": self._get_faction_resources(faction),
            }

        except Exception as e:
            return {
                "error": f"Error getting faction observation: {str(e)}",
                "error_code": "OBSERVATION_ERROR",
            }

    def _get_godview_observation(self) -> Dict[str, Any]:
        """获取上帝视角观测信息（全知视角）"""
        all_units = []
        for entity in self.world.query().with_all(Unit).entities():
            unit_info = self._get_unit_summary(entity, include_hidden=True)
            all_units.append(unit_info)

        # 按阵营分组
        units_by_faction = {}
        for unit in all_units:
            faction = unit.get("faction", "Unknown")
            if faction not in units_by_faction:
                units_by_faction[faction] = []
            units_by_faction[faction].append(unit)

        # 全地图信息
        map_info = self._get_full_map_info()

        # 全局统计
        global_stats = self._get_global_statistics()

        return {
            "all_units": all_units,
            "units_by_faction": units_by_faction,
            "map_info": map_info,
            "global_statistics": global_stats,
            "battle_history": self._get_battle_history(),
        }

    def _get_limited_observation(self, faction: Faction) -> Dict[str, Any]:
        """获取受限观测信息（基于雾战系统）"""
        # 类似faction观测，但受雾战限制
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        # 获取已探索区域
        explored_areas = set()
        if fog_of_war:
            # TODO: 从雾战系统获取已探索区域
            pass

        # 获取当前可见区域
        visible_areas = set()
        for entity in self.world.query().with_all(Unit, Vision, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                unit_visible = self._get_visible_area(entity)
                visible_areas.update(unit_visible)

        return {
            "faction": faction.value if hasattr(faction, "value") else str(faction),
            "explored_areas": list(explored_areas),
            "current_visible_areas": list(visible_areas),
            "fog_of_war_status": "active" if fog_of_war else "disabled",
        }

    def _get_visible_area(self, unit_id: int) -> Set[Tuple[int, int]]:
        """获取单位可见区域"""
        position = self.world.get_component(unit_id, HexPosition)
        vision = self.world.get_component(unit_id, Vision)

        if not position or not vision:
            return set()

        visible_positions = set()
        center = (position.col, position.row)

        # 简单的视野计算（六边形范围）
        for col in range(
            position.col - vision.sight_range, position.col + vision.sight_range + 1
        ):
            for row in range(
                position.row - vision.sight_range, position.row + vision.sight_range + 1
            ):
                if HexMath.hex_distance(center, (col, row)) <= vision.sight_range:
                    visible_positions.add((col, row))

        return visible_positions

    def _get_visible_units(
        self, observer_id: int, visible_area: Set[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """获取可见区域内的单位"""
        visible_units = []

        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            if entity == observer_id:  # 跳过观察者自己
                continue

            position = self.world.get_component(entity, HexPosition)
            if position and (position.col, position.row) in visible_area:
                unit_info = self._get_unit_summary(entity, include_hidden=False)
                visible_units.append(unit_info)

        return visible_units

    def _get_visible_terrain(
        self, visible_area: Set[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """获取可见区域内的地形"""
        terrain_info = []

        for col, row in visible_area:
            # 查找该位置的地形
            for entity in self.world.query().with_all(Tile, HexPosition).entities():
                position = self.world.get_component(entity, HexPosition)
                tile = self.world.get_component(entity, Tile)
                terrain = self.world.get_component(entity, Terrain)

                if position and position.col == col and position.row == row:
                    terrain_data = {
                        "position": {"col": col, "row": row},
                        "passable": tile.passable if tile else True,
                    }

                    if terrain:
                        terrain_data["type"] = (
                            terrain.terrain_type.value
                            if hasattr(terrain.terrain_type, "value")
                            else str(terrain.terrain_type)
                        )
                        terrain_data["movement_cost"] = terrain.movement_cost
                        terrain_data["defense_bonus"] = terrain.defense_bonus

                    terrain_info.append(terrain_data)
                    break

        return terrain_info

    def _get_unit_summary(
        self, entity: int, include_hidden: bool = False
    ) -> Dict[str, Any]:
        """获取单位摘要信息"""
        unit = self.world.get_component(entity, Unit)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)
        movement = self.world.get_component(entity, MovementPoints)
        combat = self.world.get_component(entity, Combat)
        status = self.world.get_component(entity, UnitStatus)

        unit_info = {
            "id": entity,
            "name": unit.name if unit else "Unknown",
            "faction": (
                unit.faction.value
                if unit and hasattr(unit.faction, "value")
                else str(unit.faction) if unit else "Unknown"
            ),
            "type": (
                unit.unit_type.value
                if unit and hasattr(unit.unit_type, "value")
                else str(unit.unit_type) if unit else "Unknown"
            ),
        }

        if position:
            unit_info["position"] = {"col": position.col, "row": position.row}

        if unit_count:
            unit_info["unit_count"] = {
                "current": unit_count.current_count,
                "max": unit_count.max_count,
                "percentage": (
                    unit_count.current_count / unit_count.max_count
                    if unit_count.max_count > 0
                    else 0
                ),
            }

        # 只有在包含隐藏信息或者是己方单位时才显示详细状态
        if include_hidden:
            if movement:
                unit_info["movement"] = {
                    "current": movement.current_mp,
                    "max": movement.max_mp,
                    "has_moved": movement.has_moved,
                }

            if combat:
                unit_info["combat"] = {
                    "attack": combat.attack,
                    "defense": combat.defense,
                    "range": combat.attack_range,
                    "has_attacked": combat.has_attacked,
                }

            if status:
                unit_info["status"] = {
                    "is_defending": getattr(status, "is_defending", False),
                    "is_fortified": getattr(status, "is_fortified", False),
                    "is_moving": getattr(status, "is_moving", False),
                }

        return unit_info

    def _get_unit_action_options(self, unit_id: int) -> List[str]:
        """获取单位可执行的动作选项"""
        movement = self.world.get_component(unit_id, MovementPoints)
        combat = self.world.get_component(unit_id, Combat)

        actions = []

        if movement and movement.current_mp > 0 and not movement.has_moved:
            actions.append("move")

        if combat and not combat.has_attacked:
            actions.append("attack")

        actions.extend(["defend", "scout", "retreat", "fortify"])

        return actions

    def _get_strategic_info(self, faction: Faction) -> Dict[str, Any]:
        """获取阵营战略信息"""
        return {
            "total_units": len(
                [
                    e
                    for e in self.world.query().with_all(Unit).entities()
                    if self.world.get_component(e, Unit).faction == faction
                ]
            ),
            "units_ready_to_act": len(
                [
                    e
                    for e in self.world.query()
                    .with_all(Unit, MovementPoints)
                    .entities()
                    if (
                        self.world.get_component(e, Unit).faction == faction
                        and self.world.get_component(e, MovementPoints).current_movement
                        > 0
                    )
                ]
            ),
            "wounded_units": len(
                [
                    e
                    for e in self.world.query().with_all(Unit, UnitCount).entities()
                    if (
                        self.world.get_component(e, Unit).faction == faction
                        and self.world.get_component(e, UnitCount).current_count
                        < self.world.get_component(e, UnitCount).max_count
                    )
                ]
            ),
        }

    def _get_territory_control(self, faction: Faction) -> Dict[str, Any]:
        """获取领土控制信息"""
        # TODO: 实现领土控制计算
        return {"controlled_tiles": 0, "contested_tiles": 0, "strategic_points": []}

    def _get_faction_resources(self, faction: Faction) -> Dict[str, Any]:
        """获取阵营资源信息"""
        # TODO: 实现资源系统
        return {"manpower": 1000, "supplies": 500, "morale": 80}

    def _get_full_map_info(self) -> Dict[str, Any]:
        """获取完整地图信息"""
        tiles = []
        for entity in self.world.query().with_all(Tile, HexPosition).entities():
            position = self.world.get_component(entity, HexPosition)
            tile = self.world.get_component(entity, Tile)
            terrain = self.world.get_component(entity, Terrain)

            tile_info = {
                "position": {"col": position.col, "row": position.row},
                "passable": tile.passable if tile else True,
            }

            if terrain:
                tile_info["terrain_type"] = (
                    terrain.terrain_type.value
                    if hasattr(terrain.terrain_type, "value")
                    else str(terrain.terrain_type)
                )
                tile_info["movement_cost"] = terrain.movement_cost
                tile_info["defense_bonus"] = terrain.defense_bonus

            tiles.append(tile_info)

        return {"tiles": tiles}

    def _get_global_statistics(self) -> Dict[str, Any]:
        """获取全局统计信息"""
        game_stats = self.world.get_singleton_component(GameStats)

        if game_stats:
            return {
                "turn_number": getattr(game_stats, "turn_number", 1),
                "total_battles": getattr(game_stats, "total_battles", 0),
                "total_casualties": getattr(game_stats, "total_casualties", 0),
            }

        return {"turn_number": 1, "total_battles": 0, "total_casualties": 0}

    def _get_battle_history(self) -> List[Dict[str, Any]]:
        """获取战斗历史"""
        battle_log = self.world.get_singleton_component(BattleLog)

        if battle_log and hasattr(battle_log, "entries"):
            return [
                {
                    "turn": entry.turn,
                    "attacker": entry.attacker_name,
                    "defender": entry.defender_name,
                    "damage": entry.damage,
                    "result": entry.result,
                }
                for entry in battle_log.entries[-10:]  # 最近10次战斗
            ]

        return []

    def _get_game_state_info(self) -> Dict[str, Any]:
        """获取游戏状态信息"""
        game_state = self.world.get_singleton_component(GameState)

        if game_state:
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
            }

        return {
            "current_player": "Unknown",
            "game_mode": "Unknown",
            "turn_number": 1,
            "phase": "action",
        }

    def clear_cache(self):
        """清空观测缓存"""
        self.cache.clear()
        self.cache_timestamp = 0
