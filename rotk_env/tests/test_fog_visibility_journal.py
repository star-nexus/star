from framework.ecs.world import World

from rotk_env.prefabs.config import Faction
from rotk_env.utils.fog_visibility_journal import (
    FogVisibilityChangeJournal,
    get_fog_visibility_journal,
    publish_fog_visibility_delta,
)


def test_journal_is_revisioned_and_multi_consumer_safe():
    world = World()
    journal = get_fog_visibility_journal(world)

    publish_fog_visibility_delta(world, {Faction.WEI: {(1, 2), (2, 2)}})
    first_revision = journal.revision
    publish_fog_visibility_delta(
        world,
        {
            Faction.WEI: {(3, 2)},
            Faction.SHU: {(-1, -1)},
        },
    )

    wei = journal.changes_since(0, Faction.WEI)
    shu = journal.changes_since(first_revision, Faction.SHU)

    assert wei.history_lost is False
    assert wei.dirty_tiles == frozenset({(1, 2), (2, 2), (3, 2)})
    assert shu.dirty_tiles == frozenset({(-1, -1)})
    # Reading one consumer never clears events needed by another.
    again = journal.changes_since(0, Faction.WEI)
    assert again.dirty_tiles == wei.dirty_tiles


def test_journal_reports_history_gap_instead_of_returning_partial_delta():
    journal = FogVisibilityChangeJournal(max_events=8)
    for index in range(12):
        journal.publish({Faction.WEI: {(index, 0)}})

    stale = journal.changes_since(0, Faction.WEI)
    recent = journal.changes_since(journal.revision - 2, Faction.WEI)

    assert stale.history_lost is True
    assert stale.dirty_tiles == frozenset()
    assert recent.history_lost is False
    assert recent.dirty_tiles == frozenset({(10, 0), (11, 0)})


def test_empty_publish_does_not_advance_revision():
    journal = FogVisibilityChangeJournal()
    before = journal.revision
    journal.publish({Faction.WEI: set()})
    assert journal.revision == before
