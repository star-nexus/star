"""Renderer-independent fixtures; importing Web tests must not load pygame."""
import datetime
import time
import pytest


@pytest.fixture
def frozen(monkeypatch):
    now = [1720000000.]
    monkeypatch.setattr(time, 'time', lambda: now[0])

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 12, 12)

    monkeypatch.setattr(datetime, 'datetime', Frozen)
    return now
