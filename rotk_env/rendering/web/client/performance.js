/** Local display diagnostics. Never submits data or advances the simulation. */
export class DisplayMetrics {
  constructor(canvas, enabled = false) {
    this.canvas = canvas;
    this.enabled = enabled;
    this.frames = 0; this.packets = 0; this.meshesCreated = 0;
    this.samples = []; this.cpu = []; this.intervals = [];
    this.lastFrame = null; this.windowStart = null; this.windowPackets = 0;
    this.motionFrames = 0; this.motionPackets = 0;
    this.framePositions = new Map(); this.packetPositions = new Map();
    if (enabled) {
      this.panel = document.createElement('output');
      this.panel.className = 'display-performance';
      this.panel.setAttribute('aria-label', '本地渲染性能');
      canvas.parentElement.append(this.panel);
    }
  }

  motion(rows, packet = false) {
    if (!this.enabled) return false;
    const previous = packet ? this.packetPositions : this.framePositions;
    let changed = false;
    const ids = new Set();
    for (const row of rows) {
      ids.add(row.id);
      const old = previous.get(row.id), p = row.position;
      if (old && (old[0] !== p[0] || old[1] !== p[1])) changed = true;
      if (!old) previous.set(row.id, [...p]);
      else { old[0] = p[0]; old[1] = p[1]; }
    }
    for (const id of previous.keys()) if (!ids.has(id)) previous.delete(id);
    if (packet && changed) this.motionPackets++;
    return changed;
  }

  begin(time) {
    if (this.lastFrame != null) this.intervals.push(time - this.lastFrame);
    this.lastFrame = time;
    this.windowStart ??= time;
    this.started = performance.now();
  }

  end(time, info, motion = false) {
    this.frames++;
    this.cpu.push(performance.now() - this.started);
    if (motion) this.motionFrames++;
    const elapsed = time - this.windowStart;
    if (elapsed < 1000) return;
    const p95 = values => [...values].sort((a, b) => a - b)[Math.floor((values.length - 1) * .95)] || 0;
    const sample = {
      fps: +(this.frames * 1000 / elapsed).toFixed(1),
      frame_p95_ms: +p95(this.intervals).toFixed(2),
      render_cpu_p95_ms: +p95(this.cpu).toFixed(2),
      packets_hz: +((this.packets - this.windowPackets) * 1000 / elapsed).toFixed(1),
      packets: this.packets, meshes_created: this.meshesCreated,
      motion_frames: this.motionFrames, motion_packets: this.motionPackets,
      draw_calls: info.render.calls, triangles: info.render.triangles,
      geometries: info.memory.geometries, textures: info.memory.textures,
      width: this.canvas.clientWidth, height: this.canvas.clientHeight,
    };
    this.samples.push(sample);
    if (this.samples.length > 20) this.samples.shift();
    this.canvas.dataset.performance = JSON.stringify(this.samples);
    if (this.panel) this.panel.textContent = `${sample.fps} FPS · 状态 ${sample.packets_hz}/s · 绘制 ${sample.draw_calls}`;
    this.frames = 0; this.cpu.length = 0; this.intervals.length = 0;
    this.windowStart = time; this.windowPackets = this.packets;
  }

  close() { this.panel?.remove(); }
}
