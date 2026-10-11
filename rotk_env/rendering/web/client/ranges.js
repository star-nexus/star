import * as THREE from 'three';
import {InstanceBatches} from './batches.js';
import {hexToWorld} from './hex.js';

/** Draw only server-provided cells. No movement or attack rules live here. */
export class TacticalRanges {
  constructor(group, orientation, onCreated = () => {}) {
    this.group = group; this.orientation = orientation;
    const angle = orientation === 'flat' ? 0 : Math.PI / 6;
    this.fillGeometry = new THREE.CircleGeometry(.94, 6, angle);
    this.outlineGeometry = new THREE.RingGeometry(.91, .96, 6, 1, angle);
    this.targetGeometry = new THREE.RingGeometry(.72, .82, 24);
    const material = color => new THREE.MeshBasicMaterial({color, transparent: true, depthWrite: false});
    this.fillMaterial = material('#52c8df'); this.outlineMaterial = material('#ffba68');
    this.targetMaterial = material('#ff7067'); this.targetMaterial.opacity = .95;
    this.movement = new InstanceBatches(group, this.fillGeometry, () => this.fillMaterial, onCreated);
    this.attack = new InstanceBatches(group, this.outlineGeometry, () => this.outlineMaterial, onCreated);
    this.targets = new InstanceBatches(group, this.targetGeometry, () => this.targetMaterial, onCreated);
    this.targetIds = []; this.key = null;
  }

  update(snapshot, selectedId, active = 'move', poses = null) {
    const data = snapshot.selection;
    if (!data || data.unit_id !== selectedId || snapshot.hud?.game_over ||
        !snapshot.units.some(u => u.id === selectedId)) { this.clear(); return; }
    this.fillMaterial.opacity = active === 'attack' ? .12 : .30;
    this.outlineMaterial.opacity = active === 'attack' ? .95 : .58;
    const key = JSON.stringify([snapshot.epoch, snapshot.view, data]);
    if (key !== this.key) {
      const rows = cells => cells.map(([col, row]) => ({id: `${col},${row}`, col, row}));
      const options = {asset: () => '', color: () => '#ffffff',
        position: row => hexToWorld(row.col, row.row, this.orientation)};
      this.movement.sync(rows(data.movement), {...options, z: .06});
      this.attack.sync(rows(data.attack), {...options, z: .08});
      this.targetIds = [...data.targets];
      this.key = key;
    }
    const targets = new Set(this.targetIds);
    this.targets.sync(snapshot.units.filter(u => targets.has(u.id)), {
      asset: () => '', color: () => '#ffffff', position: row => poses?.get(row.id)?.position || row.position, z: .32});
  }

  moveTargets(records) {
    const rows = this.targetIds.map(id => records.get(id)).filter(Boolean);
    this.targets.move(rows, .32);
  }

  clear() {
    if (this.key === null) return;
    this.movement.close(); this.attack.close(); this.targets.close();
    this.key = null; this.targetIds = [];
  }

  close() {
    this.clear(); this.movement.close(); this.attack.close(); this.targets.close();
    this.fillGeometry.dispose(); this.outlineGeometry.dispose(); this.targetGeometry.dispose();
    this.fillMaterial.dispose(); this.outlineMaterial.dispose(); this.targetMaterial.dispose();
  }
}
