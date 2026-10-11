import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DisplayState, canEndTurn} from '../state.js';
import {hexToWorld, mapBounds, fitExtent} from '../hex.js';

const baseline = () => ({schema: 1, kind: 'snapshot', sequence: 4, epoch: '1', view: 'wei',
  scene: {map_id: 'test'}, units: [{id: '9223372036854775819', ap: 2}, {id: '2', ap: 1}],
  tiles: [{id: '0', owner: 'wei'}], hud: {mode: 'turn_based', current_player: 'wei', game_over: false}});

test('display updates preserve decimal u64 IDs and reject gaps or old epochs', () => {
  const state = new DisplayState(); const input = baseline();
  assert.ok(state.apply(input)); input.units.length = 0; assert.equal(state.snapshot.units.length, 2);
  const delta = {schema: 1, kind: 'delta', epoch: '1', view: 'wei', base_sequence: 4, sequence: 5,
    units: [{id: '9223372036854775819', ap: 0}], tiles: [], removed: ['2']};
  assert.ok(state.apply(delta)); assert.deepEqual(state.snapshot.units, [{id: '9223372036854775819', ap: 0}]);
  assert.equal(state.apply({...delta, base_sequence: 9}), false);
  assert.equal(state.apply({...delta, epoch: '2'}), false);
  assert.equal(state.snapshot.sequence, 5);
  assert.ok(state.apply({...baseline(), epoch: '2'})); state.clear(); assert.equal(state.snapshot, null);
});

test('Space and button eligibility uses the granted view and game mode', () => {
  const s = baseline(); assert.ok(canEndTurn(s, true)); assert.equal(canEndTurn(s, false), false);
  s.hud.current_player = 'shu'; assert.equal(canEndTurn(s, true), false);
  s.hud.current_player = 'wei'; s.hud.mode = 'real_time'; assert.equal(canEndTurn(s, true), false);
  s.hud.mode = 'turn_based'; s.hud.game_over = true; assert.equal(canEndTurn(s, true), false);
  s.hud.game_over = false; s.scene.commands = []; assert.equal(canEndTurn(s, true), false);
});

test('STAR offset coordinates include negative odd rows and fit without cropping', () => {
  assert.deepEqual(hexToWorld(-1, 0), [-1.5, Math.sqrt(3)/2]);
  assert.deepEqual(hexToWorld(0, -1, 'pointy'), [Math.sqrt(3)/2, -1.5]);
  const bounds = mapBounds([{col: -7, row: -7}, {col: 7, row: 7}], 'flat');
  for (const aspect of [.5, 1, 2]) {
    const fit = fitExtent(bounds, aspect);
    assert.ok(fit.width >= bounds.maxX-bounds.minX && fit.height >= bounds.maxY-bounds.minY);
    assert.ok(Math.abs(fit.width/fit.height - aspect) < 1e-9);
  }
});
