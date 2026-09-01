from framework.ecs.world import World

from rotk_env.components import HexPosition, MovementPoints, Unit, UnitCount, UnitStatus
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.movement_planning import MovementPlanningPolicy
from rotk_env.systems.movement_system import MovementSystem


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
    pos = world.get_component(entity, HexPosition)
    assert (pos.col, pos.row) == (0, 0)
    assert world.get_component(entity, MovementPoints).current_mp == 3

    result = movement.execute_move_plan(planned.plan, emit_log=False)
    assert result["success"] is True
    assert result["to"] == (2, 0)
    assert world.get_component(entity, MovementPoints).current_mp == 1
    pos = world.get_component(entity, HexPosition)
    assert (pos.col, pos.row) == (2, 0)


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
