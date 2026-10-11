export function hexToWorld(col, row, orientation = 'flat') {
  return orientation === 'flat'
    ? [1.5 * col, Math.sqrt(3) * (row + .5 * (col & 1))]
    : [Math.sqrt(3) * (col + .5 * (row & 1)), 1.5 * row];
}

export function mapBounds(tiles, orientation) {
  const positions = tiles.map(t => hexToWorld(t.col, t.row, orientation));
  return {minX: Math.min(...positions.map(p => p[0])) - 1,
    maxX: Math.max(...positions.map(p => p[0])) + 1,
    minY: Math.min(...positions.map(p => p[1])) - 1,
    maxY: Math.max(...positions.map(p => p[1])) + 1};
}

export function fitExtent(bounds, aspect) {
  const width = (bounds.maxX - bounds.minX) * 1.06;
  const height = (bounds.maxY - bounds.minY) * 1.06;
  return {width: Math.max(width, height * aspect), height: Math.max(height, width / aspect),
    x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2};
}
