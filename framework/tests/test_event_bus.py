"""EventBus: handlers must not see subscribe/unsubscribe that happen mid-publish."""

from framework.engine.events import Event, EventBus


class _Probe(Event):
    pass


def test_publish_does_not_deliver_to_subscriber_added_during_publish():
    bus = EventBus()
    seen = []

    def late(_event):
        seen.append("late")

    def first(_event):
        seen.append("first")
        bus.subscribe(_Probe, late)

    bus.subscribe(_Probe, first)
    try:
        bus.publish(_Probe())
        assert seen == ["first"]
        bus.publish(_Probe())
        assert seen == ["first", "first", "late"]
    finally:
        bus.unsubscribe(_Probe, first)
        bus.unsubscribe(_Probe, late)


def test_publish_still_calls_listener_unsubscribed_by_an_earlier_handler():
    bus = EventBus()
    seen = []

    def first(_event):
        seen.append("first")
        bus.unsubscribe(_Probe, second)

    def second(_event):
        seen.append("second")

    bus.subscribe(_Probe, first)
    bus.subscribe(_Probe, second)
    try:
        bus.publish(_Probe())
        assert seen == ["first", "second"]
    finally:
        bus.unsubscribe(_Probe, first)
        bus.unsubscribe(_Probe, second)
