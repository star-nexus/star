"""Selected panels preserve shared intelligence and the live legality oracle."""
import pytest

from rotk_env.components import ActionPoints, FogOfWar, GameStats, HexPosition, TeamCoordination, UnitCount
from rotk_env.prefabs.config import Faction
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.tests.test_faction_state_affordances import _world, _spawn
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index, update_unit_spatial_index, remove_unit_from_spatial_index


def setup_world():
    world = _world()
    a = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=3)
    b = _spawn(world, faction=Faction.WEI, col=-1, row=0, mp=3)
    enemy = _spawn(world, faction=Faction.SHU, col=1, row=0, mp=3)
    world.get_singleton_component(FogOfWar).faction_vision[Faction.WEI] = {(0, 0), (-1, 0), (1, 0)}
    world.get_singleton_component(GameStats).agent_id_to_faction = {'a':Faction.WEI, 'b':Faction.WEI}
    coord = TeamCoordination()
    world.add_singleton_component(coord)
    coord.claim_units('a', [a, b])
    return world, a, b, enemy


def test_selected_panels_are_exact_projection_and_shared_channels_stay_complete():
    world, a, b, enemy = setup_world()
    h = LLMActionHandler(world)
    whole = h.handle_faction_state({'faction':'wei', 'agent_id':'a'})
    selected = h.handle_faction_state({'faction':'wei', 'agent_id':'a', 'unit_ids':[b, b]})
    assert selected['units'] == [next(u for u in whole['units'] if u['unit_id']==b)]
    assert {k:v for k,v in selected.items() if k!='units'} == {k:v for k,v in whole.items() if k!='units'}
    empty = h.handle_faction_state({'faction':'wei', 'agent_id':'a', 'unit_ids':[]})
    assert empty['units'] == [] and empty['visible_enemy_units'] == whole['visible_enemy_units']


@pytest.mark.parametrize('ids', [None, 'all', [True], [1.0], [999999]])
def test_invalid_selection_is_rejected(ids):
    world, *_ = setup_world()
    assert not LLMActionHandler(world).handle_faction_state({'faction':'wei', 'unit_ids':ids})['success']


def test_enemy_selection_is_rejected_and_teammate_reads_do_not_gain_control():
    world, a, b, enemy = setup_world()
    h = LLMActionHandler(world)
    assert not h.handle_faction_state({'faction':'wei', 'agent_id':'a', 'unit_ids':[a, enemy]})['success']
    peer = h.handle_faction_state({'faction':'wei', 'agent_id':'b', 'unit_ids':[a]})
    assert peer['units'][0]['commandable'] is False
    world.get_singleton_component(TeamCoordination).claim_units('b', [a], exclusive=False)
    assert h.handle_faction_state({'faction':'wei', 'agent_id':'b', 'unit_ids':[a]})['units'][0]['commandable'] is True


def test_indexed_masks_equal_scan_after_moves_colocation_ap_fog_and_removal():
    world, a, b, enemy = setup_world()
    h = LLMActionHandler(world)

    def compare():
        index = getattr(world, '_unit_spatial_index', None)
        world._unit_spatial_index = None
        reference = h.handle_faction_state({'faction':'wei', 'agent_id':'a'})
        world._unit_spatial_index = index
        if index is None:
            rebuild_unit_spatial_index(world)
        actual = h.handle_faction_state({'faction':'wei', 'agent_id':'a'})
        assert actual == reference
        return actual

    compare()
    # Same-cell enemies are legal targets; exclude only the mover, not its stack.
    world.get_component(enemy, HexPosition).col = 0
    update_unit_spatial_index(world, enemy)
    result = compare()
    own = next(u for u in result['units'] if u['unit_id']==a)
    assert enemy in own['attackable']
    assert {'col':0, 'row':0} not in own['reachable']
    world.get_component(a, ActionPoints).current_ap = 0
    compare()
    world.get_singleton_component(FogOfWar).faction_vision[Faction.WEI].clear()
    assert not compare()['visible_enemy_units']
    world.get_singleton_component(FogOfWar).enabled = False
    assert compare()['visible_enemy_units']
    remove_unit_from_spatial_index(world, enemy)
    world.destroy_entity(enemy)
    compare()


def test_selected_unit_death_and_component_replacement_are_immediate():
    world, a, *_ = setup_world()
    h = LLMActionHandler(world)
    params = {'faction':'wei', 'agent_id':'a', 'unit_ids':[a]}
    assert h.handle_faction_state(params)['units']
    world.add_component(a, UnitCount(current_count=0, max_count=100))
    assert h.handle_faction_state(params)['units'] == []
    world.add_component(a, UnitCount(current_count=80, max_count=100))
    assert h.handle_faction_state(params)['units'][0]['unit_status']['current_count'] == 80


def test_selected_panel_catalog_survives_reference_client_schema_conversion():
    from rotk_env.prefabs.action_catalog import GAME_ACTIONS
    from rotk_agent.core.tools import _env_params_to_json_schema
    import jsonschema

    spec = next(s for s in GAME_ACTIONS if s.name == 'get_faction_state')
    schema = _env_params_to_json_schema(spec.parameters, 'observation')
    assert schema['properties']['unit_ids']['items']['type'] == 'integer'
    jsonschema.validate({'faction':'wei'}, schema)
    jsonschema.validate({'faction':'wei', 'unit_ids':[1, 2]}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'faction':'wei', 'unit_ids':['1']}, schema)
