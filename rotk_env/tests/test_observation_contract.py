"""Observation and combat-capability contract tests. No hub, no pygame window."""

from framework.ecs.world import World
from rotk_env.components import (
    ActionPoints,
    Combat,
    FogOfWar,
    HexPosition,
    MapData,
    Unit,
    UnitCount,
    UIState,
    Vision,
)
from rotk_env.prefabs.config import ActionType, Faction, UnitType
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.input_system import InputHandlingSystem
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.llm_observation_system import LLMObservationSystem, ObservationLevel


def _world_with_combat():
    world = World()
    combat_system = CombatSystem()
    world.add_system(combat_system)
    return world, combat_system


def _spawn_unit(world: World, *, faction=Faction.WEI, col=0, row=0, ap=2, cooldown=0.0):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=2))
    world.add_component(
        entity,
        Combat(base_attack=10, base_defense=10, attack_range=1, attack_cooldown=cooldown),
    )
    return entity


def test_combat_component_can_attack_respects_cooldown():
    ready = Combat(base_attack=10, base_defense=8)
    locked = Combat(base_attack=10, base_defense=8, attack_cooldown=0.4)
    assert ready.can_attack() is True
    assert locked.can_attack() is False


def test_combat_in_attack_range():
    combat = Combat(base_attack=10, base_defense=8, attack_range=3)
    assert combat.in_attack_range(0) is False
    assert combat.in_attack_range(1) is True
    assert combat.in_attack_range(3) is True
    assert combat.in_attack_range(4) is False


def test_combat_system_can_attack_requires_ap_and_alive():
    world, combat_system = _world_with_combat()
    ready = _spawn_unit(world, ap=1)
    tired = _spawn_unit(world, col=1, ap=0)
    dead = _spawn_unit(world, col=2, ap=1)
    world.get_component(dead, UnitCount).current_count = 0

    assert combat_system.can_attack(ready) is True
    assert combat_system.can_attack(tired) is False
    assert combat_system.can_attack(dead) is False


def test_combat_system_can_attack_target_rejects_friendly_and_range():
    world, combat_system = _world_with_combat()
    attacker = _spawn_unit(world, faction=Faction.WEI, col=0, row=0)
    friend = _spawn_unit(world, faction=Faction.WEI, col=1, row=0)
    far_enemy = _spawn_unit(world, faction=Faction.SHU, col=5, row=5)
    near_enemy = _spawn_unit(world, faction=Faction.SHU, col=1, row=0)

    assert combat_system.can_attack(attacker, friend) is False
    assert combat_system.can_attack(attacker, far_enemy) is False
    assert combat_system.can_attack(attacker, near_enemy) is True


def test_faction_resources_are_zero_placeholders():
    world, _ = _world_with_combat()
    obs = LLMObservationSystem(world)
    resources = obs._get_faction_resources(Faction.WEI)
    assert resources == {"manpower": 0, "supplies": 0, "morale": 0}


def test_limited_observation_reads_explored_tiles_when_fog_enabled():
    world, _ = _world_with_combat()
    fog = FogOfWar(enabled=True)
    fog.explored_tiles[Faction.WEI] = {(0, 0), (1, 0)}
    fog.faction_vision[Faction.WEI] = {(0, 0)}
    world.add_singleton_component(fog)

    obs = LLMObservationSystem(world)
    result = obs._get_limited_observation(Faction.WEI)
    assert result["fog_of_war_status"] == "active"
    assert {"col": 0, "row": 0} in result["explored_areas"]
    assert {"col": 1, "row": 0} in result["explored_areas"]
    assert result["current_visible_areas"] == [{"col": 0, "row": 0}]


def test_limited_observation_empty_vision_does_not_fallback():
    """An empty faction_vision set is real FoW, not 'VisionSystem not ticked'."""
    world, _ = _world_with_combat()
    unit = _spawn_unit(world, col=5, row=5)
    world.add_component(unit, Vision(range=2))

    fog = FogOfWar(enabled=True)
    fog.explored_tiles[Faction.WEI] = {(0, 0)}
    fog.faction_vision[Faction.WEI] = set()
    world.add_singleton_component(fog)

    obs = LLMObservationSystem(world)
    result = obs._get_limited_observation(Faction.WEI)
    assert result["fog_of_war_status"] == "active"
    assert result["explored_areas"] == [{"col": 0, "row": 0}]
    assert result["current_visible_areas"] == []


def test_limited_observation_exposes_whole_map_when_fog_disabled():
    world, _ = _world_with_combat()
    world.add_singleton_component(
        MapData(width=2, height=1, tiles={(0, 0): 1, (1, 0): 2})
    )
    world.add_singleton_component(FogOfWar(enabled=False))

    obs = LLMObservationSystem(world)
    result = obs._get_limited_observation(Faction.WEI)
    assert result["fog_of_war_status"] == "disabled"
    assert len(result["explored_areas"]) == 2
    assert result["explored_areas"] == result["current_visible_areas"]


def test_reserved_actions_are_registered_placeholders():
    world, _ = _world_with_combat()
    handler = LLMActionHandler(world)
    for action in ("defend", "scout", "retreat"):
        result = handler.execute_action(action, {})
        assert result["implemented"] is False
        assert result["error_code"] == "NOT_IMPLEMENTED"
        assert action in handler.action_handlers


def test_unit_observation_can_attack_false_without_ap():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world, ap=0)
    obs = LLMObservationSystem(world)
    data = obs._get_unit_observation(unit_id)
    assert data["unit"]["combat"]["can_attack"] is False
    assert "attack" not in data["action_options"]


def test_action_points_attack_cost():
    ap = ActionPoints(current_ap=1, max_ap=2)
    assert ap.can_perform_action(ActionType.ATTACK) is True
    ap.current_ap = 0
    assert ap.can_perform_action(ActionType.ATTACK) is False


def test_execute_attack_rejects_cooldown():
    world, combat_system = _world_with_combat()
    attacker = _spawn_unit(world, ap=1, cooldown=0.5)
    target = _spawn_unit(world, faction=Faction.SHU, col=1, row=0)
    result = combat_system.execute_attack(attacker, target)
    assert result["success"] is False
    assert result["error"] == "attack_on_cooldown"
    assert combat_system.can_attack(attacker, target) is False


def test_execute_attack_rejects_insufficient_ap():
    world, combat_system = _world_with_combat()
    attacker = _spawn_unit(world, ap=0)
    target = _spawn_unit(world, faction=Faction.SHU, col=1, row=0)
    result = combat_system.execute_attack(attacker, target)
    assert result["success"] is False
    assert result["error"] == "insufficient_action_points"


def test_key_1_toggles_god_view():
    import pygame

    world = World()
    ui_state = UIState()
    world.add_singleton_component(ui_state)
    system = InputHandlingSystem()
    system.world = world

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_1})
    system._handle_key_down(event)
    assert ui_state.god_mode is True
    system._handle_key_down(event)
    assert ui_state.god_mode is False
    system._handle_key_down(event)
    assert ui_state.god_mode is True
