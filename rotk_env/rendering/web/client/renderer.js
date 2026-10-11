import * as THREE from 'three';
import {hexToWorld, mapBounds, fitExtent} from './hex.js';
import {DisplayMetrics} from './performance.js';
import {InstanceBatches} from './batches.js';
import {UnitMotion} from './motion.js';
import {TacticalRanges} from './ranges.js';

function hexGeometry(orientation) {
  const geometry = new THREE.BufferGeometry();
  const positions = [0, 0, 0], uv = [.5, .5], indices = [];
  const offset = orientation === 'flat' ? 0 : Math.PI / 6;
  for (let i = 0; i < 6; i++) {
    const x = Math.cos(offset + i * Math.PI / 3), y = Math.sin(offset + i * Math.PI / 3);
    positions.push(x, y, 0); uv.push((x + 1) / 2, (y + 1) / 2);
    indices.push(0, i + 1, (i + 1) % 6 + 1);
  }
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geometry.setIndex(indices); geometry.computeVertexNormals();
  return geometry;
}

export class BattlefieldRenderer {
  constructor(container, {onPick, onError}) {
    this.container = container; this.onPick = onPick; this.onError = onError;
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color('rgb(135,141,106)');
    this.camera = new THREE.OrthographicCamera(-10, 10, 10, -10, .1, 100);
    this.camera.position.z = 30;
    this.engine = new THREE.WebGLRenderer({antialias: true, alpha: false});
    this.engine.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.engine.outputColorSpace = THREE.SRGBColorSpace;
    container.prepend(this.engine.domElement);
    this.metrics = new DisplayMetrics(this.engine.domElement, new URLSearchParams(location.search).has('perf'));
    this.raycaster = new THREE.Raycaster(); this.pointer = new THREE.Vector2();
    this.textures = new Map(); this.materials = new Map(); this.tiles = new THREE.Group();
    this.units = new THREE.Group(); this.effects = new THREE.Group();
    this.territories = new THREE.Group();
    this.tactical = new THREE.Group();
    this.scene.add(this.tiles, this.units, this.effects, this.territories, this.tactical);
    this.unitGeometry = new THREE.PlaneGeometry(1.65, 1.65);
    this.markerGeometry = new THREE.CircleGeometry(.10, 12);
    this.markerMaterial = new THREE.MeshBasicMaterial({depthTest: false});
    this.selection = new THREE.Mesh(new THREE.RingGeometry(.78, .86, 6),
      new THREE.MeshBasicMaterial({color: '#f5dc88', transparent: true, opacity: .95, depthTest: false}));
    this.selection.position.z = .6; this.selection.visible = false; this.scene.add(this.selection);
    this.labels = container.querySelector('#labels'); this.labelNodes = new Map();
    this.effectLabels = new Map(); this.effectObjects = new Map();
    this.motion = new UnitMotion(); this.effectMotion = new UnitMotion(); this.labelPoint = new THREE.Vector3();
    this.labelsDirty = true; this.cameraDirty = true;
    const created = () => this.metrics.meshesCreated++;
    this.unitBatches = new InstanceBatches(this.units, this.unitGeometry, asset => this.material(asset), created);
    this.territoryBatches = new InstanceBatches(this.territories, this.markerGeometry, () => this.markerMaterial, created);
    this.abort = new AbortController(); const options = {signal: this.abort.signal};
    const canvas = this.engine.domElement;
    canvas.addEventListener('pointerdown', event => {
      this.drag = {x: event.clientX, y: event.clientY, cx: this.camera.position.x, cy: this.camera.position.y};
      canvas.setPointerCapture(event.pointerId);
    }, options);
    canvas.addEventListener('pointermove', event => {
      if (!this.drag) return;
      const dx = event.clientX - this.drag.x, dy = event.clientY - this.drag.y;
      this.camera.position.x = this.drag.cx - dx * this.extent.width / this.width / this.camera.zoom;
      this.camera.position.y = this.drag.cy + dy * this.extent.height / this.height / this.camera.zoom;
      this.drag.moved ||= Math.hypot(dx, dy) > 5; this.cameraDirty = true;
    }, options);
    canvas.addEventListener('pointerup', event => {
      if (this.drag && !this.drag.moved) this.pick(event);
      this.drag = null;
    }, options);
    canvas.addEventListener('pointercancel', () => { this.drag = null; }, options);
    canvas.addEventListener('wheel', event => {
      event.preventDefault(); this.camera.zoom = Math.max(.5, Math.min(8, this.camera.zoom * Math.exp(-event.deltaY * .001)));
      this.camera.updateProjectionMatrix(); this.cameraDirty = true;
    }, {...options, passive: false});
    canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault(); this.lost = true; onError('图形上下文中断，正在等待恢复');
    }, options);
    canvas.addEventListener('webglcontextrestored', () => { this.lost = false; }, options);
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(container);
    this.resize(); this.engine.setAnimationLoop(() => this.draw());
  }

  material(asset) {
    const key = asset || 'hidden';
    if (!this.materials.has(key)) {
      let texture = null;
      if (asset) {
        texture = new THREE.TextureLoader().load('/assets/' + asset.split('/').map(encodeURIComponent).join('/'),
          undefined, undefined, () => this.onError('部分画面资源加载失败'));
        texture.colorSpace = THREE.SRGBColorSpace;
        this.textures.set(key, texture);
      }
      this.materials.set(key, new THREE.MeshBasicMaterial({map: texture, transparent: !!asset,
        alphaTest: .04, depthWrite: true, side: THREE.DoubleSide}));
    }
    return this.materials.get(key);
  }

  clear(group) { group.children.slice().forEach(mesh => {
    group.remove(mesh); mesh.dispose?.();
    if (mesh.userData.owned) { mesh.geometry.dispose(); mesh.material.dispose(); }
  }); }

  update(snapshot, selectedId, active = 'move') {
    this.selectedId = selectedId;
    if (snapshot === this.snapshot) {
      this.updateSelection(); this.ranges?.update(snapshot, selectedId, active, this.motion.records); return;
    }
    this.metrics.packets++; this.metrics.motion(snapshot.units, true);
    const previous = this.snapshot;
    const newScene = !previous || previous.epoch !== snapshot.epoch || previous.view !== snapshot.view ||
      previous.scene.map_id !== snapshot.scene.map_id || previous.scene.orientation !== snapshot.scene.orientation;
    const baseline = newScene || previous.scene !== snapshot.scene;
    const tileChanged = newScene || previous.tiles !== snapshot.tiles;
    const unitChanged = newScene || previous.units !== snapshot.units;
    this.snapshot = snapshot;
    this.labelsDirty = this.motion.update(snapshot.units, performance.now(), baseline) || this.labelsDirty;
    if (newScene) {
      this.ranges?.close();
      this.ranges = new TacticalRanges(this.tactical, snapshot.scene.orientation,
        () => this.metrics.meshesCreated++);
      this.tileBatches?.close(); this.tileGeometry?.dispose();
      this.tileGeometry = hexGeometry(snapshot.scene.orientation);
      this.tileBatches = new InstanceBatches(this.tiles, this.tileGeometry, asset => this.material(asset),
        () => this.metrics.meshesCreated++);
      this.bounds = mapBounds(snapshot.scene.tiles, snapshot.scene.orientation); this.fit();
    }
    if (tileChanged) {
      this.tileBatches.sync(snapshot.tiles, {
        asset: row => row.asset, position: row => hexToWorld(row.col, row.row, snapshot.scene.orientation),
        color: row => row.visibility === 'hidden' ? '#535e53' : !row.asset ? `rgb(${row.color.join(',')})`
          : row.visibility === 'explored' ? '#798b78' : '#ffffff', z: 0});
      const owned = snapshot.tiles.filter(t => t.owner && t.visibility !== 'hidden');
      const colors = new Map(snapshot.scene.factions.map(f => [f.id, `rgb(${f.color.join(',')})`]));
      this.territoryBatches.sync(owned, {asset: () => '', position: row => {
        const [x, y] = hexToWorld(row.col, row.row, snapshot.scene.orientation); return [x, y - .55];
      }, color: row => colors.get(row.owner) || '#cabb85', z: .1});
    }
    if (unitChanged) {
      this.unitBatches.sync(snapshot.units, {asset: row => row.asset,
        position: row => this.motion.records.get(row.id).position, color: () => '#ffffff', z: .2});
      const ids = new Set(snapshot.units.map(row => row.id));
      for (const [id, node] of this.labelNodes) if (!ids.has(id)) { node.remove(); this.labelNodes.delete(id); }
      if (snapshot.units.length < 200) for (const row of snapshot.units) {
        if (!this.labelNodes.has(row.id)) {
          const node = document.createElement('span'); node.className = 'unit-label';
          this.labels.append(node); this.labelNodes.set(row.id, node);
        }
        const node = this.labelNodes.get(row.id);
        if (node.textContent !== String(row.count)) node.textContent = row.count;
      } else { this.labelNodes.forEach(node => node.remove()); this.labelNodes.clear(); }
      this.labelsDirty = true;
    }
    // Retargeting can advance a previous interpolation even without membership changes.
    this.unitBatches.move(this.motion.rows, .2);
    this.ranges.update(snapshot, selectedId, active, this.motion.records);
    this.updateSelection(); this.updateEffects(snapshot.visuals || [], baseline);
  }

  updateSelection() {
    const selected = this.motion.records.get(this.selectedId);
    this.selection.visible = !!selected;
    if (selected) this.selection.position.set(...selected.position, .5);
  }

  clearSelection() {
    this.selectedId = null; this.selection.visible = false; this.ranges?.clear();
  }

  updateEffects(rows, reset = false) {
    this.effectMotion.update(rows.filter(row => row.kind === 'projectile' || row.kind === 'effect'),
      performance.now(), reset);
    const ids = new Set(rows.map(row => row.id));
    for (const [id, object] of this.effectObjects) if (!ids.has(id)) {
      this.effects.remove(object); object.dispose?.();
      if (object.userData.owned) { object.geometry.dispose(); object.material.dispose(); }
      this.effectObjects.delete(id);
    }
    for (const [id, node] of this.effectLabels) if (!ids.has(id)) { node.remove(); this.effectLabels.delete(id); }
    for (const row of rows) {
      if (row.kind === 'damage') {
        if (!this.effectLabels.has(row.id)) {
          const node = document.createElement('span'); node.className = 'damage-label';
          this.labels.append(node); this.effectLabels.set(row.id, node);
        }
        const node = this.effectLabels.get(row.id);
        if (node.textContent !== row.text) node.textContent = row.text;
        node.style.opacity = Math.max(0, 1 - row.progress);
      } else if (row.kind === 'attack' && row.target) {
        let line = this.effectObjects.get(row.id);
        if (!line) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
          line = new THREE.Line(geometry, new THREE.LineBasicMaterial({color: '#f5d48a',
            transparent: true, depthTest: false}));
          line.userData.owned = true; this.effects.add(line); this.effectObjects.set(row.id, line);
        }
        const position = line.geometry.getAttribute('position');
        position.setXYZ(0, ...row.position, .7); position.setXYZ(1, ...row.target, .7);
        position.needsUpdate = true; line.geometry.computeBoundingSphere();
        line.material.opacity = Math.max(.15, 1 - row.progress);
      } else if (row.kind === 'projectile' || row.kind === 'effect') {
        let marker = this.effectObjects.get(row.id);
        if (!marker) {
          marker = new THREE.Mesh(this.markerGeometry, this.markerMaterial.clone());
          marker.material.color.set('#f3cf72');
          marker.dispose = () => marker.material.dispose();
          this.effects.add(marker); this.effectObjects.set(row.id, marker);
        }
        marker.position.set(...this.effectMotion.records.get(row.id).position, .7);
      }
    }
    this.labelsDirty ||= rows.some(row => row.kind === 'damage');
  }

  fit() {
    if (!this.bounds) return;
    this.extent = fitExtent(this.bounds, this.width / this.height);
    this.camera.zoom = 1; this.camera.position.set(this.extent.x, this.extent.y, 30);
    this.resize();
  }

  resize() {
    this.width = Math.max(1, this.container.clientWidth); this.height = Math.max(1, this.container.clientHeight);
    this.engine.setSize(this.width, this.height, false);
    const old = this.extent;
    this.extent = this.bounds ? fitExtent(this.bounds, this.width / this.height)
      : {width: 20 * this.width / this.height, height: 20};
    this.camera.left = -this.extent.width / 2; this.camera.right = this.extent.width / 2;
    this.camera.top = this.extent.height / 2; this.camera.bottom = -this.extent.height / 2;
    if (old && this.camera.zoom === 1 && this.bounds) this.camera.position.set(this.extent.x, this.extent.y, 30);
    this.camera.updateProjectionMatrix(); this.cameraDirty = true;
  }

  pick(event) {
    const rect = this.engine.domElement.getBoundingClientRect();
    this.pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const unit = this.raycaster.intersectObjects(this.units.children)[0];
    const tile = this.raycaster.intersectObjects(this.tiles.children)[0];
    this.onPick({unit: unit?.object.userData.rows[unit.instanceId], tile: tile?.object.userData.rows[tile.instanceId]});
  }

  placeLabel(node, x, y, z, clip = true) {
    const p = this.labelPoint.set(x, y, z).project(this.camera);
    const left = `${((p.x + 1) / 2 * this.width).toFixed(2)}px`;
    const top = `${((1 - p.y) / 2 * this.height).toFixed(2)}px`;
    if (node.style.left !== left) node.style.left = left;
    if (node.style.top !== top) node.style.top = top;
    const visibility = clip && (Math.abs(p.x) > 1 || Math.abs(p.y) > 1) ? 'hidden' : 'visible';
    if (node.style.visibility !== visibility) node.style.visibility = visibility;
  }

  draw() {
    if (this.lost) return;
    const time = performance.now(); this.metrics.begin(time);
    const moved = this.motion.step(time);
    if (moved) {
      this.unitBatches.move(this.motion.rows, .2); this.updateSelection();
      this.ranges?.moveTargets(this.motion.records);
    }
    if (this.effectMotion.step(time)) for (const row of this.effectMotion.rows) {
      this.effectObjects.get(row.id)?.position.set(...row.position, .7);
    }
    this.camera.updateMatrixWorld(); this.engine.render(this.scene, this.camera);
    if (this.snapshot && (moved || this.labelsDirty || this.cameraDirty)) {
      for (const record of this.motion.rows) {
        const node = this.labelNodes.get(record.id); if (!node) continue;
        this.placeLabel(node, record.position[0], record.position[1] - .65, .3);
      }
      for (const row of this.snapshot.visuals || []) if (row.kind === 'damage') {
        const node = this.effectLabels.get(row.id); if (!node) continue;
        this.placeLabel(node, row.position[0], row.position[1] + row.progress, .8);
      }
      this.labelsDirty = this.cameraDirty = false;
    }
    this.metrics.end(time, this.engine.info, this.metrics.motion(this.motion.rows));
  }

  close() {
    this.abort.abort(); this.observer.disconnect(); this.engine.setAnimationLoop(null);
    this.tileBatches?.close(); this.unitBatches.close(); this.territoryBatches.close(); this.clear(this.effects);
    this.ranges?.close();
    this.tileGeometry?.dispose(); this.unitGeometry.dispose(); this.selection.geometry.dispose();
    this.selection.material.dispose(); this.materials.forEach(m => m.dispose());
    this.markerGeometry.dispose(); this.markerMaterial.dispose();
    this.textures.forEach(t => t.dispose()); this.labelNodes.forEach(node => node.remove());
    this.effectLabels.forEach(node => node.remove());
    this.engine.dispose(); this.engine.domElement.remove();
    this.metrics.close();
  }
}
