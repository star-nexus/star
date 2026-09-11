"""Externally visible ordering and path ties form the normalized oracle contract."""

from rotk_env.components import TeamCoordination
from rotk_env.prefabs.config import Faction
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.tests.test_faction_state_affordances import _world, _spawn
from rotk_env.utils.hex_utils import HexMath, PathFinding


def test_faction_lists_use_ids_and_explicit_selection_keeps_request_order():
    world = _world()
    world.entity_counter = 61
    own = [_spawn(world, faction=Faction.WEI, col=0, row=0) for _ in range(4)]
    enemies = [_spawn(world, faction=Faction.SHU, col=1, row=0) for _ in range(4)]
    from rotk_env.components import FogOfWar
    world.get_singleton_component(FogOfWar).enabled = False
    handler = LLMActionHandler(world)
    response = handler.handle_faction_state({'faction': 'wei'})
    assert [u['unit_id'] for u in response['units']] == own
    assert [u['unit_id'] for u in response['visible_enemy_units']] == enemies
    selected = handler.handle_faction_state({'faction': 'wei', 'unit_ids': [own[-1], own[0], own[-1]]})
    assert [u['unit_id'] for u in selected['units']] == [own[-1], own[0]]


def test_release_all_orders_ids_but_explicit_release_preserves_order():
    team = TeamCoordination()
    team.claim_units('a', [65, 63, 64])
    assert team.release_units('a')['released'] == [63, 64, 65]
    team.claim_units('a', [65, 63, 64])
    assert team.release_units('a', [65, 63])['released'] == [65, 63]


def test_equal_cost_paths_are_independent_of_board_and_obstacle_insertion():
    cells = [(c, r) for c in range(-3, 4) for r in range(-3, 4)]
    obstacles = [(0, 0), (0, 1)]
    expected = PathFinding.find_path((-2, 0), (2, 0), set(obstacles), walkable=set(cells))
    assert expected
    for reverse in (False, True):
        actual = PathFinding.find_path((-2, 0), (2, 0), set(obstacles[:: -1 if reverse else 1]),
                                       walkable=set(cells[:: -1 if reverse else 1]))
        assert actual == expected
    assert all(b in HexMath.hex_neighbors(*a) for a, b in zip(expected, expected[1:]))
