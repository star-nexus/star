from dataclasses import dataclass

from framework import World, Component


@dataclass
class Label(Component):
    value: int = 0


@dataclass
class Position(Component):
    x: int = 0


def test_reference_version_tracks_replacements_not_unrelated_or_in_place_writes():
    w=World(); e=w.create_entity()
    v=w.component_reference_version(Label)
    w.add_component(e,Label())
    assert w.component_reference_version(Label)!=v
    v=w.component_reference_version(Label)
    w.get_component(e,Label).value=42
    w.add_component(e,Position())
    assert w.component_reference_version(Label)==v
    w.add_component(e,Label(7))
    assert w.component_reference_version(Label)!=v
    v=w.component_reference_version(Label)
    w.remove_component(e,Label)
    assert w.component_reference_version(Label)!=v
    w.add_component(e,Label())
    v=w.component_reference_version(Label)
    w.destroy_entity(e)
    assert w.component_reference_version(Label)!=v


def test_explicit_cache_resets_invalidate_reference_tokens():
    w=World()
    v=w.component_reference_version(Label)
    w.clear_cache()
    assert w.component_reference_version(Label)!=v
    v=w.component_reference_version(Label)
    w._invalidate_cache()
    assert w.component_reference_version(Label)!=v
