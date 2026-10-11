import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {InstanceBatches} from '../batches.js';
import {UnitMotion} from '../motion.js';
import {DisplayState} from '../state.js';
import {BattlefieldRenderer} from '../renderer.js';

const options = {asset: r => r.asset, position: r => r.position, color: r => r.color || '#ffffff', z: .2};
const unit = (id, x = 0, asset = 'infantry') => ({id, asset, position: [x, 0]});

test('100 display packets reuse meshes and unchanged GPU buffers; motion patches only its batch', () => {
  const group = new THREE.Group(), geometry = new THREE.PlaneGeometry(), material = new THREE.MeshBasicMaterial();
  let allocations = 0;
  const batches = new InstanceBatches(group, geometry, () => material, () => allocations++);
  const rows = [unit('1'), unit('2', 1), unit('3', 2, 'archer')];
  batches.sync(rows, options);
  const original = [...group.children], versions = original.map(m => m.instanceMatrix.version);
  for (let i = 0; i < 100; i++) batches.sync(structuredClone(rows), options);
  assert.equal(allocations, 2); assert.deepEqual(group.children, original);
  assert.deepEqual(original.map(m => m.instanceMatrix.version), versions);
  rows[0].position = [.5, 0]; batches.move(rows, .2);
  assert.equal(original[0].instanceMatrix.version, versions[0] + 1);
  assert.equal(original[1].instanceMatrix.version, versions[1]);
  const matrix = new THREE.Matrix4(); original[0].getMatrixAt(0, matrix);
  assert.equal(matrix.elements[12], .5);
  assert.equal(original[0].userData.rows[0].id, '1');
  batches.close(); assert.equal(group.children.length, 0);
  geometry.dispose(); material.dispose();
});

test('visibility removals update instance count and raycast IDs without stale units; capacity grows only when needed', () => {
  const group = new THREE.Group(), geometry = new THREE.PlaneGeometry(), material = new THREE.MeshBasicMaterial();
  let created = 0, disposed = 0;
  const batches = new InstanceBatches(group, geometry, () => material, () => created++);
  batches.sync([unit('a'), unit('b')], options);
  const mesh = group.children[0]; mesh.addEventListener('dispose', () => disposed++);
  batches.sync([unit('b', 1)], options);
  assert.equal(mesh.count, 1); assert.equal(mesh.userData.rows[0].id, 'b');
  assert.equal(batches.slots.has('a'), false); assert.equal(created, 1);
  batches.sync([unit('b'), unit('c'), unit('d')], options);
  assert.equal(created, 2); assert.equal(disposed, 1); assert.equal(group.children[0].instanceMatrix.count, 4);
  const grown = group.children[0]; batches.sync([unit('b'), unit('c'), unit('d'), unit('e')], options);
  assert.equal(group.children[0], grown);
  batches.sync([], options); assert.equal(group.children.length, 0); batches.close();
  geometry.dispose(); material.dispose();
});

test('authoritative poses at 20 Hz yield intermediate animation frames without mutating state or overshooting', () => {
  const motion = new UnitMotion(), initial = [unit('1')];
  motion.update(initial, 0, true);
  const next = [unit('1', 1)]; motion.update(next, 50);
  assert.equal(motion.records.get('1').position[0], 0);
  for (const [time, x] of [[60, .2], [75, .5], [90, .8], [100, 1], [1000, 1]]) {
    motion.step(time); assert.equal(motion.records.get('1').position[0], x);
  }
  assert.deepEqual(initial[0].position, [0, 0]); assert.deepEqual(next[0].position, [1, 0]);
});

test('retargeting stays continuous; hidden/dead units disappear immediately; baselines and stalls snap', () => {
  const motion = new UnitMotion(); motion.update([unit('1')], 0);
  motion.update([unit('1', 1)], 50); motion.step(75);
  motion.update([unit('1', 2)], 75); assert.equal(motion.records.get('1').position[0], .5);
  motion.step(87.5); assert.equal(motion.records.get('1').position[0], 1.25);
  motion.update([], 90); assert.equal(motion.active.size, 0); assert.equal(motion.records.size, 0);
  motion.update([unit('1', 10)], 100, true); assert.equal(motion.rows[0].position[0], 10);
  motion.update([unit('1', 20)], 1000); assert.equal(motion.rows[0].position[0], 20);
  motion.update([unit('1', 30)], 1010, true); assert.equal(motion.rows[0].position[0], 30);
});

test('empty deltas retain terrain and unit arrays for incremental rendering, changed rows remain owned', () => {
  const state = new DisplayState();
  state.apply({schema: 1, kind: 'snapshot', sequence: 1, epoch: '1', view: 'wei', units: [unit('1')], tiles: [{id: 'tile'}]});
  const {units, tiles} = state.snapshot;
  const delta = {schema: 1, kind: 'delta', base_sequence: 1, sequence: 2, epoch: '1', view: 'wei', units: [], tiles: []};
  assert.ok(state.apply(delta)); assert.equal(state.snapshot.units, units); assert.equal(state.snapshot.tiles, tiles);
  const row = unit('1', 1);
  assert.ok(state.apply({...delta, base_sequence: 2, sequence: 3, units: [row]}));
  row.position[0] = 999; assert.equal(state.snapshot.units[0].position[0], 1); assert.equal(state.snapshot.tiles, tiles);
});

test('attack and projectile effects retain GPU resources until their visible lifetime ends', () => {
  const renderer = Object.create(BattlefieldRenderer.prototype);
  Object.assign(renderer, {effects: new THREE.Group(), effectObjects: new Map(), effectLabels: new Map(),
    effectMotion: new UnitMotion(), markerGeometry: new THREE.CircleGeometry(.1),
    markerMaterial: new THREE.MeshBasicMaterial()});
  const rows = [{id: 'attack:1', kind: 'attack', position: [0, 0], target: [1, 0], progress: .1},
    {id: 'projectile:2', kind: 'projectile', position: [0, 0]}];
  renderer.updateEffects(rows, true);
  const line = renderer.effectObjects.get('attack:1'), marker = renderer.effectObjects.get('projectile:2');
  let disposed = 0; line.geometry.addEventListener('dispose', () => disposed++);
  marker.material.addEventListener('dispose', () => disposed++);
  for (let i = 0; i < 20; i++) renderer.updateEffects(rows);
  assert.equal(renderer.effectObjects.get('attack:1'), line);
  assert.equal(renderer.effectObjects.get('projectile:2'), marker); assert.equal(disposed, 0);
  renderer.updateEffects([]);
  assert.equal(renderer.effects.children.length, 0); assert.equal(renderer.effectObjects.size, 0);
  assert.equal(renderer.effectMotion.records.size, 0); assert.equal(disposed, 2);
  renderer.markerGeometry.dispose(); renderer.markerMaterial.dispose();
});

test('complete resync resets interpolation while retaining scene buffers and the user camera', () => {
  const renderer = Object.create(BattlefieldRenderer.prototype);
  const geometry = new THREE.PlaneGeometry(), material = new THREE.MeshBasicMaterial();
  let fits = 0;
  Object.assign(renderer, {tiles: new THREE.Group(), units: new THREE.Group(), territories: new THREE.Group(),
    effects: new THREE.Group(), effectObjects: new Map(), effectLabels: new Map(), labelNodes: new Map(),
    motion: new UnitMotion(), effectMotion: new UnitMotion(), selection: new THREE.Mesh(),
    metrics: {packets: 0, meshesCreated: 0, motion() {}},
    material: () => material, fit: () => fits++});
  renderer.unitBatches = new InstanceBatches(renderer.units, geometry, () => material);
  renderer.territoryBatches = new InstanceBatches(renderer.territories, geometry, () => material);
  const baseline = {epoch: '1', view: 'wei', units: [], visuals: [],
    scene: {map_id: 'small', orientation: 'flat', tiles: [{col: 0, row: 0}], factions: []},
    tiles: [{id: '0', col: 0, row: 0, visibility: 'hidden', asset: null}]};
  renderer.update(baseline, null);
  const mesh = renderer.tiles.children[0], tileGeometry = renderer.tileGeometry;
  const version = mesh.instanceMatrix.version;
  renderer.update(structuredClone(baseline), null);
  assert.equal(fits, 1); assert.equal(renderer.tiles.children[0], mesh);
  assert.equal(renderer.tileGeometry, tileGeometry); assert.equal(mesh.instanceMatrix.version, version);
  renderer.tileBatches.close(); renderer.unitBatches.close(); renderer.territoryBatches.close();
  renderer.tileGeometry.dispose(); geometry.dispose(); material.dispose();
});
