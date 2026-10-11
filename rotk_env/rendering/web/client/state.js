/** Disposable display state. No rules, authority clock or Agent requests live here. */
export class DisplayState {
  constructor() { this.snapshot = null; }

  apply(packet) {
    if (packet.schema !== 1 || !Number.isSafeInteger(packet.sequence)) return false;
    if (packet.kind === 'snapshot') {
      this.snapshot = structuredClone(packet);
      return true;
    }
    const previous = this.snapshot;
    if (packet.kind !== 'delta' || !previous || packet.epoch !== previous.epoch ||
        packet.view !== previous.view || packet.base_sequence !== previous.sequence ||
        packet.sequence < previous.sequence) return false;
    const merge = (rows, updates, removed = []) => {
      const next = new Map(rows.map(row => [row.id, row]));
      removed.forEach(id => next.delete(id));
      updates.forEach(row => next.set(row.id, structuredClone(row)));
      return [...next.values()];
    };
    this.snapshot = {...previous, ...structuredClone(packet), kind: 'snapshot',
      units: merge(previous.units, packet.units, packet.removed),
      tiles: merge(previous.tiles, packet.tiles)};
    delete this.snapshot.base_sequence;
    delete this.snapshot.removed;
    return true;
  }

  clear() { this.snapshot = null; }
}

export function canEndTurn(snapshot, canControl) {
  return !!snapshot && canControl && !snapshot.hud.game_over &&
    (!snapshot.scene?.commands || snapshot.scene.commands.includes('end_turn')) &&
    snapshot.hud.mode === 'turn_based' && snapshot.hud.current_player === snapshot.view;
}
