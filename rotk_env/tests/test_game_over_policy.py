"""GameOverPolicy: annihilation, mutual wipe, and mode clocks."""

from framework.ecs.world import World
from rotk_env.components import (
    GameModeComponent,
    GameState,
    GameTime,
    HexPosition,
    Unit,
    UnitCount,
)
from rotk_env.prefabs.config import Faction, GameConfig, GameMode, UnitType
from rotk_env.systems.game_over_policy import (
    REASON_ANNIHILATION,
    REASON_MUTUAL_ANNIHILATION,
    REASON_TIMEOUT,
    GameOverPolicy,
)


def _world(mode=GameMode.TURN_BASED, turn_number=1, elapsed=0.0):
    world = World()
    world.add_singleton_component(
        GameState(
            current_player=Faction.WEI,
            turn_number=turn_number,
            game_mode=mode,
            max_turns=GameConfig.MAX_TURNS,
        )
    )
    world.add_singleton_component(GameModeComponent(mode=mode))
    game_time = GameTime()
    game_time.initialize(mode)
    game_time.game_elapsed_time = elapsed
    world.add_singleton_component(game_time)
    return world


def _spawn(world, faction, col=0, row=0, count=100):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=count, max_count=100))
    return entity


def test_annihilation_sets_winner():
    world = _world()
    _spawn(world, Faction.WEI)
    shu = _spawn(world, Faction.SHU, col=1)
    world.get_component(shu, UnitCount).current_count = 0

    policy = GameOverPolicy(world)
    assert policy.apply() is True
    state = world.get_singleton_component(GameState)
    assert state.game_over is True
    assert state.winner == Faction.WEI
    assert state.end_reason == REASON_ANNIHILATION


def test_mutual_annihilation_is_draw():
    world = _world()
    wei = _spawn(world, Faction.WEI)
    shu = _spawn(world, Faction.SHU, col=1)
    world.get_component(wei, UnitCount).current_count = 0
    world.get_component(shu, UnitCount).current_count = 0

    policy = GameOverPolicy(world)
    assert policy.apply() is True
    state = world.get_singleton_component(GameState)
    assert state.winner is None
    assert state.end_reason == REASON_MUTUAL_ANNIHILATION


def test_turn_timeout_is_draw_regardless_of_survivors():
    world = _world(turn_number=GameConfig.MAX_TURNS + 1)
    _spawn(world, Faction.WEI)
    _spawn(world, Faction.SHU, col=1)

    policy = GameOverPolicy(world)
    assert policy.apply() is True
    state = world.get_singleton_component(GameState)
    assert state.winner is None
    assert state.end_reason == REASON_TIMEOUT


def test_turn_100_with_both_alive_continues():
    world = _world(turn_number=GameConfig.MAX_TURNS)
    _spawn(world, Faction.WEI)
    _spawn(world, Faction.SHU, col=1)

    policy = GameOverPolicy(world)
    assert policy.apply() is False
    assert world.get_singleton_component(GameState).game_over is False


def test_realtime_timeout_is_draw():
    world = _world(mode=GameMode.REAL_TIME, elapsed=GameConfig.MAX_REALTIME_SECONDS)
    _spawn(world, Faction.WEI)
    _spawn(world, Faction.SHU, col=1)

    policy = GameOverPolicy(world)
    assert policy.apply() is True
    state = world.get_singleton_component(GameState)
    assert state.winner is None
    assert state.end_reason == REASON_TIMEOUT


def test_realtime_before_timeout_continues():
    world = _world(
        mode=GameMode.REAL_TIME, elapsed=GameConfig.MAX_REALTIME_SECONDS - 1
    )
    _spawn(world, Faction.WEI)
    _spawn(world, Faction.SHU, col=1)

    policy = GameOverPolicy(world)
    assert policy.apply() is False


def test_annihilation_beats_timeout_on_same_tick():
    """A completed wipe is a win even if the clock has also expired."""
    world = _world(
        mode=GameMode.REAL_TIME, elapsed=GameConfig.MAX_REALTIME_SECONDS
    )
    _spawn(world, Faction.WEI)
    shu = _spawn(world, Faction.SHU, col=1)
    world.get_component(shu, UnitCount).current_count = 0

    policy = GameOverPolicy(world)
    assert policy.apply() is True
    state = world.get_singleton_component(GameState)
    assert state.winner == Faction.WEI
    assert state.end_reason == REASON_ANNIHILATION
