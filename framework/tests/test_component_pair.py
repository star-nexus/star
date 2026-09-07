from dataclasses import dataclass
from framework import World, Component


@dataclass
class First(Component):
    value: int=0


@dataclass
class Second(Component):
    value: int=0


def test_pair_matches_two_reads_across_missing_replacement_and_destroy():
    w=World(); e=w.create_entity()
    def check():
        actual=w.get_component_pair(e,First,Second)
        assert actual[0] is w.get_component(e,First)
        assert actual[1] is w.get_component(e,Second)
    check()
    w.add_component(e,First()); check()
    w.add_component(e,Second()); check()
    old=w.get_component(e,First)
    w.add_component(e,First(2)); check()
    assert w.get_component_pair(e,First,First)==(w.get_component(e,First),)*2
    assert w.get_component(e,First) is not old
    w.remove_component(e,Second); check()
    w.destroy_entity(e); check()
