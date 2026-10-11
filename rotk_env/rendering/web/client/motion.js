/** Smooth only received poses. No prediction, rules, clock or command execution. */
export class UnitMotion {
  constructor() { this.records = new Map(); this.rows = []; this.active = new Set(); }

  update(rows, time, reset = false) {
    if (reset) { this.records.clear(); this.active.clear(); }
    const advanced = this.step(time);
    const ids = new Set();
    this.rows = rows.map(row => {
      ids.add(row.id);
      let record = this.records.get(row.id);
      if (!record) {
        record = {id: row.id, position: [...row.position], target: [...row.position], at: time};
        this.records.set(row.id, record);
      } else if (record.target[0] !== row.position[0] || record.target[1] !== row.position[1]) {
        const gap = time - record.at;
        if (gap > 250) {
          // A stalled stream / discontinuity resumes at authoritative pixels.
          record.position[0] = row.position[0]; record.position[1] = row.position[1];
          this.active.delete(record);
        } else {
          record.start = [...record.position];
          record.duration = Math.max(16, Math.min(100, gap));
          record.started = time; this.active.add(record);
        }
        record.target[0] = row.position[0]; record.target[1] = row.position[1]; record.at = time;
      } else if (!this.active.has(record)) record.at = time;
      record.row = row;
      return record;
    });
    for (const [id, record] of this.records) if (!ids.has(id)) {
      this.active.delete(record); this.records.delete(id);
    }
    return advanced;
  }

  step(time) {
    let changed = false;
    for (const record of this.active) {
      const p = Math.max(0, Math.min(1, (time - record.started) / record.duration));
      const x = record.start[0] + (record.target[0] - record.start[0]) * p;
      const y = record.start[1] + (record.target[1] - record.start[1]) * p;
      changed ||= x !== record.position[0] || y !== record.position[1];
      record.position[0] = x; record.position[1] = y;
      if (p === 1) this.active.delete(record);
    }
    return changed;
  }
}
