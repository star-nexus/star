"""
Resource recovery system - handles automatic and manual recovery of multi-tier resources.
Implemented per MULTILAYER_RESOURCE_SYSTEM_DESIGN.md.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple

from framework import System, World
from framework.ecs import profiling
from ..components import ActionPoints, MovementPoints, SkillPoints, Terrain, GameTime
from ..prefabs.config import TerrainType


_RECOVERY_SYSTEM_ATTR = "_resource_recovery_scheduler"
_ScheduledEntry = Tuple[int, int]  # version, entity


def get_resource_recovery_system(world) -> Optional["ResourceRecoverySystem"]:
    """Return the world's recovery scheduler when it has been initialized."""
    return getattr(world, _RECOVERY_SYSTEM_ATTR, None)


def mark_action_points_spent(world, entity: int) -> None:
    system = get_resource_recovery_system(world)
    if system is not None:
        system.mark_action_points_spent(entity)


def mark_movement_points_spent(world, entity: int) -> None:
    system = get_resource_recovery_system(world)
    if system is not None:
        system.mark_movement_points_spent(entity)


def mark_skill_cooldown_started(world, entity: int) -> None:
    system = get_resource_recovery_system(world)
    if system is not None:
        system.mark_skill_cooldown_started(entity)


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

        # Heaps contain distinct due times. Entities that recover together share
        # one versioned bucket, avoiding 10k heappop calls in synchronized bursts.
        self._ap_heap: List[float] = []
        self._mp_heap: List[float] = []
        self._skill_heap: List[float] = []
        self._ap_buckets: Dict[float, List[_ScheduledEntry]] = {}
        self._mp_buckets: Dict[float, List[_ScheduledEntry]] = {}
        self._skill_buckets: Dict[float, List[_ScheduledEntry]] = {}
        self._ap_due: Dict[int, Tuple[float, int]] = {}
        self._mp_due: Dict[int, Tuple[float, int]] = {}
        self._skill_due: Dict[int, Tuple[float, int]] = {}
        self._ap_versions: Dict[int, int] = {}
        self._mp_versions: Dict[int, int] = {}
        self._skill_versions: Dict[int, int] = {}
        # MP recovery starts on the first recovery update after a spend.
        self._mp_pending_detection: Set[int] = set()
        self._known_entity_counter = 0

        # Optional: accelerate recovery from decision quality. Not wired.
        # Tracks each unit's "decision quality score" to accelerate resource recovery.
        # self.unit_decision_quality: Dict[int, float] = {}  # 0.0-1.0; 1.0 = perfect decision

    def initialize(self, world: World) -> None:
        self.world = world
        setattr(world, _RECOVERY_SYSTEM_ATTR, self)
        game_time = world.get_singleton_component(GameTime)
        if game_time:
            self._last_game_elapsed = game_time.game_elapsed_time
        self._bootstrap_active_resources()
        self._known_entity_counter = world.entity_counter

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
        if sim_dt <= 0:
            return

        # Resources created since the previous recovery boundary begin AP and
        # skill cadence at ``last`` and accrue this complete simulation interval.
        self._register_new_entities()
        self._last_game_elapsed = now

        # Detect MP spends at the recovery boundary. Pending entries invalidate
        # any superseded recovery task.
        pending_mp = tuple(self._mp_pending_detection)
        self._mp_pending_detection.clear()
        for entity in pending_mp:
            movement_points = self.world.get_component(entity, MovementPoints)
            if movement_points is None or movement_points.current_mp >= movement_points.max_mp:
                self._cancel_mp(entity)
                continue
            self.mp_elapsed[entity] = 0.0
            self.mp_last_points[entity] = movement_points.current_mp
            self._schedule_mp(entity, now + self.mp_recovery_interval)

        due_updates = 0
        due_updates += self._run_ap_due(now)
        due_updates += self._run_mp_due(now)
        due_updates += self._run_skill_due(now)

        profiling.profiler.set_frame_metric("recovery_units_scanned", 0)
        profiling.profiler.set_frame_metric("recovery_ap_active", len(self._ap_due))
        profiling.profiler.set_frame_metric("recovery_mp_active", len(self._mp_due))
        profiling.profiler.set_frame_metric("recovery_skill_active", len(self._skill_due))
        profiling.profiler.set_frame_metric(
            "recovery_pending_detection", len(self._mp_pending_detection)
        )
        profiling.profiler.set_frame_metric("recovery_due_updates", due_updates)

    @staticmethod
    def _next_version(versions: Dict[int, int], entity: int) -> int:
        version = versions.get(entity, 0) + 1
        versions[entity] = version
        return version

    def _schedule(
        self,
        entity: int,
        due_time: float,
        heap: List[float],
        buckets: Dict[float, List[_ScheduledEntry]],
        active: Dict[int, Tuple[float, int]],
        versions: Dict[int, int],
    ) -> None:
        version = self._next_version(versions, entity)
        due = float(due_time)
        active[entity] = (due, version)
        bucket = buckets.get(due)
        if bucket is None:
            bucket = []
            buckets[due] = bucket
            heapq.heappush(heap, due)
        bucket.append((version, entity))

    def _schedule_ap(self, entity: int, due_time: float) -> None:
        self._schedule(
            entity,
            due_time,
            self._ap_heap,
            self._ap_buckets,
            self._ap_due,
            self._ap_versions,
        )

    def _schedule_mp(self, entity: int, due_time: float) -> None:
        self._schedule(
            entity,
            due_time,
            self._mp_heap,
            self._mp_buckets,
            self._mp_due,
            self._mp_versions,
        )

    def _schedule_skill(self, entity: int, due_time: float) -> None:
        self._schedule(
            entity,
            due_time,
            self._skill_heap,
            self._skill_buckets,
            self._skill_due,
            self._skill_versions,
        )

    def _cancel(
        self,
        entity: int,
        active: Dict[int, Tuple[float, int]],
        versions: Dict[int, int],
    ) -> None:
        active.pop(entity, None)
        self._next_version(versions, entity)

    def _cancel_ap(self, entity: int) -> None:
        self._cancel(entity, self._ap_due, self._ap_versions)
        self.ap_elapsed.pop(entity, None)

    def _cancel_mp(self, entity: int) -> None:
        self._cancel(entity, self._mp_due, self._mp_versions)
        self._mp_pending_detection.discard(entity)
        self.mp_elapsed.pop(entity, None)
        self.mp_last_points.pop(entity, None)

    def _cancel_skill(self, entity: int) -> None:
        self._cancel(entity, self._skill_due, self._skill_versions)
        self.skill_elapsed.pop(entity, None)

    def _schedule_anchor(self) -> float:
        if self._last_game_elapsed is not None:
            return self._last_game_elapsed
        game_time = self.world.get_singleton_component(GameTime)
        return float(game_time.game_elapsed_time) if game_time is not None else 0.0

    def mark_action_points_spent(self, entity: int) -> None:
        action_points = self.world.get_component(entity, ActionPoints)
        if action_points is None or action_points.current_ap >= action_points.max_ap:
            return
        # Additional spends do not reset an active AP recovery cadence.
        if entity not in self._ap_due:
            self.ap_elapsed[entity] = 0.0
            self._schedule_ap(entity, self._schedule_anchor() + self.ap_recovery_interval)

    def mark_movement_points_spent(self, entity: int) -> None:
        movement_points = self.world.get_component(entity, MovementPoints)
        if movement_points is None or movement_points.current_mp >= movement_points.max_mp:
            return
        # Invalidate an active timer now and restart it at the next recovery
        # update, when the spend becomes part of the board-time ledger.
        self._cancel(entity, self._mp_due, self._mp_versions)
        self._mp_pending_detection.add(entity)
        self.mp_elapsed[entity] = 0.0
        self.mp_last_points[entity] = movement_points.current_mp

    def mark_skill_cooldown_started(self, entity: int) -> None:
        skill_points = self.world.get_component(entity, SkillPoints)
        if skill_points is None or not skill_points.skill_cooldowns:
            return
        # All cooldowns share the existing cadence; adding another cooldown does
        # not reset cooldown progress already accumulated by this entity.
        if entity not in self._skill_due:
            self.skill_elapsed[entity] = 0.0
            self._schedule_skill(
                entity, self._schedule_anchor() + self.skill_cooldown_interval
            )

    def _bootstrap_active_resources(self) -> None:
        """One initialization audit for pre-existing depleted resources."""
        for entity in self.world.query().with_component(ActionPoints).entities():
            self._register_initial_entity(entity, include_ap=True)

        for entity in self.world.query().with_component(MovementPoints).entities():
            self._register_initial_entity(entity, include_mp=True)

        for entity in self.world.query().with_component(SkillPoints).entities():
            self._register_initial_entity(entity, include_skill=True)

    def _register_initial_entity(
        self,
        entity: int,
        *,
        include_ap: bool = False,
        include_mp: bool = False,
        include_skill: bool = False,
    ) -> None:
        anchor = self._schedule_anchor()
        if include_ap and entity not in self._ap_due:
            action_points = self.world.get_component(entity, ActionPoints)
            if action_points is not None and action_points.current_ap < action_points.max_ap:
                self.ap_elapsed[entity] = 0.0
                self._schedule_ap(entity, anchor + self.ap_recovery_interval)

        if include_mp and entity not in self._mp_due:
            movement_points = self.world.get_component(entity, MovementPoints)
            if movement_points is not None and movement_points.current_mp < movement_points.max_mp:
                self._mp_pending_detection.add(entity)

        if include_skill and entity not in self._skill_due:
            skill_points = self.world.get_component(entity, SkillPoints)
            if skill_points is not None and skill_points.skill_cooldowns:
                self.skill_elapsed[entity] = 0.0
                self._schedule_skill(entity, anchor + self.skill_cooldown_interval)

    def _register_new_entities(self) -> None:
        """Inspect only entity IDs created since the previous recovery update.

        World IDs are monotonic, so a system may initialize before initial units
        are constructed without rescanning all existing entities every frame.
        """
        current_counter = self.world.entity_counter
        start = self._known_entity_counter
        if current_counter <= start:
            return
        for entity in range(start, current_counter):
            if self.world.has_entity(entity):
                self._register_initial_entity(
                    entity, include_ap=True, include_mp=True, include_skill=True
                )
        self._known_entity_counter = current_counter

    @staticmethod
    def _is_current_task(
        entity: int,
        due: float,
        version: int,
        active: Dict[int, Tuple[float, int]],
    ) -> bool:
        return active.get(entity) == (due, version)

    def _run_ap_due(self, now: float) -> int:
        processed = 0
        interval = self.ap_recovery_interval
        while self._ap_heap and self._ap_heap[0] <= now:
            due = heapq.heappop(self._ap_heap)
            entries = self._ap_buckets.pop(due, ())
            ticks = int((now - due) // interval) + 1
            for version, entity in entries:
                if not self._is_current_task(entity, due, version, self._ap_due):
                    continue
                action_points = self.world.get_component(entity, ActionPoints)
                if action_points is None or action_points.current_ap >= action_points.max_ap:
                    self._cancel_ap(entity)
                    continue
                action_points.recover(self.ap_recovery_amount * ticks)
                processed += 1
                if action_points.current_ap >= action_points.max_ap:
                    self._cancel_ap(entity)
                else:
                    next_due = due + interval * ticks
                    self.ap_elapsed[entity] = max(
                        0.0, interval - (next_due - now)
                    )
                    self._schedule_ap(entity, next_due)
        return processed

    def _run_mp_due(self, now: float) -> int:
        processed = 0
        while self._mp_heap and self._mp_heap[0] <= now:
            due = heapq.heappop(self._mp_heap)
            entries = self._mp_buckets.pop(due, ())
            for version, entity in entries:
                if not self._is_current_task(entity, due, version, self._mp_due):
                    continue
                movement_points = self.world.get_component(entity, MovementPoints)
                if movement_points is None:
                    self._cancel_mp(entity)
                    continue
                movement_points.reset()
                processed += 1
                self._cancel_mp(entity)
        return processed

    def _run_skill_due(self, now: float) -> int:
        processed = 0
        interval = self.skill_cooldown_interval
        while self._skill_heap and self._skill_heap[0] <= now:
            due = heapq.heappop(self._skill_heap)
            entries = self._skill_buckets.pop(due, ())
            ticks = int((now - due) // interval) + 1
            for version, entity in entries:
                if not self._is_current_task(entity, due, version, self._skill_due):
                    continue
                skill_points = self.world.get_component(entity, SkillPoints)
                if skill_points is None or not skill_points.skill_cooldowns:
                    self._cancel_skill(entity)
                    continue
                for _ in range(ticks):
                    skill_points.update_cooldowns()
                processed += 1
                if not skill_points.skill_cooldowns:
                    self._cancel_skill(entity)
                else:
                    next_due = due + interval * ticks
                    self.skill_elapsed[entity] = max(
                        0.0, interval - (next_due - now)
                    )
                    self._schedule_skill(entity, next_due)
        return processed

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
