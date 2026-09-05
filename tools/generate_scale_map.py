#!/usr/bin/env python3
"""Generate deterministic synthetic STAR maps for Phase-4 scale experiments.

The Phase-4 system-scale frontier needs map/unit-count inputs that can be
recreated from source rather than depending on local historical map files.
This generator intentionally keeps terrain simple (all plain) so resident
population, moving density, temporal burstiness, and later map-footprint
experiments can be varied explicitly instead of inheriting an accidental
terrain composition.

Generated files are ordinary STAR map JSON documents and are ignored by git.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rotk_env.maps.ascii_map import MAPS_DIR
from rotk_env.prefabs.config import Faction

Hex = Tuple[int, int]
DEFAULT_FACTIONS = ("wei", "shu", "wu")
DEFAULT_UNIT_MIX = [1, 3, 1]


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


def _normalize_factions(factions: Sequence[str]) -> List[str]:
    normalized = [str(name).strip().lower() for name in factions if str(name).strip()]
    if not normalized:
        raise ValueError("at least one faction is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("factions must be unique")
    for name in normalized:
        try:
            Faction(name)
        except ValueError as exc:
            known = ", ".join(item.value for item in Faction)
            raise ValueError(f"unknown faction {name!r}; expected one of: {known}") from exc
    return normalized


def _board_cells(size: int) -> List[Hex]:
    if size <= 0:
        raise ValueError("size must be > 0")
    if size % 2 == 0:
        raise ValueError("size must be odd so the centered map has an origin cell")
    half = size // 2
    return [(col, row) for col in range(-half, half + 1) for row in range(-half, half + 1)]


def _band_index(col: int, *, size: int, faction_count: int) -> int:
    half = size // 2
    zero_based = col + half
    return min(faction_count - 1, (zero_based * faction_count) // size)


def _band_anchor(index: int, *, size: int, faction_count: int) -> Hex:
    """Return the centered coordinate at the middle of one vertical band."""
    half = size // 2
    left = -half + (index * size) / faction_count
    right = -half + ((index + 1) * size) / faction_count
    col = int(round((left + right - 1.0) / 2.0))
    return (max(-half, min(half, col)), 0)


def _ordered_candidates(
    cells: Iterable[Hex],
    *,
    anchor: Hex,
    tie_break: Dict[Hex, float],
) -> List[Hex]:
    return sorted(
        cells,
        key=lambda cell: (
            abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]),
            tie_break[cell],
            cell[0],
            cell[1],
        ),
    )


def generate_formations(
    *,
    size: int,
    total_units: int,
    factions: Sequence[str] = DEFAULT_FACTIONS,
    seed: int = 42,
) -> Dict[str, List[Hex]]:
    """Generate deterministic, unique formation cells with spatial separation.

    The board is partitioned into vertical faction bands. Each faction fills
    cells near the center of its own band first. If a requested quota exceeds
    the local band capacity, the deterministic fallback takes the nearest unused
    board cells. No two units share a spawn cell.
    """
    names = _normalize_factions(factions)
    cells = _board_cells(size)
    if total_units > len(cells):
        raise ValueError(
            f"requested {total_units} units but a {size}x{size} map has only {len(cells)} cells"
        )

    quotas = _balanced_quotas(total_units, names)
    rng = random.Random(seed)
    tie_break = {cell: rng.random() for cell in cells}

    territories: Dict[str, List[Hex]] = {name: [] for name in names}
    for cell in cells:
        owner_index = _band_index(cell[0], size=size, faction_count=len(names))
        territories[names[owner_index]].append(cell)

    assigned: Dict[str, List[Hex]] = {name: [] for name in names}
    used: set[Hex] = set()
    anchors = {
        name: _band_anchor(index, size=size, faction_count=len(names))
        for index, name in enumerate(names)
    }

    for name in names:
        for cell in _ordered_candidates(
            territories[name], anchor=anchors[name], tie_break=tie_break
        ):
            if len(assigned[name]) >= quotas[name]:
                break
            assigned[name].append(cell)
            used.add(cell)

    fallback = {
        name: _ordered_candidates(cells, anchor=anchors[name], tie_break=tie_break)
        for name in names
    }
    cursor = {name: 0 for name in names}
    while any(len(assigned[name]) < quotas[name] for name in names):
        progress = False
        for name in names:
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


def build_scale_payload(
    *,
    size: int,
    total_units: int,
    factions: Sequence[str] = DEFAULT_FACTIONS,
    seed: int = 42,
) -> dict:
    names = _normalize_factions(factions)
    formations = generate_formations(
        size=size,
        total_units=total_units,
        factions=names,
        seed=seed,
    )
    scenario = f"_generated_scale_{size}x{size}_{total_units}"
    return {
        "id": scenario,
        "name": f"Generated Scale {size}x{size} / {total_units} Units",
        "width": size,
        "height": size,
        "coordinate_system": "centered",
        "unit_mix": list(DEFAULT_UNIT_MIX),
        "terrain": ["." * size for _ in range(size)],
        "formations": {
            name: [[col, row] for col, row in formations[name]] for name in names
        },
        "scale_profile": {
            "generator": "phase4-synthetic-v1",
            "terrain": "all_plain",
            "placement": "balanced_vertical_bands",
            "total_units": total_units,
            "seed": seed,
            "factions": names,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic synthetic map for STAR Phase-4 scale experiments"
    )
    parser.add_argument("--size", type=int, default=91, help="Odd square map size. Default: 91.")
    parser.add_argument("--units", type=int, required=True, help="Total resident unit count.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--factions",
        default=",".join(DEFAULT_FACTIONS),
        help="Comma-separated factions. Default: wei,shu,wu.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output map JSON. Default: rotk_env/maps/"
            "_generated_scale_<size>x<size>_<units>.json"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    factions = [part.strip() for part in args.factions.split(",") if part.strip()]
    payload = build_scale_payload(
        size=args.size,
        total_units=args.units,
        factions=factions,
        seed=args.seed,
    )
    output = args.output or MAPS_DIR / f"_generated_scale_{args.size}x{args.size}_{args.units}.json"
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = {name: len(payload["formations"][name]) for name in factions}
    print(
        f"Generated {output}: size={args.size}x{args.size} "
        f"units={sum(counts.values())} counts={counts} seed={args.seed} "
        f"scenario={payload['id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
