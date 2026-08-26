"""Combat math: damage formula, d20 hit/crit. No hub, no pygame window."""

from framework.ecs.world import World
from rotk_env.components import (
    ActionPoints,
    Combat,
    HexPosition,
    Unit,
    UnitCount,
    UnitStatus,
)
from rotk_env.components.random_events import CombatRoll
from rotk_env.prefabs.config import Faction, GameConfig, UnitState, UnitType
from rotk_env.systems.combat_system import CombatSystem


class _SeqRng:
    def __init__(self, values):
        self._values = iter(values)

    def randint(self, a, b):
        return next(self._values)


def _world():
    world = World()
    combat = CombatSystem()
    world.add_system(combat)
    return world, combat


def _spawn(
    world,
    *,
    faction=Faction.WEI,
    col=0,
    row=0,
    unit_type=UnitType.INFANTRY,
    ap=2,
    charge=0,
):
    stats = GameConfig.UNIT_BASE_STATS[unit_type]
    entity = world.create_entity()
    world.add_component(entity, Unit(unit_type=unit_type, faction=faction, name="test"))
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=2))
    world.add_component(
        entity,
        Combat(
            base_attack=stats.base_attack,
            base_defense=stats.base_defense,
            attack_range=stats.attack_range,
        ),
    )
    world.add_component(
        entity, UnitStatus(current_status=UnitState.NORMAL, charge_stacks=charge)
    )
    return entity


def test_hit_is_d20_against_threshold_one():
    roll = CombatRoll()
    assert roll.hit_threshold == 1
    assert roll.roll_hit(_SeqRng([1])) is True
    assert roll.hit_roll == 1
    miss = CombatRoll(hit_threshold=2)
    assert miss.roll_hit(_SeqRng([1])) is False


def test_crit_is_d20_against_threshold_nineteen():
    roll = CombatRoll()
    assert roll.crit_threshold == 19
    assert roll.roll_crit(_SeqRng([18])) is False
    assert roll.roll_crit(_SeqRng([19])) is True
    assert roll.roll_crit(_SeqRng([20])) is True


def test_full_infantry_plain_damage_is_five():
    """base 10 vs 10, infantry shield +1 def, max(1, atk - int(def * 0.5))."""
    world, combat = _world()
    attacker = _spawn(world, faction=Faction.WEI, col=0, row=0)
    target = _spawn(world, faction=Faction.SHU, col=1, row=0)
    damage = combat._calculate_damage(
        attacker,
        target,
        world.get_component(attacker, UnitCount),
        world.get_component(target, UnitCount),
        world.get_component(attacker, UnitStatus),
        world.get_component(target, UnitStatus),
    )
    assert damage == 5


def test_cavalry_charge_multiplies_damage_by_one_point_five():
    world, combat = _world()
    attacker = _spawn(
        world, faction=Faction.WEI, col=0, row=0, unit_type=UnitType.CAVALRY, charge=1
    )
    target = _spawn(world, faction=Faction.SHU, col=1, row=0)
    damage = combat._calculate_damage(
        attacker,
        target,
        world.get_component(attacker, UnitCount),
        world.get_component(target, UnitCount),
        world.get_component(attacker, UnitStatus),
        world.get_component(target, UnitStatus),
    )
    assert damage == 13
    assert world.get_component(attacker, UnitStatus).charge_stacks == 0


def test_execute_attack_applies_damage_and_spends_ap():
    world, combat = _world()
    attacker = _spawn(world, faction=Faction.WEI, col=0, row=0)
    target = _spawn(world, faction=Faction.SHU, col=1, row=0)
    combat._roll_hit = lambda *args, **kwargs: True
    combat._roll_crit = lambda *args, **kwargs: False

    result = combat.execute_attack(attacker, target)
    assert result["success"] is True
    battle = result["battle_result"]
    assert battle["hit_success"] is True
    assert battle["is_critical"] is False
    assert battle["damage_dealt"] == 5
    assert battle["casualties_inflicted"] == 5
    assert world.get_component(target, UnitCount).current_count == 95
    assert world.get_component(attacker, ActionPoints).current_ap == 1


def test_crit_multiplies_damage_by_one_point_five():
    world, combat = _world()
    attacker = _spawn(world, faction=Faction.WEI, col=0, row=0)
    target = _spawn(world, faction=Faction.SHU, col=1, row=0)
    combat._roll_hit = lambda *args, **kwargs: True
    combat._roll_crit = lambda *args, **kwargs: True

    result = combat.execute_attack(attacker, target)
    battle = result["battle_result"]
    assert battle["is_critical"] is True
    assert battle["damage_dealt"] == 7
    assert world.get_component(target, UnitCount).current_count == 93


def test_miss_deals_no_damage_but_still_spends_ap():
    world, combat = _world()
    attacker = _spawn(world, faction=Faction.WEI, col=0, row=0)
    target = _spawn(world, faction=Faction.SHU, col=1, row=0)
    combat._roll_hit = lambda *args, **kwargs: False

    result = combat.execute_attack(attacker, target)
    battle = result["battle_result"]
    assert battle["hit_success"] is False
    assert battle["damage_dealt"] == 0
    assert world.get_component(target, UnitCount).current_count == 100
    assert world.get_component(attacker, ActionPoints).current_ap == 1
