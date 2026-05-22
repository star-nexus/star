"""
Multi-agent team coordination components.

These power the "multiple agents per faction" research mode, where two or
more LLM agents share a single faction and divide the work between them.
The pieces are:

* `unit_owners` — optional per-unit ownership. When set, only the owning
  agent may issue unit-targeted actions for that unit. Empty by default,
  so single-agent mode is unaffected.
* `faction_members` — registry of every agent_id that has registered to
  each faction, in the order they registered. Used to fan out team chat
  and to enumerate teammates.
* `team_inboxes` — per-agent message queues populated by `broadcast_to_team`.
  Agents pull these with `read_team_messages`.
* `team_history` — capped append-only log per faction, for post-game
  analysis of multi-agent communication patterns.

All state is held on a single singleton so it survives in `GameStats`
context and can be serialized into settlement reports.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set

from framework import SingletonComponent


# Soft cap so a chatty pair of agents can't OOM the env.
_DEFAULT_HISTORY_CAP = 256
_DEFAULT_INBOX_CAP = 64


@dataclass
class TeamCoordination(SingletonComponent):
    """Singleton state for multi-agent team coordination."""

    # unit_entity_id -> agent_id of the claimant
    unit_owners: Dict[int, str] = field(default_factory=dict)

    # faction_key ("wei"|"shu"|"wu") -> ordered list of agent_ids
    faction_members: Dict[str, List[str]] = field(default_factory=dict)

    # agent_id -> queued messages addressed to that agent (deque for FIFO with cap)
    team_inboxes: Dict[str, Deque[Dict]] = field(default_factory=dict)

    # faction_key -> append-only broadcast log (capped) for analysis / replay
    team_history: Dict[str, Deque[Dict]] = field(default_factory=dict)

    # Tunable caps — tests may shrink/extend these.
    history_cap: int = _DEFAULT_HISTORY_CAP
    inbox_cap: int = _DEFAULT_INBOX_CAP

    # ----- registry --------------------------------------------------------

    def register_member(self, faction_key: str, agent_id: str) -> bool:
        """Record that `agent_id` is part of `faction_key`'s team.

        Returns True if the membership was newly added, False if the agent
        was already a known member of this faction.
        """
        members = self.faction_members.setdefault(faction_key, [])
        if agent_id in members:
            return False
        members.append(agent_id)
        self.team_inboxes.setdefault(agent_id, deque(maxlen=self.inbox_cap))
        return True

    def teammates_of(self, faction_key: str, agent_id: Optional[str]) -> List[str]:
        """Return every other agent_id in the same faction, in registration order."""
        members = self.faction_members.get(faction_key, [])
        if agent_id is None:
            return list(members)
        return [a for a in members if a != agent_id]

    # ----- ownership -------------------------------------------------------

    def claim_units(
        self,
        agent_id: str,
        unit_ids: List[int],
        exclusive: bool = True,
    ) -> Dict[str, object]:
        """Try to claim `unit_ids` for `agent_id`.

        Args:
            agent_id: requesting agent.
            unit_ids: entity ids the agent wants to own.
            exclusive: when True (default), refuse the whole claim if any
                unit is already owned by a different agent. When False,
                forcibly transfer ownership.

        Returns a dict with the outcome — never raises so the caller can
        forward it directly to the LLM.
        """
        if exclusive:
            conflicts = {
                uid: self.unit_owners[uid]
                for uid in unit_ids
                if uid in self.unit_owners and self.unit_owners[uid] != agent_id
            }
            if conflicts:
                return {
                    "success": False,
                    "claimed": [],
                    "conflicts": conflicts,
                    "message": (
                        f"Exclusive claim refused: "
                        f"{len(conflicts)} units already owned by other agents."
                    ),
                }

        for uid in unit_ids:
            self.unit_owners[uid] = agent_id
        return {
            "success": True,
            "claimed": list(unit_ids),
            "conflicts": {},
            "message": f"Claimed {len(unit_ids)} units for agent {agent_id}.",
        }

    def release_units(
        self, agent_id: str, unit_ids: Optional[List[int]] = None
    ) -> Dict[str, object]:
        """Release ownership of `unit_ids` (or all of agent's units when None)."""
        released: List[int] = []
        if unit_ids is None:
            unit_ids = [uid for uid, owner in self.unit_owners.items() if owner == agent_id]
        for uid in unit_ids:
            if self.unit_owners.get(uid) == agent_id:
                del self.unit_owners[uid]
                released.append(uid)
        return {
            "success": True,
            "released": released,
            "message": f"Released {len(released)} units.",
        }

    def owner_of(self, unit_id: int) -> Optional[str]:
        return self.unit_owners.get(unit_id)

    def is_authorized(self, agent_id: Optional[str], unit_id: int) -> bool:
        """Return True iff `agent_id` may act on `unit_id`.

        Default policy: when nobody has claimed the unit, anyone in the
        right faction is authorized (preserves single-agent semantics).
        Once a unit is claimed, only the owner may act on it.
        """
        owner = self.unit_owners.get(unit_id)
        if owner is None:
            return True
        return agent_id == owner

    # ----- messaging -------------------------------------------------------

    def broadcast(
        self,
        sender_agent_id: str,
        faction_key: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, object]:
        """Deliver `text` to every teammate of `sender_agent_id` in `faction_key`."""
        teammates = self.teammates_of(faction_key, sender_agent_id)
        message = {
            "from": sender_agent_id,
            "faction": faction_key,
            "ts": time.time(),
            "text": text,
            "metadata": metadata or {},
        }

        delivered: List[str] = []
        for member_id in teammates:
            inbox = self.team_inboxes.setdefault(
                member_id, deque(maxlen=self.inbox_cap)
            )
            inbox.append(message)
            delivered.append(member_id)

        # Append to faction-level history regardless of delivery count, so
        # post-game analysis still sees solo broadcasts.
        history = self.team_history.setdefault(
            faction_key, deque(maxlen=self.history_cap)
        )
        history.append(message)

        return {
            "success": True,
            "delivered_to": delivered,
            "teammate_count": len(teammates),
            "message": (
                f"Delivered to {len(delivered)} teammate(s)."
                if delivered
                else "No teammates currently registered; message recorded in history."
            ),
        }

    def drain_inbox(self, agent_id: str) -> List[Dict]:
        """Return queued messages for `agent_id` and clear the inbox."""
        inbox = self.team_inboxes.get(agent_id)
        if not inbox:
            return []
        items = list(inbox)
        inbox.clear()
        return items

    # ----- snapshot --------------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """JSON-serializable snapshot for settlement reports."""
        return {
            "unit_owners": dict(self.unit_owners),
            "faction_members": {k: list(v) for k, v in self.faction_members.items()},
            "history_lengths": {k: len(v) for k, v in self.team_history.items()},
            "pending_inbox_sizes": {k: len(v) for k, v in self.team_inboxes.items()},
        }
