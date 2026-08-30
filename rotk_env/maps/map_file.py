"""Load and dump skirmish map documents from rotk_env/maps.

A map file is JSON: size, ASCII terrain rows (north first), and per-faction
formation cells in centered offset coordinates. Spawn count, positions, and
unit types all come from this file — MapSystem only loads these.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rotk_env.maps.ascii_map import MAPS_DIR, dump_ascii_map, parse_ascii_map
from rotk_env.prefabs.config import Faction, TerrainType, UnitType

Hex = Tuple[int, int]

# CLI aliases only. Any other --scenario name loads <name>.json in this folder.
SCENARIO_ALIASES = {
    "default": "river_split.json",
    "river_split": "river_split.json",
    "river_split_offset": "river_split.json",
    "three_kingdoms": "river_split.json",
}

_UNIT_TYPE_BY_NAME = {item.value: item for item in UnitType}
_MIX_ORDER = (UnitType.INFANTRY, UnitType.ARCHER, UnitType.CAVALRY)


@dataclass
class MapDocument:
    """Parsed map file. Terrain keys are offset (col, row)."""

    id: str
    name: str
    width: int
    height: int
    terrain: Dict[Hex, TerrainType]
    formations: Dict[str, List[Hex]]
    formation_types: Dict[str, List[UnitType]] = field(default_factory=dict)
    unit_mix: list | dict | None = None
    coordinate_system: str = "centered"
    path: Path | None = None


def list_map_files() -> List[Path]:
    return sorted(p for p in MAPS_DIR.glob("*.json") if p.is_file())


def map_catalog() -> List[Dict[str, Any]]:
    """One entry per JSON file: scenario stem, display name, size."""
    items: List[Dict[str, Any]] = []
    for path in list_map_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        items.append(
            {
                "scenario": path.stem,
                "id": str(data.get("id") or path.stem),
                "name": str(data.get("name") or path.stem),
                "width": int(data.get("width") or 0),
                "height": int(data.get("height") or 0),
            }
        )
    return items


def resolve_map_path(scenario: str) -> Path:
    """CLI/scenario name → a JSON file in this directory."""
    name = SCENARIO_ALIASES.get(scenario, scenario)
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = MAPS_DIR / name
    if not path.is_file():
        available = sorted(p.name for p in list_map_files())
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
    unit_mix = _parse_unit_mix(data.get("unit_mix"), path)
    formations: Dict[str, List[Hex]] = {}
    formation_types: Dict[str, List[UnitType]] = {}
    raw_formations = data.get("formations") or {}
    for faction, cells in raw_formations.items():
        _require_faction(str(faction), path)
        parsed_cells: List[Hex] = []
        explicit_types: List[UnitType | None] = []
        for cell in cells:
            hex_cell, unit_type = _parse_slot(cell)
            if hex_cell not in terrain:
                raise ValueError(
                    f"{path}: {faction} formation cell {hex_cell} is off the board"
                )
            if terrain[hex_cell] is TerrainType.WATER:
                raise ValueError(
                    f"{path}: {faction} formation cell {hex_cell} is water"
                )
            parsed_cells.append(hex_cell)
            explicit_types.append(unit_type)
        template = _mix_template(_mix_for_faction(unit_mix, str(faction)))
        formation_types[str(faction)] = _fill_types(explicit_types, template)
        formations[str(faction)] = parsed_cells
    return MapDocument(
        id=str(data.get("id") or path.stem),
        name=str(data.get("name") or path.stem),
        width=width,
        height=height,
        terrain=terrain,
        formations=formations,
        formation_types=formation_types,
        unit_mix=unit_mix,
        coordinate_system=str(data.get("coordinate_system") or "centered"),
        path=path,
    )


def dump_map(doc: MapDocument) -> str:
    ascii_block = dump_ascii_map(
        doc.terrain, width=doc.width, height=doc.height
    ).rstrip("\n")
    payload: Dict[str, Any] = {
        "id": doc.id,
        "name": doc.name,
        "width": doc.width,
        "height": doc.height,
        "coordinate_system": doc.coordinate_system,
        "terrain": ascii_block.split("\n"),
        "formations": _dump_formations(doc),
    }
    if doc.unit_mix is not None:
        payload["unit_mix"] = doc.unit_mix
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _dump_formations(doc: MapDocument) -> Dict[str, List[list]]:
    """Keep untyped cells when mix inference matches; write type overrides."""
    out: Dict[str, List[list]] = {}
    for faction, cells in doc.formations.items():
        types = (doc.formation_types or {}).get(faction) or []
        template = _mix_template(_mix_for_faction(doc.unit_mix, faction))
        inferred = _fill_types([None] * len(cells), template)
        slots: List[list] = []
        for i, cell in enumerate(cells):
            actual = types[i] if i < len(types) else None
            expected = inferred[i] if i < len(inferred) else UnitType.INFANTRY
            if actual is None or actual == expected:
                slots.append([cell[0], cell[1]])
            else:
                slots.append([cell[0], cell[1], actual.value])
        out[faction] = slots
    return out


def _require_faction(name: str, path: Path) -> None:
    try:
        Faction(name)
    except ValueError as exc:
        known = ", ".join(item.value for item in Faction)
        raise ValueError(
            f"{path}: unknown faction {name!r}; expected one of: {known}"
        ) from exc


def _parse_slot(cell) -> Tuple[Hex, UnitType | None]:
    if isinstance(cell, dict):
        try:
            col, row = int(cell["col"]), int(cell["row"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"formation cell must have col/row, got {cell!r}") from exc
        raw_type = cell.get("type")
        return (col, row), _parse_unit_type(raw_type) if raw_type else None
    if not isinstance(cell, (list, tuple)) or len(cell) not in (2, 3):
        raise ValueError(
            f"formation cell must be [col, row] or [col, row, type], got {cell!r}"
        )
    hex_cell = (int(cell[0]), int(cell[1]))
    if len(cell) == 2:
        return hex_cell, None
    return hex_cell, _parse_unit_type(cell[2])


def _parse_unit_type(value) -> UnitType:
    name = str(value).strip().lower()
    if name not in _UNIT_TYPE_BY_NAME:
        raise ValueError(
            f"unknown unit type {value!r}; expected one of {sorted(_UNIT_TYPE_BY_NAME)}"
        )
    return _UNIT_TYPE_BY_NAME[name]


def _parse_unit_mix(raw, path: Path) -> list | dict | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return _as_mix_counts(raw, path)
    if isinstance(raw, dict):
        return {str(key): _as_mix_counts(value, path) for key, value in raw.items()}
    raise ValueError(f"{path}: unit_mix must be [inf, arch, cav] or a per-faction object")


def _as_mix_counts(raw, path: Path) -> List[int]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError(
            f"{path}: unit_mix must be [infantry, archer, cavalry] counts, got {raw!r}"
        )
    counts = [int(n) for n in raw]
    if any(n < 0 for n in counts):
        raise ValueError(f"{path}: unit_mix counts must be >= 0, got {counts}")
    return counts


def _mix_for_faction(unit_mix: list | dict | None, faction: str) -> List[int] | None:
    if unit_mix is None:
        return None
    if isinstance(unit_mix, dict):
        part = unit_mix.get(faction)
        return part
    return unit_mix


def _mix_template(counts: List[int] | None) -> List[UnitType]:
    if not counts:
        return []
    types: List[UnitType] = []
    for unit_type, n in zip(_MIX_ORDER, counts):
        types.extend([unit_type] * n)
    return types


def _fill_types(
    explicit: List[UnitType | None], template: List[UnitType]
) -> List[UnitType]:
    filled: List[UnitType] = []
    cursor = 0
    for item in explicit:
        if item is not None:
            filled.append(item)
            continue
        if template:
            filled.append(template[cursor % len(template)])
            cursor += 1
        else:
            filled.append(UnitType.INFANTRY)
    return filled
