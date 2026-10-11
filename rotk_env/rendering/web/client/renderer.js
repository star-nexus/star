import * as THREE from 'three';
import {hexToWorld, mapBounds, fitExtent} from './hex.js';

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
    this.raycaster = new THREE.Raycaster(); this.pointer = new THREE.Vector2();
    this.textures = new Map(); this.materials = new Map(); this.tiles = new THREE.Group();
    this.units = new THREE.Group(); this.effects = new THREE.Group();
    this.territories = new THREE.Group();
    this.scene.add(this.tiles, this.units, this.effects, this.territories);
    this.unitGeometry = new THREE.PlaneGeometry(1.65, 1.65);
    this.markerGeometry = new THREE.CircleGeometry(.10, 12);
    this.markerMaterial = new THREE.MeshBasicMaterial({depthTest: false});
    this.selection = new THREE.Mesh(new THREE.RingGeometry(.78, .86, 6),
      new THREE.MeshBasicMaterial({color: '#f5dc88', transparent: true, opacity: .95, depthTest: false}));
    this.selection.position.z = .6; this.selection.visible = false; this.scene.add(this.selection);
    this.labels = container.querySelector('#labels'); this.labelNodes = new Map();
    this.effectLabels = new Map();
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
      this.drag.moved ||= Math.hypot(dx, dy) > 5;
    }, options);
    canvas.addEventListener('pointerup', event => {
      if (this.drag && !this.drag.moved) this.pick(event);
      this.drag = null;
    }, options);
    canvas.addEventListener('pointercancel', () => { this.drag = null; }, options);
    canvas.addEventListener('wheel', event => {
      event.preventDefault(); this.camera.zoom = Math.max(.5, Math.min(8, this.camera.zoom * Math.exp(-event.deltaY * .001)));
      this.camera.updateProjectionMatrix();
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

  batches(group, rows, geometry, assetOf, positionOf, colorOf, z) {
    this.clear(group);
    const buckets = new Map();
    rows.forEach(row => {
      const asset = assetOf(row); if (!buckets.has(asset)) buckets.set(asset, []);
      buckets.get(asset).push(row);
    });
    for (const [asset, batch] of buckets) {
      const mesh = new THREE.InstancedMesh(geometry, this.material(asset), batch.length);
      const matrix = new THREE.Matrix4();
      batch.forEach((row, i) => {
        const [x, y] = positionOf(row); matrix.makeTranslation(x, y, z);
        mesh.setMatrixAt(i, matrix); mesh.setColorAt(i, new THREE.Color(colorOf(row)));
      });
      mesh.userData.rows = batch; mesh.computeBoundingSphere(); group.add(mesh);
    }
  }

  update(snapshot, selectedId) {
    const newScene = !this.snapshot || this.snapshot.epoch !== snapshot.epoch;
    const tileChanged = newScene || snapshot.tiles.some((row, i) => JSON.stringify(row) !== JSON.stringify(this.snapshot.tiles[i]));
    this.snapshot = snapshot;
    if (newScene) {
      this.tileGeometry?.dispose(); this.tileGeometry = hexGeometry(snapshot.scene.orientation);
      this.bounds = mapBounds(snapshot.scene.tiles, snapshot.scene.orientation); this.fit();
    }
    if (tileChanged) {
      this.batches(this.tiles, snapshot.tiles, this.tileGeometry,
        row => row.asset, row => hexToWorld(row.col, row.row, snapshot.scene.orientation),
        row => row.visibility === 'hidden' ? '#535e53' : !row.asset ? `rgb(${row.color.join(',')})`
          : row.visibility === 'explored' ? '#798b78' : '#ffffff', 0);
      this.clear(this.territories);
      const owned = snapshot.tiles.filter(t => t.owner && t.visibility !== 'hidden');
      if (owned.length) {
        const markers = new THREE.InstancedMesh(this.markerGeometry, this.markerMaterial, owned.length);
        const colors = new Map(snapshot.scene.factions.map(f => [f.id, new THREE.Color(`rgb(${f.color.join(',')})`)]));
        owned.forEach((row, i) => {
          const [x, y] = hexToWorld(row.col, row.row, snapshot.scene.orientation);
          markers.setMatrixAt(i, new THREE.Matrix4().makeTranslation(x, y - .55, .1));
          markers.setColorAt(i, colors.get(row.owner) || new THREE.Color('#cabb85'));
        }); markers.computeBoundingSphere(); this.territories.add(markers);
      }
    }
    this.batches(this.units, snapshot.units, this.unitGeometry, row => row.asset,
      row => row.position, () => '#ffffff', .2);
    const selected = snapshot.units.find(row => row.id === selectedId);
    this.selection.visible = !!selected;
    if (selected) this.selection.position.set(...selected.position, .5);
    const ids = new Set(snapshot.units.map(row => row.id));
    for (const [id, node] of this.labelNodes) if (!ids.has(id)) { node.remove(); this.labelNodes.delete(id); }
    if (snapshot.units.length < 200) for (const row of snapshot.units) {
      if (!this.labelNodes.has(row.id)) {
        const node = document.createElement('span'); node.className = 'unit-label';
        this.labels.append(node); this.labelNodes.set(row.id, node);
      }
      this.labelNodes.get(row.id).textContent = row.count;
    } else { this.labelNodes.forEach(node => node.remove()); this.labelNodes.clear(); }
    this.updateEffects(snapshot.visuals || []);
  }

  updateEffects(rows) {
    this.clear(this.effects);
    const ids = new Set(rows.filter(row => row.kind === 'damage').map(row => row.id));
    for (const [id, node] of this.effectLabels) if (!ids.has(id)) { node.remove(); this.effectLabels.delete(id); }
    for (const row of rows) {
      if (row.kind === 'damage') {
        if (!this.effectLabels.has(row.id)) {
          const node = document.createElement('span'); node.className = 'damage-label';
          this.labels.append(node); this.effectLabels.set(row.id, node);
        }
        const node = this.effectLabels.get(row.id); node.textContent = row.text;
        node.style.opacity = Math.max(0, 1 - row.progress);
      } else if (row.kind === 'attack' && row.target) {
        const geometry = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(...row.position, .7), new THREE.Vector3(...row.target, .7)]);
        const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({color: '#f5d48a',
          transparent: true, opacity: Math.max(.15, 1 - row.progress), depthTest: false}));
        line.userData.owned = true; this.effects.add(line);
      } else if (row.kind === 'projectile' || row.kind === 'effect') {
        const marker = new THREE.Mesh(this.markerGeometry, this.markerMaterial.clone());
        marker.material.color.set('#f3cf72'); marker.position.set(...row.position, .7);
        // Geometry is shared; material is retired explicitly on the next patch.
        marker.dispose = () => marker.material.dispose(); this.effects.add(marker);
      }
    }
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
    this.camera.updateProjectionMatrix();
  }

  pick(event) {
    const rect = this.engine.domElement.getBoundingClientRect();
    this.pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const unit = this.raycaster.intersectObjects(this.units.children)[0];
    const tile = this.raycaster.intersectObjects(this.tiles.children)[0];
    this.onPick({unit: unit?.object.userData.rows[unit.instanceId], tile: tile?.object.userData.rows[tile.instanceId]});
  }

  draw() {
    if (this.lost) return;
    this.camera.updateMatrixWorld(); this.engine.render(this.scene, this.camera);
    if (!this.snapshot) return;
    for (const row of this.snapshot.units) {
      const node = this.labelNodes.get(row.id); if (!node) continue;
      const p = new THREE.Vector3(row.position[0], row.position[1] - .65, .3).project(this.camera);
      node.style.left = `${(p.x + 1) / 2 * this.width}px`; node.style.top = `${(1 - p.y) / 2 * this.height}px`;
      node.style.visibility = Math.abs(p.x) > 1 || Math.abs(p.y) > 1 ? 'hidden' : 'visible';
    }
    for (const row of this.snapshot.visuals || []) if (row.kind === 'damage') {
      const node = this.effectLabels.get(row.id); if (!node) continue;
      const p = new THREE.Vector3(row.position[0], row.position[1] + row.progress, .8).project(this.camera);
      node.style.left = `${(p.x + 1) / 2 * this.width}px`; node.style.top = `${(1 - p.y) / 2 * this.height}px`;
    }
  }

  close() {
    this.abort.abort(); this.observer.disconnect(); this.engine.setAnimationLoop(null);
    this.clear(this.tiles); this.clear(this.units); this.clear(this.effects); this.clear(this.territories);
    this.tileGeometry?.dispose(); this.unitGeometry.dispose(); this.selection.geometry.dispose();
    this.selection.material.dispose(); this.materials.forEach(m => m.dispose());
    this.markerGeometry.dispose(); this.markerMaterial.dispose();
    this.textures.forEach(t => t.dispose()); this.labelNodes.forEach(node => node.remove());
    this.effectLabels.forEach(node => node.remove());
    this.engine.dispose(); this.engine.domElement.remove();
  }
}
