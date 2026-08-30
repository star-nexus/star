"""Parse an ASCII hex map (centered offset coords)."""

from pathlib import Path
from typing import Dict, Tuple

from rotk_env.prefabs.config import TerrainType

LEGEND = {
    ".": TerrainType.PLAIN,
    "~": TerrainType.WATER,
    "M": TerrainType.MOUNTAIN,
    "F": TerrainType.FOREST,
    "H": TerrainType.HILL,
    "C": TerrainType.URBAN,
}

CHAR_FOR = {terrain: ch for ch, terrain in LEGEND.items()}

MAPS_DIR = Path(__file__).resolve().parent


def parse_ascii_map(
    text: str,
    width: int,
    height: int,
) -> Dict[Tuple[int, int], TerrainType]:
    """First line is north (row = +half). Column 0 of a line is west (col = -half)."""
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue
        lines.append(line)
    if len(lines) != height:
        raise ValueError(f"expected {height} map rows, got {len(lines)}")
    half_w = width // 2
    half_h = height // 2
    terrain: Dict[Tuple[int, int], TerrainType] = {}
    for i, line in enumerate(lines):
        if len(line) != width:
            raise ValueError(f"row {i} has length {len(line)}, expected {width}: {line!r}")
        row = half_h - i
        for j, ch in enumerate(line):
            if ch not in LEGEND:
                raise ValueError(f"unknown terrain {ch!r} at row {i} col {j}")
            col = j - half_w
            terrain[(col, row)] = LEGEND[ch]
    return terrain


def load_ascii_map(path: Path) -> Dict[Tuple[int, int], TerrainType]:
    text = path.read_text(encoding="utf-8")
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line:
            lines.append(line)
    if not lines:
        raise ValueError(f"{path}: empty map")
    height = len(lines)
    width = len(lines[0])
    return parse_ascii_map(text, width=width, height=height)


def dump_ascii_map(
    terrain: Dict[Tuple[int, int], TerrainType],
    width: int,
    height: int,
) -> str:
    half_w = width // 2
    half_h = height // 2
    lines = []
    for i in range(height):
        row = half_h - i
        chars = []
        for j in range(width):
            col = j - half_w
            chars.append(CHAR_FOR[terrain[(col, row)]])
        lines.append("".join(chars))
    return "\n".join(lines) + "\n"
