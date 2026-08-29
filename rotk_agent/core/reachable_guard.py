"""Shadow-check move targets against the latest get_faction_state reachable set.

The validator always runs. It does not recompute legality — it compares the
LLM's ``target_position`` to the compact ``reachable`` list the model just
saw. Packs without that channel (A, C, E) and units missing from the snapshot
are skipped, not flagged.

Enforcement is optional: when on, the agent rejects the call before ENV sees
it and returns the current reachable list so the model can copy a legal hex.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .filters import OWN_UNIT_BASIC_COLUMNS

Hex = Tuple[int, int]
AFFORDANCE_INDEX = len(OWN_UNIT_BASIC_COLUMNS)


def as_hex(value: Any) -> Optional[Hex]:
    """Accept ``{col,row}``, nested position objects, or ``[col, row]``."""
    if isinstance(value, dict):
        if "col" in value and "row" in value:
            try:
                return (int(value["col"]), int(value["row"]))
            except (TypeError, ValueError):
                return None
        for key in ("target_position", "position"):
            nested = as_hex(value.get(key))
            if nested is not None:
                return nested
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    return None


def index_reachable(filtered: Dict[str, Any]) -> Dict[int, List[Hex]]:
    """unit_id → reachable hexes for rows that actually carry the channel."""
    units = filtered.get("units")
    if not isinstance(units, list):
        return {}

    index: Dict[int, List[Hex]] = {}
    for row in units:
        if not isinstance(row, list) or not row:
            continue
        try:
            unit_id = int(row[0])
        except (TypeError, ValueError):
            continue
        if len(row) <= AFFORDANCE_INDEX:
            continue
        anchor = row[AFFORDANCE_INDEX]
        if not isinstance(anchor, dict) or "reachable" not in anchor:
            continue
        hexes: List[Hex] = []
        for item in anchor.get("reachable") or []:
            pair = as_hex(item)
            if pair is not None:
                hexes.append(pair)
        index[unit_id] = hexes
    return index


def parse_move(arguments: Optional[Dict[str, Any]]) -> Optional[Tuple[int, Hex]]:
    if not isinstance(arguments, dict):
        return None
    action = arguments.get("action")
    if not (isinstance(action, str) and action.strip().lower() == "move"):
        return None
    params = arguments.get("params")
    if not isinstance(params, dict):
        return None
    try:
        unit_id = int(params["unit_id"])
    except (KeyError, TypeError, ValueError):
        return None
    target = as_hex(params.get("target_position")) or as_hex(params)
    if target is None:
        return None
    return unit_id, target


@dataclass(frozen=True)
class ReachableMismatch:
    unit_id: int
    target: Hex
    reachable: List[Hex]

    def as_event(self, *, enforced: bool) -> Dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "target": {"col": self.target[0], "row": self.target[1]},
            "reachable": [[col, row] for col, row in self.reachable],
            "enforced": enforced,
        }

    def tool_error(self) -> Dict[str, Any]:
        return {
            "success": False,
            "result": False,
            "reason": "not_in_reachable",
            "details": "target not in latest reachable",
            "unit_id": self.unit_id,
            "target_position": {"col": self.target[0], "row": self.target[1]},
        }


class ReachableGuard:
    """Latest compact reachable snapshot, plus an optional intercept switch."""

    def __init__(self, enforce: bool = False):
        self.enforce = enforce
        self._reachable: Dict[int, List[Hex]] = {}

    def observe_faction_state(self, filtered: Any) -> None:
        if not isinstance(filtered, dict) or "units" not in filtered:
            return
        self._reachable = index_reachable(filtered)

    def check_move(
        self, arguments: Optional[Dict[str, Any]]
    ) -> Optional[ReachableMismatch]:
        parsed = parse_move(arguments)
        if parsed is None:
            return None
        unit_id, target = parsed
        snapshot = self._reachable
        if unit_id not in snapshot:
            return None
        reachable = snapshot[unit_id]
        if target in reachable:
            return None
        return ReachableMismatch(
            unit_id=unit_id, target=target, reachable=list(reachable)
        )


__all__ = [
    "AFFORDANCE_INDEX",
    "ReachableGuard",
    "ReachableMismatch",
    "as_hex",
    "index_reachable",
    "parse_move",
]
