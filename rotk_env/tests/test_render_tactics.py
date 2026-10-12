"""Range hints reuse pure queries, respect visibility and never mutate authority."""
from copy import deepcopy

import pytest
pytest.importorskip('star_rust_runtime')
from rotk_env import components as c
from rotk_env.runtime.session import NativeSession
from rotk_env.utils.hex_utils import HexMath
from rotk_env.utils.map_query import reachable_hexes
from rotk_env.tests.render_fixtures import frozen


@pytest.fixture
def scene(frozen):
    with NativeSession(renderer='web', scenario='chibi-small', seed=42) as scene:
        yield scene


def selected(model, view='spectator', uid=None):
    snapshot = model.snapshot(view)
    uid = uid or next(u['id'] for u in snapshot['units'] if u['faction'] == 'wei')
    return model.with_selection(snapshot, uid)['selection']


def test_full_view_matches_existing_mp_budget_path_and_attack_queries_without_authority_writes(scene):
    model = scene.renderer.model
    before = scene.runtime.export_state()
    ranges = selected(model)
    uid = int(ranges['unit_id'])
    mp = scene.world.get_component(uid, c.MovementPoints)
    count = scene.world.get_component(uid, c.UnitCount)
    origin = tuple(ranges['origin'])
    expected = reachable_hexes(scene.world, origin, mp.spendable(count), mover=uid) - {origin}
    assert {tuple(p) for p in ranges['movement']} == expected
    combat = scene.world.get_component(uid, c.Combat)
    board = set(scene.world.get_singleton_component(c.MapData).tiles)
    assert {tuple(p) for p in ranges['attack']} == HexMath.hex_in_range(*origin, combat.attack_range) & board - {origin}
    assert scene.runtime.export_state() == before


def test_ranges_refresh_for_mp_headcount_moving_and_committed_hex(scene):
    model = scene.renderer.model
    ranges = selected(model); raw = model.units[ranges['unit_id']]
    raw['movement_points'].update(current_mp=0)
    assert selected(model)['movement'] == []
    raw['movement_points'].update(current_mp=3, base_mp=3, has_moved=False)
    assert selected(model)['movement']
    raw['movement_points']['has_moved'] = True
    assert selected(model)['movement'] == []
    raw['movement_points']['has_moved'] = False
    raw['position'].update(col=0, row=0)
    assert selected(model)['origin'] == [0, 0]
    raw['position'].update(col=ranges['origin'][0], row=ranges['origin'][1])
    raw['count'].update(current_count=10)
    reduced = selected(model)['movement']
    raw['count'].update(current_count=100)
    assert len(selected(model)['movement']) > len(reduced)
    raw['movement'] = {**(raw['movement'] or {}), 'is_moving': True,
                       'start_pixel_pos': None, 'target_pixel_pos': None}
    assert selected(model)['movement'] == []


def test_authorized_hints_do_not_expose_hidden_tiles_units_or_enemy_private_ranges(scene):
    model = scene.renderer.model
    snapshot = model.snapshot('wei')
    uid = snapshot['units'][0]['id']
    hints = model.with_selection(snapshot, uid)['selection']
    known = {(t['col'], t['row']) for t in snapshot['tiles'] if t['visibility'] != 'hidden'}
    assert all(tuple(pos) in known for key in ('movement', 'attack') for pos in hints[key])
    assert set(hints['targets']) <= {u['id'] for u in snapshot['units'] if u['faction'] != 'wei'}
    secret_id, secret = next((uid, u) for uid, u in model.units.items() if u['unit']['faction'] == 'shu')
    assert model.with_selection(snapshot, secret_id)['selection'] is None
    # Changing a secret's resources and occupancy cannot change the same view's hints.
    secret['movement_points']['current_mp'] = 0
    hidden = next(t for t in snapshot['tiles'] if t['visibility'] == 'hidden')
    secret['position'].update(col=hidden['col'], row=hidden['row'])
    assert selected(model, 'wei', uid) == hints
    forged = deepcopy(snapshot)
    forged['units'].append(dict(id=secret_id, faction='shu'))
    assert model.with_selection(forged, secret_id)['selection'] is None


def test_range_cache_and_owned_results_clear_selection_and_removed_units(scene):
    model = scene.renderer.model
    original = selected(model)
    computations = model.tactics.computations
    for _ in range(100):
        assert selected(model) == original
    assert model.tactics.computations == computations
    damaged = selected(model); damaged['movement'].clear(); damaged['targets'].append('secret')
    assert selected(model) == original
    snapshot = model.snapshot('wei')
    assert model.with_selection(snapshot, None)['selection'] is None
    snapshot['units'].clear()
    assert model.with_selection(snapshot, original['unit_id'])['selection'] is None


def test_visible_enemy_targets_use_decimal_ids_and_disappear_with_visibility(scene):
    model = scene.renderer.model
    own = selected(model, 'wei')
    cell = tuple(own['attack'][0]); model.visible['wei'].add(cell)
    enemy = deepcopy(next(u for u in model.units.values() if u['unit']['faction'] == 'shu'))
    uid = str(2**63 + 11); enemy['id'] = int(uid)
    enemy['position'].update(col=cell[0], row=cell[1]); model.units[uid] = enemy
    hints = selected(model, 'wei', own['unit_id'])
    assert uid in hints['targets'] and list(cell) not in hints['movement']
    model.visible['wei'].discard(cell)
    assert uid not in selected(model, 'wei', own['unit_id'])['targets']
