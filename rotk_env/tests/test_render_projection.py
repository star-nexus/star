"""Authorized display views are owned, visibility-complete and read-only."""
from copy import deepcopy

import pytest
pytest.importorskip('star_native')

from rotk_env.runtime.session import NativeSession
from rotk_env.rendering.projection import diff_snapshot
from rotk_env.tests.test_native_request_batch import frozen


@pytest.fixture
def scene(frozen):
    with NativeSession(renderer='web', scenario='chibi-small', seed=42) as s:
        yield s


def publication(model):
    return dict(epoch=model.epoch, revision=model.revision+1, tick=model.tick,
        units=[], removed=[], tiles=[], state={},
        fog=dict(full=False, enabled=True, factions=[]), visuals=dict(rows=[], removed=[]))


def cell_delta(faction, pos, *, visible, explored=True):
    return dict(faction=faction, cells=[dict(col=pos[0], row=pos[1], visible=visible, explored=explored)])


def test_views_omit_hidden_units_resources_and_terrain_without_mutating_authority(scene):
    model = scene.renderer.model
    before = scene.runtime.export_state()
    wei = model.snapshot('wei')
    assert all(u['faction'] == 'wei' for u in wei['units'])
    assert all('ap' in u for u in wei['units'])
    hidden = [t for t in wei['tiles'] if t['visibility'] == 'hidden']
    assert hidden and all(t['asset'] is None and t['terrain'] is None and t['owner'] is None for t in hidden)
    assert len(model.snapshot()['units']) == 10
    wei['units'][0]['position'][0] = 999
    wei['scene']['tiles'].clear()
    assert model.snapshot('wei')['units'][0]['position'][0] != 999
    assert scene.runtime.export_state() == before


def test_visibility_only_change_emits_unit_birth_removal_and_keeps_enemy_ap_private(scene):
    m = scene.renderer.model
    enemy = next(row for row in m.units.values() if row['unit']['faction'] == 'shu')
    pos = (enemy['position']['col'], enemy['position']['row'])
    before = m.snapshot('wei')
    delta = publication(m); delta['fog']['enabled'] = False  # Desktop paint toggle isn't a remote grant.
    delta['fog']['factions'] = [cell_delta('wei', pos, visible=True)]
    m.apply(delta)
    current = m.snapshot('wei'); packet = diff_snapshot(before, current)
    unit = next(u for u in packet['units'] if u['id'] == str(enemy['id']))
    assert 'ap' not in unit and 'mp' not in unit
    delta = publication(m); delta['fog']['factions'] = [cell_delta('wei', pos, visible=False)]
    m.apply(delta)
    packet = diff_snapshot(current, m.snapshot('wei'))
    assert str(enemy['id']) in packet['removed']
    assert str(enemy['id']) not in {u['id'] for u in m.snapshot('wei')['units']}


def test_hidden_territory_change_does_not_leak_into_last_seen_tiles(scene):
    m = scene.renderer.model
    uid = next(uid for uid, tile in m.tiles.items() if (tile['col'], tile['row']) in m.visible['wei'])
    tile = m.tiles[uid]; pos = (tile['col'], tile['row'])
    old_owner = next(t for t in m.snapshot('wei')['tiles'] if t['id'] == uid)['owner']
    delta = publication(m); delta['fog']['factions'] = [cell_delta('wei', pos, visible=False)]
    m.apply(delta)
    delta = publication(m); delta['tiles'] = [dict(id=int(uid), control=dict(controlling_faction='wu', fortified=True))]
    m.apply(delta)
    remembered = next(t for t in m.snapshot('wei')['tiles'] if t['id'] == uid)
    assert remembered['visibility'] == 'explored' and remembered['owner'] == old_owner
    assert next(t for t in m.snapshot()['tiles'] if t['id'] == uid)['owner'] == 'wu'
    delta = publication(m); delta['fog']['factions'] = [cell_delta('wei', pos, visible=True)]
    m.apply(delta)
    assert next(t for t in m.snapshot('wei')['tiles'] if t['id'] == uid)['owner'] == 'wu'


def test_epoch_stale_publication_and_u64_ids(scene):
    m = scene.renderer.model
    row = deepcopy(next(iter(m.units.values()))); row['id'] = 2**63+11
    delta = publication(m); delta['units'] = [row]; m.apply(delta)
    assert str(2**63+11) in {u['id'] for u in m.snapshot('wei')['units']}
    delta['revision'] = m.revision-1
    with pytest.raises(ValueError, match='Stale'): m.apply(delta)
    delta['epoch'] += 1
    with pytest.raises(ValueError, match='epoch'): m.apply(delta)


def test_view_delta_reconstructs_current_snapshot(scene):
    m = scene.renderer.model; before = m.snapshot('wei')
    scene.step(.1); current = m.snapshot('wei')
    packet = diff_snapshot(before, current)
    assert packet['base_sequence'] == before['sequence']
    result = {**before, **packet, 'kind': 'snapshot'}
    for key in ('units', 'tiles'):
        rows = {r['id']: r for r in before[key]}
        if key == 'units':
            for uid in packet['removed']: rows.pop(uid, None)
        rows.update({r['id']: r for r in packet[key]}); result[key] = list(rows.values())
    result.pop('base_sequence'); result.pop('removed')
    assert result == current


def test_web_frame_provider_explicitly_unavailable_and_adapter_does_not_simulate(scene):
    before = scene.runtime.export_state()
    assert scene.frame_provider.capture() == (None, 'Web renderer does not provide Agent observation frames')
    scene.update_display(123)
    assert scene.runtime.export_state() == before


def test_native_visual_lifecycle_translates_without_pixel_or_entity_aliases(frozen):
    from rotk_env.tests.test_native_combat_presentation import make
    from rotk_env.runtime.bootstrap import export_initial_state
    from rotk_env.runtime.native import RustRuntime
    from rotk_env.rendering.projection import RenderProjection
    from rotk_env.prefabs.config import GameMode
    world, (attacker, _, target), _ = make('dummy', GameMode.REAL_TIME, 'ranged', critical=True)
    try:
        initial = export_initial_state(world, display='dummy'); model = RenderProjection(world, initial)
        with RustRuntime(initial) as runtime:
            model.apply(runtime.take_presentation_delta())
            assert runtime.execute_control('attack', unit_id=attacker, target_id=target)
            model.apply(runtime.take_presentation_delta())
            kinds = {row['kind'] for row in model.snapshot()['visuals']}
            assert {'attack', 'damage', 'effect'} <= kinds
            for dt in (.2, .2, 1, 3):
                runtime.step(dt); model.apply(runtime.take_presentation_delta())
            assert model.snapshot()['visuals'] == []
    finally:
        world.reset()
