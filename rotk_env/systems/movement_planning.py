"""Orthogonal movement planning data structures.

Planning is pure: it may inspect world state, but it never spends resources,
changes HexPosition, starts animations, or records statistics. Execution consumes
a prepared :class:`MovePlan` and performs those mutations exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import AbstractSet, Any, Dict, FrozenSet, Mapping, Optional, Tuple

from ..prefabs.config import Faction

Hex = Tuple[int, int]


class MovementPlanningPolicy(str, Enum):
    """Explicit movement-legality policy selected by the caller."""

    NORMAL = "normal"
    STRESS_STACK_ENDPOINT = "stress_stack_endpoint"

    @classmethod
    def coerce(cls, value: "MovementPlanningPolicy | str") -> "MovementPlanningPolicy":
        if isinstance(value, cls):
            return value
        return cls(str(value))


class EndpointUnblockedObstacles:
    """Zero-copy membership view that exempts one endpoint from blockers.

    PathFinding only asks ``neighbor in obstacles``. This view therefore lets a
    stress planner enter one occupied target without copying a thousands-cell
    blocker set for every plan and without making any other enemy cell traversable.
    """

    __slots__ = ("base", "endpoint")

    def __init__(self, base: AbstractSet[Hex], endpoint: Hex):
        self.base = base
        self.endpoint = endpoint

    def __contains__(self, cell: object) -> bool:
        return cell != self.endpoint and cell in self.base


@dataclass(frozen=True)
class MovementPlanningSnapshot:
    """Shared read-only inputs for a batch of move planners.

    Dynamic occupancy/blockers and static map geometry are captured once. Batch
    planners reuse these exact containers; they must not clone board-sized sets
    or dictionaries per unit.
    """

    walkable: Optional[FrozenSet[Hex]]
    terrain_costs: Mapping[Hex, int]
    occupied: FrozenSet[Hex]
    blockers_by_faction: Mapping[Faction, FrozenSet[Hex]]
    revision: Optional[int] = None

    def blockers_for(self, faction: Optional[Faction]) -> AbstractSet[Hex]:
        return self.blockers_by_faction.get(faction, frozenset())


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
