/** Local display diagnostics. Never submits data or advances the simulation. */
export class FrameRateCounter {
  constructor() { this.reset(); }
  reset() { this.start = null; this.frames = 0; }
  frame(time) {
    if (this.start === null) { this.start = time; return null; }
    this.frames++;
    const elapsed = time - this.start;
    if (elapsed < 1000) return null;
    const fps = this.frames * 1000 / elapsed;
    this.start = time; this.frames = 0;
    return fps;
  }
}

export class DisplayMetrics {
  constructor(canvas, enabled = false) {
    this.canvas = canvas;
    this.enabled = enabled;
    this.frames = 0; this.packets = 0; this.meshesCreated = 0;
    this.samples = []; this.cpu = []; this.intervals = [];
    this.lastFrame = null; this.windowStart = null; this.windowPackets = 0;
    this.motionFrames = 0; this.motionPackets = 0;
    this.framePositions = new Map(); this.packetPositions = new Map();
    this.rate = new FrameRateCounter();
    this.panel = document.createElement('output');
    this.panel.className = enabled ? 'display-fps display-performance' : 'display-fps';
    this.panel.setAttribute('aria-label', '渲染帧率');
    this.panel.setAttribute('aria-live', 'off');
    this.panel.textContent = '— FPS';
    canvas.parentElement.append(this.panel);
    this.visibility = () => {
      this.rate.reset(); this.lastFrame = this.windowStart = null;
      this.frames = 0; this.cpu.length = this.intervals.length = 0;
      this.windowPackets = this.packets;
      this.panel.textContent = '— FPS';
      delete this.canvas.dataset.fps;
    };
    document.addEventListener('visibilitychange', this.visibility);
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
    if (!this.enabled || document.hidden) return;
    if (this.lastFrame != null) this.intervals.push(time - this.lastFrame);
    this.lastFrame = time;
    this.windowStart ??= time;
    this.started = performance.now();
  }

  end(time, info, motion = false) {
    if (document.hidden) return;
    const fps = this.rate.frame(time);
    if (!this.enabled) {
      if (fps !== null) this.showFps(fps);
      return;
    }
    this.frames++;
    this.cpu.push(performance.now() - this.started);
    if (motion) this.motionFrames++;
    const elapsed = time - this.windowStart;
    if (fps === null) return;
    const p95 = values => [...values].sort((a, b) => a - b)[Math.floor((values.length - 1) * .95)] || 0;
    const sample = {
      fps: +fps.toFixed(1),
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
    this.showFps(fps, ` · 状态 ${sample.packets_hz}/s · 绘制 ${sample.draw_calls}`);
    this.frames = 0; this.cpu.length = 0; this.intervals.length = 0;
    this.windowStart = time; this.windowPackets = this.packets;
  }

  showFps(fps, details = '') {
    const value = String(Math.round(fps)), text = `${value} FPS${details}`;
    if (this.panel.textContent !== text) this.panel.textContent = text;
    this.canvas.dataset.fps = value;
  }

  close() {
    document.removeEventListener('visibilitychange', this.visibility);
    this.panel.remove();
  }
}
