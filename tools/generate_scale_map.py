#!/usr/bin/env python3
"""Generate deterministic high-unit-count STAR maps for scale profiling.

The source map supplies terrain, faction anchors, and unit_mix. This tool only
replaces formation cells, so 20/200/500-unit runs can share the same board and
unit-type mix while changing unit count in a repeatable way.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from rotk_env.maps.map_file import MapDocument, load_map, resolve_map_path
from rotk_env.prefabs.config import Faction, TerrainType

Hex = Tuple[int, int]


def _hex_distance(a: Hex, b: Hex) -> int:
    """Flat-top even-q distance used by STAR."""
    aq, ar = a[0], a[1] - (a[0] // 2)
    bq, br = b[0], b[1] - (b[0] // 2)
    dq = aq - bq
    dr = ar - br
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def _formation_anchor(cells: Sequence[Hex]) -> Hex:
    """Pick a deterministic medoid-like anchor from an existing formation."""
    if not cells:
        raise ValueError("selected faction has no source formation to anchor placement")
    return min(
        cells,
        key=lambda cell: (
            sum(_hex_distance(cell, other) for other in cells),
            cell[0],
            cell[1],
        ),
    )


def _balanced_quotas(total_units: int, factions: Sequence[str]) -> Dict[str, int]:
    if total_units <= 0:
        raise ValueError("total_units must be > 0")
    if not factions:
        raise ValueError("at least one faction is required")
    base, remainder = divmod(total_units, len(factions))
    return {
        faction: base + (1 if index < remainder else 0)
        for index, faction in enumerate(factions)
    }


def generate_scale_formations(
    doc: MapDocument,
    *,
    total_units: int,
    factions: Sequence[str],
    seed: int = 42,
) -> Dict[str, List[Hex]]:
    """Return non-overlapping, deterministic formation cells for a scale run.

    Each faction grows outward from its source-map formation anchor. Passable
    cells are first partitioned by nearest anchor (Voronoi-style) to preserve
    spatial separation; if a faction's local region is too small, it borrows
    the nearest remaining cells. Counts are balanced to within one unit.
    """
    normalized = [str(name).strip().lower() for name in factions if str(name).strip()]
    if len(set(normalized)) != len(normalized):
        raise ValueError("factions must be unique")
    for name in normalized:
        try:
            Faction(name)
        except ValueError as exc:
            known = ", ".join(item.value for item in Faction)
            raise ValueError(f"unknown faction {name!r}; expected one of: {known}") from exc
        if not doc.formations.get(name):
            raise ValueError(
                f"source map {doc.id!r} has no {name!r} formation; cannot infer its placement anchor"
            )

    passable = sorted(
        cell for cell, terrain in doc.terrain.items() if terrain is not TerrainType.WATER
    )
    if total_units > len(passable):
        raise ValueError(
            f"requested {total_units} units but map {doc.id!r} has only "
            f"{len(passable)} passable cells; use a larger map"
        )

    quotas = _balanced_quotas(total_units, normalized)
    anchors = {name: _formation_anchor(doc.formations[name]) for name in normalized}
    faction_order = {name: index for index, name in enumerate(normalized)}

    # Stable pseudo-random tie breaking prevents long straight coordinate bands
    # while preserving exact reproducibility for a given seed.
    rng = random.Random(seed)
    tie_break = {
        (name, cell): rng.random()
        for name in normalized
        for cell in passable
    }

    territories: Dict[str, List[Hex]] = {name: [] for name in normalized}
    for cell in passable:
        owner = min(
            normalized,
            key=lambda name: (
                _hex_distance(cell, anchors[name]),
                faction_order[name],
            ),
        )
        territories[owner].append(cell)

    def ordered_candidates(name: str, cells: Iterable[Hex]) -> List[Hex]:
        return sorted(
            cells,
            key=lambda cell: (
                _hex_distance(cell, anchors[name]),
                tie_break[(name, cell)],
                cell[0],
                cell[1],
            ),
        )

    assigned: Dict[str, List[Hex]] = {name: [] for name in normalized}
    used: set[Hex] = set()

    # Prefer each faction's own nearest-anchor region first.
    for name in normalized:
        for cell in ordered_candidates(name, territories[name]):
            if len(assigned[name]) >= quotas[name]:
                break
            assigned[name].append(cell)
            used.add(cell)

    # Fill any region deficit from the globally nearest unused cells. Iterate
    # round-robin so earlier factions cannot consume all shared fallback cells.
    fallback = {
        name: ordered_candidates(name, passable)
        for name in normalized
    }
    cursor = {name: 0 for name in normalized}
    while any(len(assigned[name]) < quotas[name] for name in normalized):
        progress = False
        for name in normalized:
            if len(assigned[name]) >= quotas[name]:
                continue
            candidates = fallback[name]
            while cursor[name] < len(candidates) and candidates[cursor[name]] in used:
                cursor[name] += 1
            if cursor[name] >= len(candidates):
                continue
            cell = candidates[cursor[name]]
            cursor[name] += 1
            assigned[name].append(cell)
            used.add(cell)
            progress = True
        if not progress:
            raise RuntimeError("could not allocate requested formation cells")

    return assigned


def _resolve_source(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_file():
        return candidate
    return resolve_map_path(value)


def build_scale_payload(
    source: Path,
    *,
    total_units: int,
    factions: Sequence[str],
    seed: int,
) -> dict:
    doc = load_map(source)
    formations = generate_scale_formations(
        doc,
        total_units=total_units,
        factions=factions,
        seed=seed,
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["id"] = f"{doc.id}-scale-{total_units}"
    payload["name"] = f"{doc.name} Scale {total_units}"
    payload["formations"] = {
        faction: [[col, row] for col, row in formations[faction]]
        for faction in factions
    }
    payload["scale_profile"] = {
        "source_map": doc.id,
        "total_units": total_units,
        "seed": seed,
        "factions": list(factions),
        "placement": "nearest-anchor-balanced",
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic STAR scale-test map from an existing map."
    )
    parser.add_argument(
        "--map",
        default="chibi",
        help="Scenario name (e.g. chibi) or path to a STAR map JSON.",
    )
    parser.add_argument("--units", type=int, required=True, help="Total units to place.")
    parser.add_argument(
        "--factions",
        default="wei,shu,wu",
        help="Comma-separated factions to distribute units across.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic placement seed.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Default: rotk_env/maps/<source>-scale-<units>.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    factions = [part.strip().lower() for part in args.factions.split(",") if part.strip()]
    source = _resolve_source(args.map)
    payload = build_scale_payload(
        source,
        total_units=args.units,
        factions=factions,
        seed=args.seed,
    )
    output = args.output or source.with_name(f"{source.stem}-scale-{args.units}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = {name: len(payload["formations"].get(name, ())) for name in factions}
    print(
        f"Generated {output}: units={sum(counts.values())} "
        f"counts={counts} seed={args.seed} source={source.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
