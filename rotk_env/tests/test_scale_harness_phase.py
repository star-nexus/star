"""Scale Harness temporal-phase tests for sustained dynamic-world workloads."""

from collections import Counter

from framework.ecs.world import World

from rotk_env.components import HexPosition, MovementAnimation, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.movement_planning import MovePlan, MovementPlanningPolicy
from rotk_env.testing.scale_harness import PreparedMoveBatch, ScaleHarnessSystem


class _FakeMovementService:
    """Only the pure-motion surface needed by ScaleHarnessSystem."""

    def __init__(self, world):
        self.world = world

    def start_prepared_motion(self, entity, path, *, expected_start=None):
        pos = self.world.get_component(entity, HexPosition)
        start = (pos.col, pos.row)
        route = tuple(path)
        if expected_start is not None and start != expected_start:
            return {"success": False, "reason": "stale_motion_path"}
        anim = self.world.get_component(entity, MovementAnimation)
        if anim is None:
            anim = MovementAnimation()
            self.world.add_component(entity, anim)
        anim.path = list(route[1:])
        anim.current_target_index = 0
        anim.progress = 0.0
        anim.is_moving = True
        return {"success": True, "unit_id": entity}


def _unit(world, col):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=Faction.WEI, name="phase-test"),
    )
    world.add_component(entity, HexPosition(col, 0))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, MovementAnimation(speed=2.0))
    return entity


def _harness_with_batch(count=8):
    world = World()
    plans = []
    for col in range(count):
        entity = _unit(world, col)
        start = (col, 0)
        target = (col, 1)
        plans.append(
            MovePlan(
                entity=entity,
                start=start,
                requested_target=target,
                resolved_target=target,
                path=(start, target),
                cost=1,
                spendable_at_plan=1,
                policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
            )
        )

    harness = ScaleHarnessSystem(_FakeMovementService(world), "/tmp/not-opened.sock")
    harness.world = world  # no socket needed for direct command-level tests
    harness.prepared = PreparedMoveBatch(
        batch_id=1,
        seed=42,
        density=1.0,
        target_radius=1,
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
        correct_unreachable=True,
        living_units_at_prepare=count,
        requested_units=count,
        requested_targets={plan.entity: plan.requested_target for plan in plans},
        plans=plans,
        failures=Counter(),
    )
    return world, harness, plans


def test_synchronized_sustained_keeps_zero_initial_phase_and_no_hold_segment():
    world, harness, plans = _harness_with_batch()
    result = harness._start_sustained_batch(
        {"duration_seconds": 2.0, "phase": "synchronized"}
    )

    assert result["ok"] is True
    assert result["motion_phase"] == "synchronized"
    assert result["accepted_units"] == len(plans)
    assert result["segments_total"] == 4 * len(plans)
    assert result["animation_segments_total"] == result["segments_total"]

    for plan in plans:
        anim = world.get_component(plan.entity, MovementAnimation)
        assert anim.progress == 0.0
        assert anim.path[0] == plan.resolved_target


def test_staggered_sustained_changes_only_initial_phase_via_zero_distance_hold():
    world, harness, plans = _harness_with_batch()
    result = harness._start_sustained_batch(
        {
            "duration_seconds": 2.0,
            "phase": "staggered",
            "phase_seed": 7,
        }
    )

    assert result["ok"] is True
    assert result["motion_phase"] == "staggered"
    assert result["phase_seed"] == 7
    assert result["accepted_units"] == len(plans)
    # Real motion remains 4 segments per unit; the animation gets exactly one
    # extra zero-distance hold used only for phase offset.
    assert result["segments_total"] == 4 * len(plans)
    assert result["animation_segments_total"] == 5 * len(plans)

    progresses = []
    for plan in plans:
        anim = world.get_component(plan.entity, MovementAnimation)
        progresses.append(anim.progress)
        assert anim.path[0] == plan.start
        assert anim.path[1] == plan.resolved_target
        assert 0.0 <= anim.progress < 1.0

    assert len(set(progresses)) > 1
    assert any(progress > 0.0 for progress in progresses)


def test_invalid_sustained_phase_is_rejected_without_starting_units():
    world, harness, plans = _harness_with_batch()
    result = harness._start_sustained_batch(
        {"duration_seconds": 2.0, "phase": "not-a-phase"}
    )

    assert result["ok"] is False
    assert result["error"] == "invalid_phase"
    for plan in plans:
        assert world.get_component(plan.entity, MovementAnimation).is_moving is False
