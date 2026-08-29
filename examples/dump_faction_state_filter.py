"""Dump get_faction_state after rotk_agent.core.filters compression.

No Hub, no window. Builds a local skirmish world, queries ENV, then prints
the compact schema that enters the agent history.

Usage
-----

    uv run python examples/dump_faction_state_filter.py
    uv run python examples/dump_faction_state_filter.py --faction wei --fog-off
    uv run python examples/dump_faction_state_filter.py --raw
"""

from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rotk_agent.core.filters import (
    DEFAULT_FACTION_STATE_FILTER,
    filter_faction_state_result,
    resolve_faction_state_filter,
)
from rotk_env.components import FogOfWar, set_fog_enabled
from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.systems.llm_action_handler import LLMActionHandler


def _world(seed: int):
    return build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.TURN_BASED,
        seed=seed,
        hub_url=None,
        display="none",
    )


def _summarize(raw: dict, compact: dict) -> None:
    raw_units = raw.get("units") or []
    compact_units = compact.get("units") or []
    terrain = compact.get("terrain") or {}
    print(
        f"fog={compact.get('fog')}  counts={compact.get('counts')}  "
        f"enemies={len(compact.get('enemies') or [])}"
    )
    print(
        f"terrain tiles raw={len(raw.get('visible_terrain') or [])}  "
        f"compact types={ {k: len(v) for k, v in terrain.items()} }"
    )
    for raw_unit, row in zip(raw_units, compact_units):
        raw_reach = raw_unit.get("reachable") or []
        anchor = row[12] if len(row) > 12 and isinstance(row[12], dict) else {}
        compact_reach = anchor.get("reachable") or []
        print(
            f"  #{row[0]}  {row[1]}  ({row[2]}, {row[3]})  "
            f"AP={row[6]} MP={row[7]}  "
            f"reachable {len(raw_reach)}->{len(compact_reach)}  "
            f"attackable={anchor.get('attackable', [])}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print filter.py compact get_faction_state (no Hub)."
    )
    parser.add_argument("--faction", default="wei", choices=("wei", "shu", "wu"))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--fog-off",
        action="store_true",
        help="Lift fog (key 1) before querying.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Also print the uncompressed ENV payload.",
    )
    args = parser.parse_args()

    world = _world(args.seed)
    if args.fog_off:
        fog = world.get_singleton_component(FogOfWar)
        if fog is not None:
            set_fog_enabled(fog, False)

    raw = LLMActionHandler(world).handle_faction_state({"faction": args.faction})
    spec = resolve_faction_state_filter(DEFAULT_FACTION_STATE_FILTER)
    compact = filter_faction_state_result(raw, spec)

    print("── summary ──")
    _summarize(raw, compact)
    if args.raw:
        print("\n── ENV raw ──")
        print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))
    print("\n── filter.py compact ──")
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
