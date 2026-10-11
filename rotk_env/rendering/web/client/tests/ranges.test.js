import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {TacticalRanges} from '../ranges.js';
import {hexToWorld} from '../hex.js';

const snapshot = () => ({epoch: '1', view: 'wei', hud: {game_over: false},
  units: [{id: '1', position: [0, 0]}, {id: '9223372036854775819', position: [1.5, .8]}],
  selection: {unit_id: '1', origin: [0, 0], movement: [[1, 0], [2, 0]],
    attack: [[1, 0]], targets: ['9223372036854775819']}});

test('server cells become distinct movement fills, attack outlines and visible target rings', () => {
  for (const orientation of ['flat', 'pointy']) {
    const group = new THREE.Group(), ranges = new TacticalRanges(group, orientation);
    const state = snapshot(), before = structuredClone(state);
    ranges.update(state, '1');
    assert.equal(ranges.movement.slots.size, 2); assert.equal(ranges.attack.slots.size, 1);
    assert.equal(ranges.targets.slots.size, 1);
    const m = new THREE.Matrix4();
    ranges.movement.slots.get('1,0').mesh.getMatrixAt(0, m);
    const expected = hexToWorld(1, 0, orientation);
    assert.ok(Math.abs(m.elements[12] - expected[0]) < .000001);
    assert.ok(Math.abs(m.elements[13] - expected[1]) < .000001);
    assert.equal(ranges.fillMaterial.color.getHexString(), '52c8df');
    assert.equal(ranges.outlineMaterial.color.getHexString(), 'ffba68');
    assert.equal(ranges.outlineGeometry.type, 'RingGeometry');
    assert.deepEqual(state, before); ranges.close();
  }
});

test('100 refreshes and mode switches keep range meshes and GPU buffers', () => {
  let created = 0;
  const group = new THREE.Group(), ranges = new TacticalRanges(group, 'flat', () => created++);
  const state = snapshot(); ranges.update(state, '1');
  const meshes = [...group.children], versions = meshes.map(m => m.instanceMatrix.version);
  for (let i = 0; i < 100; i++) ranges.update(structuredClone(state), '1');
  ranges.update(state, '1', 'attack');
  assert.equal(created, 3); assert.deepEqual(group.children, meshes);
  assert.deepEqual(meshes.map(m => m.instanceMatrix.version), versions);
  assert.equal(ranges.fillMaterial.opacity, .12); assert.equal(ranges.outlineMaterial.opacity, .95);
  ranges.close();
});

test('changed ranges update; mismatch, removal, game end and deselection clear stale overlays', () => {
  const group = new THREE.Group(), ranges = new TacticalRanges(group, 'flat');
  const state = snapshot(); ranges.update(state, '1');
  const movementMesh = ranges.movement.slots.get('1,0').mesh;
  state.selection.movement = [[2, 0]]; ranges.update(state, '1');
  assert.equal(group.children[0], movementMesh); assert.equal(movementMesh.count, 1);
  for (const next of [null, 'other', '1']) {
    ranges.update(snapshot(), '1');
    const current = snapshot(); if (next === '1') current.units = [];
    ranges.update(current, next); assert.equal(group.children.length, 0);
  }
  ranges.update(snapshot(), '1');
  ranges.update({...snapshot(), hud: {game_over: true}}, '1');
  assert.equal(group.children.length, 0); ranges.close();
});

test('target rings follow interpolated display positions; close releases all owned resources', () => {
  const group = new THREE.Group(), ranges = new TacticalRanges(group, 'flat');
  const state = snapshot(); ranges.update(state, '1');
  const id = '9223372036854775819', record = {id, position: [1.8, .9]};
  ranges.moveTargets(new Map([[id, record]]));
  const slot = ranges.targets.slots.get(id), matrix = new THREE.Matrix4();
  const version = slot.mesh.instanceMatrix.version;
  ranges.update(state, '1', 'move', new Map([[id, record]]));
  assert.equal(slot.mesh.instanceMatrix.version, version);
  slot.mesh.getMatrixAt(slot.index, matrix);
  assert.ok(Math.abs(matrix.elements[12] - 1.8) < .000001);
  assert.deepEqual(state.units[1].position, [1.5, .8]);
  let disposed = 0;
  for (const resource of [ranges.fillGeometry, ranges.outlineGeometry, ranges.targetGeometry,
    ranges.fillMaterial, ranges.outlineMaterial, ranges.targetMaterial]) {
    resource.addEventListener('dispose', () => disposed++);
  }
  ranges.close(); assert.equal(group.children.length, 0); assert.equal(disposed, 6);
});
