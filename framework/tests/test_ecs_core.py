"""ECS core behaviour: system scheduling, the `enabled` flag, query signatures.

`framework/` had no tests of its own; the ECS was only exercised indirectly
through ENV rule tests, so `System.enabled` sat unread by `World.update` for as
long as it existed.
"""

from dataclasses import dataclass, field

import pytest

from framework import Component, System, World


@dataclass
class Position(Component):
    x: int = 0
    y: int = 0


@dataclass
class Velocity(Component):
    dx: int = 0
    dy: int = 0


@dataclass
class Tag(Component):
    label: str = ""


class Recorder(System):
    """Counts its own updates so scheduling is observable."""

    def __init__(self, name="recorder", priority=100, required=None, log=None):
        super().__init__(required_components=required, priority=priority)
        self.name = name
        self.calls = 0
        self.log = log if log is not None else []

    def initialize(self, world):
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time):
        self.calls += 1
        self.log.append(self.name)


# ------------------------------------------------------------------- enabled


def test_disabled_system_is_skipped():
    """Regression: `enabled` existed but `World.update` never read it."""
    world = World()
    system = Recorder()
    world.add_system(system)

    world.update(0.016)
    assert system.calls == 1

    system.enabled = False
    world.update(0.016)
    world.update(0.016)
    assert system.calls == 1, "a disabled system must not be updated"

    system.enabled = True
    world.update(0.016)
    assert system.calls == 2, "re-enabling must resume updates"


def test_systems_default_to_enabled():
    assert Recorder().enabled is True


def test_disabling_one_system_does_not_affect_others():
    world = World()
    log = []
    a, b = Recorder("a", log=log), Recorder("b", log=log)
    world.add_system(a)
    world.add_system(b)

    a.enabled = False
    world.update(0.016)
    assert log == ["b"]


# ------------------------------------------------------------------ priority


def test_systems_run_in_priority_order():
    world = World()
    log = []
    world.add_system(Recorder("late", priority=200, log=log))
    world.add_system(Recorder("early", priority=10, log=log))
    world.add_system(Recorder("middle", priority=100, log=log))

    world.update(0.016)
    assert log == ["early", "middle", "late"]


# -------------------------------------------------------- required_components


def test_matched_entities_runs_the_declared_signature():
    """Regression: `required_components` was declared and never read."""
    world = World()
    system = Recorder(required={Position, Velocity})
    world.add_system(system)

    both = world.create_entity()
    world.add_component(both, Position(1, 1))
    world.add_component(both, Velocity(1, 1))

    position_only = world.create_entity()
    world.add_component(position_only, Position(2, 2))

    assert system.matched_entities() == {both}
    assert position_only not in system.matched_entities()


def test_matched_entities_is_empty_without_a_declaration():
    world = World()
    system = Recorder()
    world.add_system(system)
    e = world.create_entity()
    world.add_component(e, Position())
    assert system.matched_entities() == set()


def test_matched_entities_is_empty_before_attachment():
    assert Recorder(required={Position}).matched_entities() == set()


def test_matched_entities_tracks_later_component_changes():
    world = World()
    system = Recorder(required={Position, Velocity})
    world.add_system(system)

    e = world.create_entity()
    world.add_component(e, Position())
    assert system.matched_entities() == set()

    world.add_component(e, Velocity())
    assert system.matched_entities() == {e}

    world.remove_component(e, Velocity)
    assert system.matched_entities() == set()


# ---------------------------------------------------------------- revision


def test_update_bumps_revision():
    """Observation caches key off `revision`, so a frame must invalidate them."""
    world = World()
    before = world.revision
    world.update(0.016)
    assert world.revision > before


def test_structural_writes_do_not_bump_revision():
    """Pins the actual contract, which is narrower than it looks.

    `revision` advances on `update()` and on explicit `bump_revision()` only --
    component add/remove does *not* touch it. Anything mutating the board
    outside the frame loop (the agent action path) must therefore bump it
    itself; see `ActionExecutor._invalidate_observation_cache`.
    """
    world = World()
    e = world.create_entity()
    r0 = world.revision
    world.add_component(e, Position())
    world.remove_component(e, Position)
    assert world.revision == r0

    world.bump_revision()
    assert world.revision == r0 + 1
