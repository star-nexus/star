"""Observation and combat-capability contract tests. No hub, no pygame window."""

from framework.ecs.world import World
from rotk_env.components import (
    ActionPoints,
    Combat,
    ConstructionPoints,
    FogOfWar,
    HexPosition,
    MapData,
    TerritoryControl,
    Unit,
    UnitCount,
    UnitSkills,
    UnitStatus,
    UIState,
    Vision,
)
from rotk_env.components.gamemode import MatchRules
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


def _spawn_unit(world: World, *, faction=Faction.WEI, col=0, row=0, ap=2):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=2))
    world.add_component(
        entity,
        Combat(base_attack=10, base_defense=10, attack_range=1),
    )
    return entity


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


def test_reserved_actions_are_not_executable():
    world, _ = _world_with_combat()
    handler = LLMActionHandler(world)
    for action in ("defend", "scout", "retreat"):
        assert action not in handler.action_handlers
        result = handler.execute_action(action, {})
        assert result.get("success") is False
        assert result.get("error_code") == 2010
        assert "supported_actions" not in result


def test_handler_named_observation_reuses_shared_cache():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world)
    world.add_singleton_component(MatchRules(game_actions=("unit_observation",)))
    obs = LLMObservationSystem(world)
    handler = LLMActionHandler(world, observation_system=obs)
    first = handler.execute_action("unit_observation", {"unit_id": unit_id})
    second = handler.execute_action("unit_observation", {"unit_id": unit_id})
    assert handler.observation_system is obs
    assert first.get("success") is True
    assert first.get("from_cache") is not True
    assert second.get("from_cache") is True


def test_faction_observation_territory_reads_tile_control():
    world = World()
    wei_capturer = _spawn_unit(world, faction=Faction.WEI, col=5, row=5)

    def _tile(
        col,
        row,
        *,
        faction=None,
        fortified=False,
        being_captured=False,
        is_city=False,
        capturing_unit=None,
    ):
        entity = world.create_entity()
        world.add_component(entity, HexPosition(col, row))
        world.add_component(
            entity,
            TerritoryControl(
                controlling_faction=faction,
                fortified=fortified,
                being_captured=being_captured,
                is_city=is_city,
                capturing_unit=capturing_unit,
            ),
        )

    _tile(0, 0, faction=Faction.WEI, is_city=True)
    _tile(1, 0, faction=Faction.WEI, fortified=True)
    _tile(2, 0, faction=Faction.SHU)
    _tile(3, 0, faction=Faction.WEI, being_captured=True)
    _tile(
        4,
        0,
        faction=Faction.SHU,
        being_captured=True,
        capturing_unit=wei_capturer,
    )

    obs = LLMObservationSystem(world)
    wei = obs._get_territory_control(Faction.WEI)
    assert wei["controlled_tiles"] == 3
    assert wei["fortified_tiles"] == 1
    assert wei["contested_tiles"] == 2
    assert wei["strategic_points"] == [{"col": 0, "row": 0, "kind": "city"}]
    shu = obs._get_territory_control(Faction.SHU)
    assert shu["controlled_tiles"] == 2
    assert shu["contested_tiles"] == 1


def test_unit_observation_can_attack_false_without_ap():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world, ap=0)
    obs = LLMObservationSystem(world)
    data = obs._get_unit_observation(unit_id)
    assert data["unit"]["combat"]["can_attack"] is False
    assert "attack" not in data["action_options"]
    for fake in ("defend", "scout", "retreat", "fortify"):
        assert fake not in data["action_options"]


def test_unit_action_options_follow_the_match_subset():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world, ap=1)
    obs = LLMObservationSystem(world)
    default = obs._get_unit_action_options(unit_id)
    assert "fortify" not in default
    assert "defend" not in default

    world.add_singleton_component(
        MatchRules(game_actions=("move", "attack", "fortify", "rest"))
    )
    still_blocked = obs._get_unit_action_options(unit_id)
    assert "fortify" not in still_blocked
    assert "rest" not in still_blocked

    world.add_component(unit_id, UnitStatus())
    world.add_component(unit_id, ConstructionPoints(current_cp=1, max_cp=1))
    tile = world.create_entity()
    world.add_component(tile, HexPosition(0, 0))
    world.add_component(
        tile, TerritoryControl(controlling_faction=Faction.WEI, fortified=False)
    )
    ready = obs._get_unit_action_options(unit_id)
    assert "fortify" in ready
    assert "rest" in ready
    assert "defend" not in ready


def test_action_points_attack_cost():
    ap = ActionPoints(current_ap=1, max_ap=2)
    assert ap.can_perform_action(ActionType.ATTACK) is True
    ap.current_ap = 0
    assert ap.can_perform_action(ActionType.ATTACK) is False


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
    fog = FogOfWar(enabled=True)
    world.add_singleton_component(ui_state)
    world.add_singleton_component(fog)
    system = InputHandlingSystem()
    system.world = world

    event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_1})
    system._handle_key_down(event)
    assert ui_state.god_mode is True
    assert fog.enabled is False
    system._handle_key_down(event)
    assert ui_state.god_mode is False
    assert fog.enabled is True
    system._handle_key_down(event)
    assert ui_state.god_mode is True
    assert fog.enabled is False


def test_observation_cache_hits_same_revision():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world)
    obs = LLMObservationSystem(world)
    first = obs.get_observation(ObservationLevel.UNIT, unit_id=unit_id)
    second = obs.get_observation(ObservationLevel.UNIT, unit_id=unit_id)
    assert first.get("success") is True
    assert first.get("from_cache") is not True
    assert second.get("from_cache") is True


def test_observation_cache_misses_after_world_changes():
    world, _ = _world_with_combat()
    unit_id = _spawn_unit(world)
    obs = LLMObservationSystem(world)
    obs.get_observation(ObservationLevel.UNIT, unit_id=unit_id)
    world.get_component(unit_id, HexPosition).col = 3
    world.bump_revision()
    again = obs.get_observation(ObservationLevel.UNIT, unit_id=unit_id)
    assert again.get("from_cache") is not True
    assert again["data"]["unit"]["position"]["col"] == 3


def test_world_update_bumps_revision():
    world = World()
    assert world.revision == 0
    world.update(1.0 / 60)
    assert world.revision == 1
