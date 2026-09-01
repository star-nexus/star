from framework.ecs.world import World

from rotk_env.components import HexPosition, MovementPoints, Unit, UnitCount, UnitStatus
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.movement_planning import (
    MovementPlanningPolicy,
    MovementPlanningSnapshot,
)
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.testing.scale_harness import ScaleHarnessSystem


def _world_with_unit(*, mp=3):
    world = World()
    entity = world.create_entity()
    world.add_component(entity, HexPosition(0, 0))
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=Faction.WEI, name="test"),
    )
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, MovementPoints(base_mp=mp, current_mp=mp, max_mp=mp))
    world.add_component(entity, UnitStatus())
    system = MovementSystem()
    system.initialize(world)
    return world, entity, system


def _context(occupied=None, blockers=None, costs=None, walkable=None):
    occupied = set(occupied or ())
    blockers = set(blockers or ())
    costs = dict(costs or {})
    walkable = set(walkable) if walkable is not None else None
    return occupied, blockers, costs, walkable, 7


def test_plan_is_pure_and_execute_mutates_without_replanning(monkeypatch):
    world, entity, movement = _world_with_unit(mp=3)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            costs={(1, 0): 1, (2, 0): 1},
            walkable={(0, 0), (1, 0), (2, 0)},
        ),
    )

    planned = movement.plan_move(entity, (2, 0))
    assert planned.success
    assert planned.plan is not None
    assert (world.get_component(entity, HexPosition).col, world.get_component(entity, HexPosition).row) == (0, 0)
    assert world.get_component(entity, MovementPoints).current_mp == 3

    result = movement.execute_move_plan(planned.plan, emit_log=False)
    assert result["success"] is True
    assert result["to"] == (2, 0)
    assert world.get_component(entity, MovementPoints).current_mp == 1
    assert (world.get_component(entity, HexPosition).col, world.get_component(entity, HexPosition).row) == (2, 0)


def test_normal_policy_rejects_occupied_endpoint_but_stress_policy_allows_it(monkeypatch):
    _world, entity, movement = _world_with_unit(mp=3)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            occupied={(1, 0)},
            blockers={(1, 0)},
            costs={(1, 0): 1},
            walkable={(0, 0), (1, 0)},
        ),
    )

    normal = movement.plan_move(entity, (1, 0))
    assert normal.success is False
    assert normal.response["reason"] == "destination_occupied"

    stress = movement.plan_move(
        entity,
        (1, 0),
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
    )
    assert stress.success is True
    assert stress.plan is not None
    assert stress.plan.resolved_target == (1, 0)


def test_stress_endpoint_policy_does_not_allow_enemy_traversal(monkeypatch):
    _world, entity, movement = _world_with_unit(mp=3)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            occupied={(1, 0)},
            blockers={(1, 0)},
            costs={(1, 0): 1, (2, 0): 1},
            walkable={(0, 0), (1, 0), (2, 0)},
        ),
    )

    result = movement.plan_move(
        entity,
        (2, 0),
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
    )
    assert result.success is False
    assert result.response["reason"] == "no_path"


def test_batch_planning_can_correct_requested_target_to_budget(monkeypatch):
    _world, entity, movement = _world_with_unit(mp=2)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            costs={(1, 0): 1, (2, 0): 1, (3, 0): 1},
            walkable={(0, 0), (1, 0), (2, 0), (3, 0)},
        ),
    )

    normal = movement.plan_move(entity, (3, 0))
    assert normal.success is False
    assert normal.response["reason"] == "insufficient_mp"

    corrected = movement.plan_move(
        entity,
        (3, 0),
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
        correct_to_budget=True,
    )
    assert corrected.success is True
    assert corrected.plan is not None
    assert corrected.plan.requested_target == (3, 0)
    assert corrected.plan.resolved_target == (2, 0)
    assert corrected.plan.path == ((0, 0), (1, 0), (2, 0))
    assert corrected.plan.cost == 2
    assert corrected.plan.corrected is True
    assert corrected.plan.correction_reason == "budget"


def test_batch_planning_can_correct_no_path_to_nearest_reachable(monkeypatch):
    _world, entity, movement = _world_with_unit(mp=2)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            costs={(0, 0): 1, (1, 0): 1, (0, 1): 1, (3, 0): 1},
            walkable={(0, 0), (1, 0), (0, 1), (3, 0)},
        ),
    )

    raw = movement.plan_move(
        entity,
        (3, 0),
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
        correct_to_budget=True,
    )
    assert raw.success is False
    assert raw.response["reason"] == "no_path"

    corrected = movement.plan_move(
        entity,
        (3, 0),
        policy=MovementPlanningPolicy.STRESS_STACK_ENDPOINT,
        correct_to_budget=True,
        correct_unreachable=True,
    )
    assert corrected.success is True
    assert corrected.plan is not None
    assert corrected.plan.requested_target == (3, 0)
    assert corrected.plan.resolved_target == (1, 0)
    assert corrected.plan.path == ((0, 0), (1, 0))
    assert corrected.plan.cost == 1
    assert corrected.plan.corrected is True
    assert corrected.plan.correction_reason == "unreachable"


def test_start_prepared_motion_has_no_resource_side_effects():
    world, entity, movement = _world_with_unit(mp=3)
    movement_points = world.get_component(entity, MovementPoints)

    result = movement.start_prepared_motion(entity, ((0, 0), (1, 0), (2, 0)))

    assert result["success"] is True
    assert result["animated"] is False
    assert movement_points.current_mp == 3
    pos = world.get_component(entity, HexPosition)
    assert (pos.col, pos.row) == (2, 0)


def test_sustained_path_expands_forward_and_backward_without_replanning():
    world, entity, movement = _world_with_unit(mp=3)
    harness = ScaleHarnessSystem(movement, "/tmp/star-scale-test.sock")
    harness.world = world

    expanded = harness._build_sustained_path(
        entity,
        ((0, 0), (1, 0), (2, 0)),
        duration_seconds=2.0,
    )

    # Default MovementAnimation speed is 2 tiles/s -> four scheduled segments.
    assert expanded == ((0, 0), (1, 0), (2, 0), (1, 0), (0, 0))


def test_execute_rejects_stale_prepared_plan(monkeypatch):
    world, entity, movement = _world_with_unit(mp=3)
    monkeypatch.setattr(
        movement,
        "_planning_context",
        lambda *_args, **_kwargs: _context(
            costs={(1, 0): 1}, walkable={(0, 0), (1, 0)}
        ),
    )
    planned = movement.plan_move(entity, (1, 0))
    assert planned.success and planned.plan is not None

    pos = world.get_component(entity, HexPosition)
    pos.col = 9
    result = movement.execute_move_plan(planned.plan, emit_log=False)
    assert result["success"] is False
    assert result["reason"] == "stale_move_plan"


def test_planning_snapshot_reuses_shared_containers_without_copy():
    _world, entity, movement = _world_with_unit(mp=3)
    occupied = frozenset({(4, 4), (5, 5)})
    blockers = frozenset({(8, 8)})
    walkable = frozenset({(0, 0), (1, 0), (4, 4), (5, 5), (8, 8)})
    costs = {(0, 0): 1, (1, 0): 1}
    snapshot = MovementPlanningSnapshot(
        walkable=walkable,
        terrain_costs=costs,
        occupied=occupied,
        blockers_by_faction={Faction.WEI: blockers},
        revision=11,
    )

    got_occupied, got_blockers, got_costs, got_walkable, revision = (
        movement._planning_context(entity, Faction.WEI, snapshot)
    )

    assert got_occupied is occupied
    assert got_blockers is blockers
    assert got_costs is costs
    assert got_walkable is walkable
    assert revision == 11
