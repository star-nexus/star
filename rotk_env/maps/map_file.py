"""Load and dump skirmish map documents from rotk_env/maps.

A map file is JSON: size, ASCII terrain rows (north first), and per-faction
formation cells in centered offset coordinates. MapSystem only loads these.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from rotk_env.maps.ascii_map import MAPS_DIR, dump_ascii_map, parse_ascii_map
from rotk_env.prefabs.config import TerrainType

Hex = Tuple[int, int]

SCENARIO_FILES = {
    "default": "river_split.json",
    "river_split": "river_split.json",
    "river_split_offset": "river_split.json",
    "three_kingdoms": "river_split.json",
    "chibi": "chibi.json",
}


@dataclass
class MapDocument:
    """Parsed map file. Terrain keys are offset (col, row)."""

    id: str
    name: str
    width: int
    height: int
    terrain: Dict[Hex, TerrainType]
    formations: Dict[str, List[Hex]]
    coordinate_system: str = "centered"
    path: Path | None = None


def resolve_map_path(scenario: str) -> Path:
    """CLI/scenario name → a JSON file in this directory."""
    name = SCENARIO_FILES.get(scenario, scenario)
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = MAPS_DIR / name
    if not path.is_file():
        available = sorted(p.name for p in MAPS_DIR.glob("*.json"))
        raise FileNotFoundError(
            f"No map file for scenario {scenario!r} (looked for {path.name}). "
            f"Maps in {MAPS_DIR}: {available}"
        )
    return path


def load_map(path: Path) -> MapDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    width = int(data["width"])
    height = int(data["height"])
    rows = data["terrain"]
    if not isinstance(rows, list):
        raise ValueError(f"{path}: terrain must be a list of row strings")
    terrain = parse_ascii_map("\n".join(rows), width=width, height=height)
    formations: Dict[str, List[Hex]] = {}
    raw_formations = data.get("formations") or {}
    for faction, cells in raw_formations.items():
        parsed = [_as_hex(cell) for cell in cells]
        for cell in parsed:
            if cell not in terrain:
                raise ValueError(
                    f"{path}: {faction} formation cell {cell} is off the board"
                )
            if terrain[cell] is TerrainType.WATER:
                raise ValueError(
                    f"{path}: {faction} formation cell {cell} is water"
                )
        formations[str(faction)] = parsed
    return MapDocument(
        id=str(data.get("id") or path.stem),
        name=str(data.get("name") or path.stem),
        width=width,
        height=height,
        terrain=terrain,
        formations=formations,
        coordinate_system=str(data.get("coordinate_system") or "centered"),
        path=path,
    )


def dump_map(doc: MapDocument) -> str:
    ascii_block = dump_ascii_map(
        doc.terrain, width=doc.width, height=doc.height
    ).rstrip("\n")
    payload = {
        "id": doc.id,
        "name": doc.name,
        "width": doc.width,
        "height": doc.height,
        "coordinate_system": doc.coordinate_system,
        "terrain": ascii_block.split("\n"),
        "formations": {
            faction: [list(cell) for cell in cells]
            for faction, cells in doc.formations.items()
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _as_hex(cell) -> Hex:
    if not isinstance(cell, (list, tuple)) or len(cell) != 2:
        raise ValueError(f"formation cell must be [col, row], got {cell!r}")
    return (int(cell[0]), int(cell[1]))
