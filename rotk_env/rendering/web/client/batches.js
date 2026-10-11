import * as THREE from 'three';

/** Retained GPU buffers: grow on capacity changes, patch changed instances. */
export class InstanceBatches {
  constructor(group, geometry, material, onCreate = () => {}) {
    this.group = group; this.geometry = geometry; this.material = material;
    this.onCreate = onCreate; this.buckets = new Map();
    this.matrix = new THREE.Matrix4(); this.color = new THREE.Color();
    this.slots = new Map();
  }

  sync(rows, {asset, position, color, z}) {
    const buckets = new Map();
    for (const row of rows) {
      const key = asset(row);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(row);
    }
    this.slots.clear();
    for (const [key, batch] of buckets) {
      let bucket = this.buckets.get(key);
      if (!bucket || bucket.capacity < batch.length) {
        const capacity = 2 ** Math.ceil(Math.log2(Math.max(1, batch.length)));
        if (bucket) { this.group.remove(bucket.mesh); bucket.mesh.dispose(); }
        const mesh = new THREE.InstancedMesh(this.geometry, this.material(key), capacity);
        mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        this.group.add(mesh); this.onCreate();
        bucket = {mesh, capacity, values: []}; this.buckets.set(key, bucket);
      }
      const {mesh, values} = bucket;
      let matrices = false, colors = false;
      mesh.count = batch.length; mesh.userData.rows = batch;
      for (let i = 0; i < batch.length; i++) {
        const row = batch[i], p = position(row), c = color(row), old = values[i];
        if (!old || old.x !== p[0] || old.y !== p[1] || old.z !== z) {
          mesh.setMatrixAt(i, this.matrix.makeTranslation(p[0], p[1], z));
          mesh.instanceMatrix.addUpdateRange(i * 16, 16); matrices = true;
        }
        if (!old || old.color !== c) {
          mesh.setColorAt(i, this.color.set(c)); colors = true;
          mesh.instanceColor.addUpdateRange(i * 3, 3);
        }
        values[i] = old || {};
        Object.assign(values[i], {x: p[0], y: p[1], z, color: c});
        this.slots.set(row.id, {mesh, index: i, value: values[i]});
      }
      values.length = batch.length;
      if (matrices) {
        mesh.instanceMatrix.needsUpdate = true;
        mesh.computeBoundingSphere();
      }
      if (colors) {
        mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
        mesh.instanceColor.needsUpdate = true;
      }
    }
    // An empty bucket is retired; unchanged or shrinking live batches reuse buffers.
    for (const [key, bucket] of this.buckets) if (!buckets.has(key)) {
      this.group.remove(bucket.mesh); bucket.mesh.dispose(); this.buckets.delete(key);
    }
  }

  move(rows, z) {
    const changed = new Set();
    for (const row of rows) {
      const slot = this.slots.get(row.id); if (!slot) continue;
      const p = row.position, old = slot.value;
      if (old.x === p[0] && old.y === p[1]) continue;
      slot.mesh.setMatrixAt(slot.index, this.matrix.makeTranslation(p[0], p[1], z));
      slot.mesh.instanceMatrix.addUpdateRange(slot.index * 16, 16);
      old.x = p[0]; old.y = p[1]; changed.add(slot.mesh);
    }
    for (const mesh of changed) {
      mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere();
    }
  }

  close() {
    for (const {mesh} of this.buckets.values()) { this.group.remove(mesh); mesh.dispose(); }
    this.buckets.clear(); this.slots.clear();
  }
}
