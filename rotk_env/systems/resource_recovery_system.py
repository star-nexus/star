"""
Resource recovery system - handles automatic and manual recovery of multi-tier resources.
Implemented per MULTILAYER_RESOURCE_SYSTEM_DESIGN.md.
"""

from typing import Dict, Optional, Set

from framework import System, World
from ..components import ActionPoints, MovementPoints, SkillPoints, Terrain, GameTime
from ..prefabs.config import TerrainType


class ResourceRecoverySystem(System):
    """Multi-tier resource recovery system"""

    def __init__(self):
        super().__init__(priority=50)  # after GameTimeSystem (priority 10)

        # Action Point (AP) recovery config: recovers 1 AP per interval by default.
        # Interval is board seconds from GameTime.game_elapsed_time.
        self.ap_recovery_interval = 1.0
        self.ap_recovery_amount = 1

        # Movement Point (MP) recovery config: full recovery after each interval
        self.mp_recovery_interval = 3.0

        # Skill cooldown update config
        self.skill_cooldown_interval = 5.0

        # Per-entity remainder since the last granted tick, in board seconds.
        self.ap_elapsed: Dict[int, float] = {}
        self.mp_elapsed: Dict[int, float] = {}
        self.skill_elapsed: Dict[int, float] = {}
        # Last observed MP value per entity, used to detect when a move action has been spent
        self.mp_last_points: Dict[int, int] = {}
        # Last GameTime.game_elapsed_time this system applied. Not engine delta_time.
        self._last_game_elapsed: Optional[float] = None

        # Optional: accelerate recovery from decision quality. Not wired.
        # Tracks each unit's "decision quality score" to accelerate resource recovery.
        # self.unit_decision_quality: Dict[int, float] = {}  # 0.0-1.0; 1.0 = perfect decision

    def initialize(self, world: World) -> None:
        self.world = world
        game_time = world.get_singleton_component(GameTime)
        if game_time:
            self._last_game_elapsed = game_time.game_elapsed_time

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Recover from GameTime board seconds, not the engine dt argument.

        Pause, time_scale, and a skipped GameTime tick all go through the
        same ledger the HUD clock uses. ``delta_time`` is unused on purpose.
        """
        game_time = self.world.get_singleton_component(GameTime)
        if not game_time or not game_time.is_real_time():
            return

        now = game_time.game_elapsed_time
        last = self._last_game_elapsed
        if last is None:
            self._last_game_elapsed = now
            return

        sim_dt = now - last
        self._last_game_elapsed = now
        if sim_dt <= 0:
            return

        self._update_action_points(sim_dt)
        self._update_movement_points(sim_dt)
        self._update_skill_cooldowns(sim_dt)

    # === Action point recovery ===
    def _update_action_points(self, sim_dt: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.ap_recovery_interval
        amount = self.ap_recovery_amount

        for entity in self.world.query().with_component(ActionPoints).entities():
            seen_entities.add(entity)
            action_points = self.world.get_component(entity, ActionPoints)
            if not action_points:
                continue

            if action_points.current_ap >= action_points.max_ap:
                self.ap_elapsed.pop(entity, None)
                continue

            elapsed = self.ap_elapsed.get(entity, 0.0) + sim_dt
            if elapsed < interval:
                self.ap_elapsed[entity] = elapsed
                continue

            recover_ticks = int(elapsed // interval)
            if recover_ticks <= 0:
                self.ap_elapsed[entity] = elapsed
                continue

            increment = amount * recover_ticks
            action_points.current_ap = min(
                action_points.max_ap,
                action_points.current_ap + increment,
            )

            elapsed -= interval * recover_ticks
            if action_points.current_ap >= action_points.max_ap:
                self.ap_elapsed.pop(entity, None)
            else:
                self.ap_elapsed[entity] = elapsed

        # Clean up stale timers for entities that no longer exist
        stale_entities = set(self.ap_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.ap_elapsed.pop(entity, None)

    # === Movement point recovery ===
    def _update_movement_points(self, sim_dt: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.mp_recovery_interval

        for entity in self.world.query().with_component(MovementPoints).entities():
            seen_entities.add(entity)
            movement_points = self.world.get_component(entity, MovementPoints)
            if not movement_points:
                continue

            prev_points = self.mp_last_points.get(entity)
            if prev_points is None:
                prev_points = movement_points.current_mp
            else:
                if movement_points.current_mp < prev_points:
                    # Movement was spent; reset the recovery timer
                    self.mp_elapsed[entity] = 0.0
                    self.mp_last_points[entity] = movement_points.current_mp
                    continue

            if movement_points.current_mp >= movement_points.max_mp:
                self.mp_elapsed.pop(entity, None)
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            elapsed = self.mp_elapsed.get(entity, 0.0) + sim_dt
            if elapsed < interval:
                self.mp_elapsed[entity] = elapsed
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            recover_ticks = int(elapsed // interval)
            if recover_ticks <= 0:
                self.mp_elapsed[entity] = elapsed
                self.mp_last_points[entity] = movement_points.current_mp
                continue

            # Fully restore movement points
            movement_points.reset()
            elapsed -= interval * recover_ticks

            if movement_points.current_mp >= movement_points.max_mp:
                self.mp_elapsed.pop(entity, None)
            else:
                self.mp_elapsed[entity] = elapsed

            self.mp_last_points[entity] = movement_points.current_mp

        stale_entities = set(self.mp_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.mp_elapsed.pop(entity, None)
        stale_last = set(self.mp_last_points.keys()) - seen_entities
        for entity in stale_last:
            self.mp_last_points.pop(entity, None)

    # === Skill cooldown reduction ===
    def _update_skill_cooldowns(self, sim_dt: float) -> None:
        seen_entities: Set[int] = set()
        interval = self.skill_cooldown_interval

        for entity in self.world.query().with_component(SkillPoints).entities():
            seen_entities.add(entity)
            skill_points = self.world.get_component(entity, SkillPoints)
            if not skill_points:
                continue

            elapsed = self.skill_elapsed.get(entity, 0.0) + sim_dt
            if elapsed < interval:
                self.skill_elapsed[entity] = elapsed
                continue

            reduce_ticks = int(elapsed // interval)
            if reduce_ticks <= 0:
                self.skill_elapsed[entity] = elapsed
                continue

            for _ in range(reduce_ticks):
                skill_points.update_cooldowns()

            elapsed -= interval * reduce_ticks

            if not getattr(skill_points, "skill_cooldowns", None):
                self.skill_elapsed.pop(entity, None)
            else:
                self.skill_elapsed[entity] = elapsed

        stale_entities = set(self.skill_elapsed.keys()) - seen_entities
        for entity in stale_entities:
            self.skill_elapsed.pop(entity, None)


    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """Return the terrain type at the given tile position"""
        from ..components import MapData

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN
