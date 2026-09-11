"""One-time Python scene preparation and owned JSON transfer into Rust.

This is an initialization/diagnostic codec, never a per-frame component bridge.
Non-string map keys and sets retain explicit tags. New unsupported values fail
loudly. Presentation resources are intentionally outside native authority.
"""
from collections import deque
import dataclasses
from enum import Enum
import math
import random

SCHEMA_VERSION = 1
ORACLE_VERSION = 'python-r0-78cc8da'
PRESENTATION = frozenset('Renderable AnimationState Selected Camera UIState InputState MiniMap UnitActionPanel ActionConfirmDialog UIButtonCollection UIPanel GameOverButtons DamageNumber AttackAnimation EffectAnimation ProjectileAnimation'.split())


def encode(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float) and not math.isfinite(value):
        return {'$float': value.hex()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value):
        out = {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
        # UnitState is an Enum, not str. Existing coefficient lookup distinguishes
        # it from the legacy raw string; preserve that distinction in native state.
        if type(value).__name__ == 'UnitStatus' and isinstance(value.current_status, Enum):
            out['current_status_is_enum'] = True
        return out
    if isinstance(value, dict):
        pairs = [[encode(k), encode(v)] for k, v in value.items()]
        if all(isinstance(k, str) for k, _ in pairs):
            return dict(pairs)
        import json
        return {'$map': sorted(pairs, key=lambda p: json.dumps(p[0], sort_keys=True))}
    if isinstance(value, (set, frozenset)):
        import json
        return {'$set': sorted((encode(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))}
    if isinstance(value, (tuple, list, deque)):
        return [encode(v) for v in value]
    raise TypeError(f'Unsupported native scene value: {type(value)}')


def rng_state(rng: random.Random):
    version, words, gaussian = rng.getstate()
    if version != 3:
        raise ValueError('Native RNG requires CPython state version 3')
    return {'words': list(words[:-1]), 'index': words[-1], 'gauss_next': gaussian}


def export_recovery(system):
    """Import active deadlines too: resetting at a handoff would change CD."""
    def queue(kind):
        return {'buckets': [[due, [list(entry) for entry in entries]]
                            for due, entries in sorted(getattr(system, f'_{kind}_buckets').items())],
                'active': [[uid, list(value)] for uid, value in sorted(getattr(system, f'_{kind}_due').items())],
                'versions': [[uid, v] for uid, v in sorted(getattr(system, f'_{kind}_versions').items())]}
    result = {'enabled': system.enabled, 'ap_interval': system.ap_recovery_interval,
              'ap_amount': system.ap_recovery_amount, 'mp_interval': system.mp_recovery_interval,
              'skill_interval': system.skill_cooldown_interval,
              'last': system._last_game_elapsed, 'known': system._known_entity_counter,
              'mp_pending': sorted(system._mp_pending_detection)}
    for kind in ('ap', 'mp', 'skill'):
        result[kind] = queue(kind)
        result[f'{kind}_elapsed'] = {str(k): v for k, v in getattr(system, f'{kind}_elapsed').items()}
    result['mp_last_points'] = {str(k): v for k, v in system.mp_last_points.items()}
    return result


def export_initial_state(world, *, display='none'):
    from rotk_env.components import GameTime, RngService
    from rotk_env.prefabs.config import GameConfig
    clock = world.get_singleton_component(GameTime)
    rng = world.get_singleton_component(RngService)
    if clock is None or rng is None:
        raise ValueError('Scene requires GameTime and RngService')
    entities = []
    for entity, components in sorted(world.entities.items()):
        if len({t.__name__ for t in components}) != len(components):
            raise ValueError('Ambiguous component names in scene')
        kept = {t.__name__: encode(c) for t, c in components.items() if t.__name__ not in PRESENTATION}
        # Keep empty IDs too: ID zero and presentation-created gaps are legitimate.
        entities.append({'id': entity, 'components': kept})
    singletons = {t.__name__: encode(c) for t, c in world._singleton_components.items()
                  if t.__name__ not in PRESENTATION and t is not RngService}
    from rotk_env.systems.resource_recovery_system import get_resource_recovery_system
    recovery = get_resource_recovery_system(world)
    systems = {'ResourceRecoverySystem': export_recovery(recovery)} if recovery is not None else {}
    return {'schema': SCHEMA_VERSION, 'oracle': ORACLE_VERSION, 'display': display,
            'mode': clock.current_mode.value, 'seed': str(rng.seed), 'seed_source': rng.source,
            'entity_counter': world.entity_counter, 'entities': entities, 'singletons': singletons,
            'systems': systems,
            'clock': {'elapsed': clock.game_elapsed_time, 'time_scale': clock.time_scale,
                      'paused': clock.paused, 'realtime': clock.is_real_time(), 'tick': 0},
            'rng': {name: rng_state(stream) for name, stream in rng._rngs.items()},
            'rules': {'hex_size': GameConfig.HEX_SIZE,
                      'hex_orientation': GameConfig.HEX_ORIENTATION.value,
                      'terrain_effects': encode(GameConfig.TERRAIN_EFFECTS),
                      'terrain_coefficients': encode(GameConfig.TERRAIN_COEFFICIENTS),
                      'state_coefficients': encode(GameConfig.STATE_COEFFICIENTS),
                      'unit_stats': encode(GameConfig.UNIT_STATS)}}


def prepare_scene(**kwargs):
    """Prepare and discard a temporary Python world; return only owned data.

    Only call from the application owner thread during scene setup. No Hub/BOT is
    started. Existing event subscriptions are isolated and restored, even on error.
    Rendering resources must already be initialized for dummy/window preparation.
    """
    from framework import World
    from framework.engine.events import EBS
    from rotk_env.prefabs.world_builder import build_skirmish_world
    if kwargs.get('hub_url') is not None or kwargs.get('enable_mock_ai', False):
        raise ValueError('Native scene preparation cannot start Hub or BOT')
    listeners = EBS._listeners
    EBS._listeners = {}
    world = World()
    try:
        build_skirmish_world(world=world, **kwargs)
        return export_initial_state(world, display=kwargs.get('display', 'none'))
    finally:
        world.reset()
        EBS._listeners = listeners
