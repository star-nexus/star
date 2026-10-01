"""E6: live component fields, independent ownership and identical error prefixes."""
from copy import deepcopy
from dataclasses import fields
import ast
from pathlib import Path
import subprocess
import pytest
from framework import World
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, UnitType, UnitState
from rotk_env.runtime.bootstrap import encode
from rotk_env.runtime.world_presentation import WorldPresentation, _UNIT_COLUMNS
from rotk_env.utils.unit_spatial_index import get_unit_spatial_index

MODES = ('baseline', 'reuse_constructed', 'reuse_typed')


def delta(revision=0):
    row = dict(id=10)
    for key, cls in _UNIT_COLUMNS.items():
        value = cls(0, 0) if cls is c.HexPosition else (
            cls(UnitType.INFANTRY, Faction.WEI) if cls is c.Unit else cls())
        row[key] = encode(value)
    row['movement']['path'] = [[0, 0], [1, 0]]
    row['skill_points']['skill_cooldowns'] = {'dash': 2}
    return dict(epoch=1, revision=revision, removed=[], units=[row], tiles=[], state={},
                players=dict(full=True, rows=[], units_removed=[]),
                fog=dict(full=True, enabled=None, factions=[]),
                visuals=dict(removed=[], rows=[]), events=[{'values': [1, 2]}])


def state(p):
    w = p.world
    return (p.epoch, p.revision, w.revision, w.entity_counter,
            [(e, [(t.__name__, encode(v)) for t, v in sorted(cs.items(), key=lambda x:x[0].__name__)])
             for e, cs in sorted(w.entities.items())],
            [(t.__name__, encode(v)) for t, v in sorted(w._singleton_components.items(), key=lambda x:x[0].__name__)],
            dict(get_unit_spatial_index(w).by_entity))


@pytest.mark.parametrize('mode', MODES)
def test_complete_owned_fields_and_live_references(mode):
    p = WorldPresentation(World()); d = delta(); before = deepcopy(d)
    p._apply_research(d, mode=mode)
    held = {t:p.world.get_component(10,t) for t in _UNIT_COLUMNS.values()}
    versions = {t:p.world.component_reference_version(t) for t in held}
    query = p.world.query().with_all(c.Unit, c.HexPosition).ordered_entities()
    d = delta(1); d['units'][0]['position']['col'] = 2
    d['units'][0]['unit']['faction'] = 'wu'
    d['units'][0]['status']['current_status'] = UnitState.NORMAL.value
    d['units'][0]['status']['current_status_is_enum'] = True
    untouched = deepcopy(d); events=p._apply_research(d, mode=mode)
    assert d == untouched
    assert p.world.query().with_all(c.Unit, c.HexPosition).ordered_entities() == query
    assert p.world.get_component(10,c.Unit).faction is Faction.WU
    assert p.world.get_component(10,c.UnitStatus).current_status is UnitState.NORMAL
    for cls, old in held.items():
        assert (p.world.get_component(10,cls) is old) == (mode != 'baseline')
        assert (p.world.component_reference_version(cls) == versions[cls]) == (mode != 'baseline')
    d['units'][0]['movement']['path'][0][0] = 900
    d['units'][0]['skill_points']['skill_cooldowns']['dash'] = 900
    events[0]['values'].append(900)
    assert p.world.get_component(10,c.MovementAnimation).path[0] == (0,0)
    assert p.world.get_component(10,c.SkillPoints).skill_cooldowns['dash'] == 2
    assert d['events'][0]['values'] == [1,2]
    assert before == delta()


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('change', ('missing','unknown','bad_enum','bad_path','nested_cooldown','remove','extension','delete'))
def test_fallbacks_errors_and_successful_prefix_equal_baseline(mode, change):
    a=WorldPresentation(World()); b=WorldPresentation(World())
    for p in (a,b): p.apply(delta())
    d=delta(1); row=d['units'][0]
    row['position']['col']=7
    if change=='missing': row['unit'].pop('name')
    elif change=='unknown': row['count']['unknown']=1
    elif change=='bad_enum': row['unit']['faction']='invalid'
    elif change=='bad_path': row['movement']['path']=[42]
    elif change=='nested_cooldown': row['skill_points']['skill_cooldowns']={'nested': {'x':[1]}}
    elif change=='remove': row['count']=None
    elif change=='extension':
        for p in (a,b): p.world.get_component(10,c.Unit).extension=[1]
    elif change=='delete': d['removed']=[10];d['units']=[]
    outcomes=[]
    for p,m in ((a,'baseline'),(b,mode)):
        try: outcomes.append(('ok',p._apply_research(deepcopy(d),mode=m)))
        except Exception as exc: outcomes.append((type(exc).__name__,str(exc)))
    assert outcomes[0] == outcomes[1]
    assert state(a) == state(b)
    for cls in _UNIT_COLUMNS.values():
        assert a.world.query().with_component(cls).ordered_entities() == b.world.query().with_component(cls).ordered_entities()
        assert a.world.query().without_component(cls).ordered_entities() == b.world.query().without_component(cls).ordered_entities()


@pytest.mark.parametrize('mode', MODES)
def test_rejection_lifecycle_and_independent_instances(mode):
    a=WorldPresentation(World()); b=WorldPresentation(World())
    a._apply_research(delta(),mode=mode); b._apply_research(delta(),mode=mode)
    before=state(a)
    for d in (dict(delta(),epoch=2),dict(delta(),revision=-1)):
        with pytest.raises(ValueError): a._apply_research(d,mode=mode)
        assert state(a)==before
    with pytest.raises(ValueError): a._apply_research(delta(1),mode='invalid')
    assert state(a)==before
    a.world.get_component(10,c.UnitCount).current_count=1
    assert b.world.get_component(10,c.UnitCount).current_count==100
    a.world.reset();a=WorldPresentation(a.world)
    a._apply_research(dict(delta(),epoch=2),mode=mode)
    assert a.epoch==2


def test_ordinary_apply_ast_unchanged_from_e6_base():
    path='rotk_env/runtime/world_presentation.py'
    old=subprocess.check_output(['git','show','4657dd4:'+path],text=True)
    new=Path(path).read_text()
    def body(source):
        cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='WorldPresentation')
        return ast.dump(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='apply'),include_attributes=False)
    assert body(old)==body(new)
