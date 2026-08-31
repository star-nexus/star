"""Window ResourceRecoverySystem with one exact per-frame unit pass.

The base system scans AP entities, then MP entities, then SkillPoints entities.
Large skirmishes attach those resources to the same units, so the window path
uses the shared spatial index as the entity roster and processes all resource
layers together. Recovery timing semantics remain board-time based and MP spend
is still detected on the first frame after the component value drops.
"""

from __future__ import annotations

from framework.ecs import profiling

from ..components import ActionPoints, GameTime, MovementPoints, SkillPoints
from ..utils.unit_spatial_index import get_unit_spatial_index
from .resource_recovery_system import ResourceRecoverySystem as _BaseResourceRecoverySystem


class ResourceRecoverySystem(_BaseResourceRecoverySystem):
    """Single-pass recovery for indexed window units."""

    def update(self, delta_time: float) -> None:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super().update(delta_time)

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

        ap_active = 0
        mp_active = 0
        skill_active = 0
        scanned = 0

        for entity in index.by_entity:
            scanned += 1

            action_points = self.world.get_component(entity, ActionPoints)
            if action_points is not None:
                if action_points.current_ap >= action_points.max_ap:
                    self.ap_elapsed.pop(entity, None)
                else:
                    ap_active += 1
                    elapsed = self.ap_elapsed.get(entity, 0.0) + sim_dt
                    ticks = int(elapsed // self.ap_recovery_interval)
                    if ticks > 0:
                        action_points.current_ap = min(
                            action_points.max_ap,
                            action_points.current_ap + self.ap_recovery_amount * ticks,
                        )
                        elapsed -= self.ap_recovery_interval * ticks
                    if action_points.current_ap >= action_points.max_ap:
                        self.ap_elapsed.pop(entity, None)
                    else:
                        self.ap_elapsed[entity] = elapsed

            movement_points = self.world.get_component(entity, MovementPoints)
            if movement_points is not None:
                if movement_points.current_mp >= movement_points.max_mp:
                    self.mp_elapsed.pop(entity, None)
                    self.mp_last_points.pop(entity, None)
                else:
                    mp_active += 1
                    prev_points = self.mp_last_points.get(entity)
                    if prev_points is None or movement_points.current_mp < prev_points:
                        # Match the legacy first-observed-spend semantics: the
                        # detection frame resets the timer and does not accrue dt.
                        self.mp_elapsed[entity] = 0.0
                        self.mp_last_points[entity] = movement_points.current_mp
                    else:
                        elapsed = self.mp_elapsed.get(entity, 0.0) + sim_dt
                        ticks = int(elapsed // self.mp_recovery_interval)
                        if ticks > 0:
                            movement_points.reset()
                            elapsed -= self.mp_recovery_interval * ticks
                        if movement_points.current_mp >= movement_points.max_mp:
                            self.mp_elapsed.pop(entity, None)
                            self.mp_last_points.pop(entity, None)
                        else:
                            self.mp_elapsed[entity] = elapsed
                            self.mp_last_points[entity] = movement_points.current_mp

            skill_points = self.world.get_component(entity, SkillPoints)
            if skill_points is not None:
                cooldowns = getattr(skill_points, "skill_cooldowns", None)
                if not cooldowns:
                    self.skill_elapsed.pop(entity, None)
                else:
                    skill_active += 1
                    elapsed = self.skill_elapsed.get(entity, 0.0) + sim_dt
                    ticks = int(elapsed // self.skill_cooldown_interval)
                    if ticks > 0:
                        for _ in range(ticks):
                            skill_points.update_cooldowns()
                        elapsed -= self.skill_cooldown_interval * ticks
                    if not getattr(skill_points, "skill_cooldowns", None):
                        self.skill_elapsed.pop(entity, None)
                    else:
                        self.skill_elapsed[entity] = elapsed

        # Timer dictionaries contain only depleted/active resources except for
        # compatibility with state created before the index was installed. Clean
        # those rare stale ids without allocating a 2000-entry seen set.
        live = index.by_entity
        for ledger in (
            self.ap_elapsed,
            self.mp_elapsed,
            self.mp_last_points,
            self.skill_elapsed,
        ):
            for entity in tuple(ledger):
                if entity not in live:
                    ledger.pop(entity, None)

        profiling.profiler.set_frame_metric("recovery_units_scanned", scanned)
        profiling.profiler.set_frame_metric("recovery_ap_active", ap_active)
        profiling.profiler.set_frame_metric("recovery_mp_active", mp_active)
        profiling.profiler.set_frame_metric("recovery_skill_active", skill_active)
