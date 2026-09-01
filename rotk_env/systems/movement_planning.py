"""Orthogonal movement planning data structures.

Planning is pure: it may inspect world state, but it never spends resources,
changes HexPosition, starts animations, or records statistics. Execution consumes
a prepared :class:`MovePlan` and performs those mutations exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from ..prefabs.config import Faction

Hex = Tuple[int, int]


class MovementPlanningPolicy(str, Enum):
    """Explicit movement-legality policy selected by the caller.

    NORMAL is the benchmark/game rule. STRESS_STACK_ENDPOINT exists only so the
    scale harness can build dense dynamic-world workloads without changing the
    normal action contract: an occupied destination is allowed, but enemy-held
    traversal cells remain blocked.
    """

    NORMAL = "normal"
    STRESS_STACK_ENDPOINT = "stress_stack_endpoint"

    @classmethod
    def coerce(cls, value: "MovementPlanningPolicy | str") -> "MovementPlanningPolicy":
        if isinstance(value, cls):
            return value
        return cls(str(value))


@dataclass(frozen=True)
class MovementPlanningSnapshot:
    """Shared inputs for a batch of move planners.

    Static map geometry and dynamic occupancy are captured once so a 5k-plan
    batch does not rebuild the same board/blocker sets 5k times. ``HexPosition``
    remains authoritative; the snapshot is only valid for the revision it names.
    """

    walkable: Optional[FrozenSet[Hex]]
    terrain_costs: Mapping[Hex, int]
    occupied: FrozenSet[Hex]
    enemy_blockers_by_faction: Mapping[Faction, FrozenSet[Hex]]
    impassable: FrozenSet[Hex]
    revision: Optional[int] = None

    def blockers_for(self, faction: Optional[Faction]) -> set[Hex]:
        enemy = self.enemy_blockers_by_faction.get(faction, frozenset())
        return set(self.impassable) | set(enemy)


@dataclass(frozen=True)
class MovePlan:
    """A successful, side-effect-free movement decision ready for execution."""

    entity: int
    start: Hex
    requested_target: Hex
    resolved_target: Hex
    path: Tuple[Hex, ...]
    cost: int
    spendable_at_plan: int
    policy: MovementPlanningPolicy = MovementPlanningPolicy.NORMAL
    corrected: bool = False
    planning_revision: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": self.entity,
            "from": list(self.start),
            "requested_target": list(self.requested_target),
            "resolved_target": list(self.resolved_target),
            "path": [list(cell) for cell in self.path],
            "cost": self.cost,
            "spendable_at_plan": self.spendable_at_plan,
            "policy": self.policy.value,
            "corrected": self.corrected,
            "planning_revision": self.planning_revision,
        }


@dataclass(frozen=True)
class MovementPlanResult:
    """Planning result: either a MovePlan or the normal move failure payload."""

    success: bool
    plan: Optional[MovePlan] = None
    response: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def accepted(cls, plan: MovePlan) -> "MovementPlanResult":
        return cls(success=True, plan=plan, response={"success": True})

    @classmethod
    def rejected(cls, response: Dict[str, Any]) -> "MovementPlanResult":
        return cls(success=False, plan=None, response=response)
