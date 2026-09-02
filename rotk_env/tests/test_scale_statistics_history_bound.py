"""Regression coverage for bounded scale/window visibility history."""

from rotk_env.components import UnitObservation, VisibilityTracker
from rotk_env.prefabs.config import Faction
from rotk_env.systems.scale_statistics_system import StatisticsSystem


def test_scale_visibility_history_keeps_only_latest_change():
    system = StatisticsSystem()
    tracker = VisibilityTracker()
    observation = UnitObservation()

    appended, trimmed = system._record_visibility_change(
        7,
        {Faction.WEI},
        tracker,
        observation,
        1.0,
    )
    assert (appended, trimmed) == (1, 0)
    assert len(tracker.visibility_history[7]) == 1
    assert observation.is_visible_to == {Faction.WEI}

    appended, trimmed = system._record_visibility_change(
        7,
        {Faction.WEI, Faction.SHU},
        tracker,
        observation,
        2.0,
    )
    assert (appended, trimmed) == (1, 1)
    assert len(tracker.visibility_history[7]) == 1
    latest = tracker.visibility_history[7][0]
    assert latest["timestamp"] == 2.0
    assert set(latest["visible_to"]) == {Faction.WEI, Faction.SHU}
    assert latest["newly_spotted"] is True
    assert latest["lost_sight"] is False
    assert observation.is_visible_to == {Faction.WEI, Faction.SHU}


def test_scale_visibility_history_does_not_allocate_when_relation_is_unchanged():
    system = StatisticsSystem()
    tracker = VisibilityTracker()
    observation = UnitObservation(is_visible_to={Faction.WEI})
    tracker.visibility_history[7] = [
        {
            "timestamp": 1.0,
            "visible_to": [Faction.WEI],
            "newly_spotted": False,
            "lost_sight": False,
        }
    ]

    appended, trimmed = system._record_visibility_change(
        7,
        {Faction.WEI},
        tracker,
        observation,
        2.0,
    )

    assert (appended, trimmed) == (0, 0)
    assert len(tracker.visibility_history[7]) == 1
    assert tracker.visibility_history[7][0]["timestamp"] == 1.0
