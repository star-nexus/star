"""Three factions reuse base facts without retaining live component references."""
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env import components as c
from rotk_env.prefabs.config import Faction,TerrainType
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.tests.test_native_observation import setup
from rotk_env.tests.test_faction_state_affordances import _spawn


@pytest.mark.parametrize('threads',[1,2,4])
def test_public_facts_share_across_factions_and_are_rebuilt_on_reset(threads):
    world,(_,_,enemy),_=setup('none')
    _spawn(world,faction=Faction.WU,col=0,row=2)
    world.get_singleton_component(c.FogOfWar).enabled=False
    params=[dict(faction=f,unit_ids=[]) for f in ('wei','shu','wu','wei')]
    def expected():return [LLMActionHandler(world).handle_faction_state(p) for p in params]
    wire=json.dumps(params);n=NativeRuntime(json.dumps(export_initial_state(world)),threads)
    try:
        old=n._observation_probe_json(wire);report=json.loads(old);before=expected()
        assert report['results']==before
        assert report['metrics']['faction_builds']==3
        assert report['metrics']['enemy_builds']==4  # unique Units, not six faction projections
        tiles=world.get_singleton_component(c.MapData).tiles
        # The oracle excludes the mapped tile with external ID zero.
        assert report['metrics']['tile_builds']==len(before[0]['visible_terrain'])
        world.get_component(enemy,c.UnitCount).current_count=17
        world.get_component(tiles[(0,0)],c.Terrain).terrain_type=TerrainType.FOREST
        n.reset(json.dumps(export_initial_state(world)))
        current=json.loads(n._observation_probe_json(wire))['results']
        assert current==expected() and current!=before
        n.close();assert json.loads(old)['results']==before
    finally:n.close();world.reset()
