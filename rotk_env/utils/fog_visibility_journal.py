"""Revisioned visibility-delta journal shared by simulation and presentation.

Vision owns semantic visibility. Renderers and other presentation consumers should
not inspect VisionSystem internals or diff whole faction visibility sets every
frame. This journal carries only the tiles whose *faction-level* visibility state
may have changed.

Events are bounded. A consumer that falls behind the retained history receives a
``history_lost`` result and must rebuild from authoritative FogOfWar state once.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, FrozenSet, Iterable, Mapping, Optional, Set, Tuple

from framework import World

from ..prefabs.config import Faction

Hex = Tuple[int, int]
_JOURNAL_ATTR = "_fog_visibility_change_journal"


@dataclass(frozen=True)
class FogVisibilityDeltaEvent:
    revision: int
    changes: Tuple[Tuple[Faction, FrozenSet[Hex]], ...]

    def tiles_for(self, faction: Faction) -> FrozenSet[Hex]:
        for event_faction, tiles in self.changes:
            if event_faction == faction:
                return tiles
        return frozenset()


@dataclass(frozen=True)
class FogVisibilityDeltaBatch:
    revision: int
    dirty_tiles: FrozenSet[Hex]
    history_lost: bool = False
    events_scanned: int = 0


class FogVisibilityChangeJournal:
    """Bounded multi-consumer journal of faction-visibility tile deltas."""

    def __init__(self, max_events: int = 2048):
        self.max_events = max(8, int(max_events))
        self.revision = 0
        self._events: Deque[FogVisibilityDeltaEvent] = deque(
            maxlen=self.max_events
        )

    @property
    def retained_events(self) -> int:
        return len(self._events)

    @property
    def oldest_revision(self) -> int:
        if not self._events:
            return self.revision + 1
        return self._events[0].revision

    def publish(self, changes: Mapping[Faction, Iterable[Hex]]) -> int:
        normalized = []
        for faction, tiles in changes.items():
            frozen = frozenset(tiles)
            if frozen:
                normalized.append((faction, frozen))
        if not normalized:
            return self.revision

        normalized.sort(key=lambda item: item[0].value)
        self.revision += 1
        self._events.append(
            FogVisibilityDeltaEvent(
                revision=self.revision,
                changes=tuple(normalized),
            )
        )
        return self.revision

    def changes_since(
        self,
        revision: Optional[int],
        faction: Faction,
    ) -> FogVisibilityDeltaBatch:
        """Return union of dirty tiles after ``revision`` for one faction.

        ``revision=None`` means the caller has no valid presentation baseline and
        must build from authoritative FogOfWar state.
        """
        current = self.revision
        if revision is None:
            return FogVisibilityDeltaBatch(
                revision=current,
                dirty_tiles=frozenset(),
                history_lost=True,
                events_scanned=0,
            )
        revision = int(revision)
        if revision >= current:
            return FogVisibilityDeltaBatch(
                revision=current,
                dirty_tiles=frozenset(),
                history_lost=False,
                events_scanned=0,
            )

        if self._events and revision < self._events[0].revision - 1:
            return FogVisibilityDeltaBatch(
                revision=current,
                dirty_tiles=frozenset(),
                history_lost=True,
                events_scanned=0,
            )

        dirty: Set[Hex] = set()
        scanned = 0
        for event in self._events:
            if event.revision <= revision:
                continue
            scanned += 1
            dirty.update(event.tiles_for(faction))
        return FogVisibilityDeltaBatch(
            revision=current,
            dirty_tiles=frozenset(dirty),
            history_lost=False,
            events_scanned=scanned,
        )


def get_fog_visibility_journal(world: World) -> FogVisibilityChangeJournal:
    journal = getattr(world, _JOURNAL_ATTR, None)
    if journal is None:
        journal = FogVisibilityChangeJournal()
        setattr(world, _JOURNAL_ATTR, journal)
    return journal


def publish_fog_visibility_delta(
    world: World,
    changes: Mapping[Faction, Iterable[Hex]],
) -> int:
    return get_fog_visibility_journal(world).publish(changes)
