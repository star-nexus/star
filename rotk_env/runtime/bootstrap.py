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

SCHEMA_VERSION = 5
NATIVE_API_VERSION = 17
ORACLE_VERSION = 'python-r0c-3cc4ffe'
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
        # Preserve public extension fields attached after construction as well
        # as the declared fields (which already include Agent registration).
        # Private derived map/query caches are deliberately not transferred.
        out.update({name: encode(item) for name, item in vars(value).items()
                    if name not in out and not name.startswith('_')})
        # UnitState is an Enum, not str. Existing coefficient lookup distinguishes
        # it from the legacy raw string; preserve that distinction in native state.
        if type(value).__name__ == 'UnitStatus' and isinstance(value.current_status, Enum):
            out['current_status_is_enum'] = True
        if type(value).__name__ == 'TeamCoordination':
            out['inbox_maxlen'] = {k: q.maxlen for k, q in value.team_inboxes.items()}
            out['history_maxlen'] = {k: q.maxlen for k, q in value.team_history.items()}
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


def export_vision(system):
    from rotk_env.utils.unit_spatial_index import get_unit_spatial_index
    return {'enabled': system.enabled, 'window': type(system).__module__.endswith('window_vision_system'),
            'indexed': get_unit_spatial_index(system.world) is not None,
            'audit_interval': system._AUDIT_EVERY_FRAMES, 'frames': system._frames,
            'bootstrapped': system._bootstrapped, 'last_fog_enabled': system._last_fog_enabled,
            'terrain_revision': system._terrain_revision, 'capacity': system._geometry_cache_max_entries,
            'dirty': sorted(system._dirty),
            'unit_visibility': {str(uid): encode(cells) for uid, cells in system._unit_visibility.items()},
            'unit_faction': {str(uid): f.value for uid, f in system._unit_faction.items()},
            'counts': {f.value: [[list(cell), n] for cell, n in sorted(counts.items())]
                       for f, counts in system._faction_tile_counts.items()},
            'geometry': [[encode(key), encode(cells)] for key, cells in system._geometry_cache.items()],
            'recomputes': system._stat_recomputes, 'cache_hits': system._stat_cache_hits,
            'geometry_hits': system._stat_geometry_hits, 'geometry_misses': system._stat_geometry_misses,
            'geometry_evictions': system._stat_geometry_evictions}


def export_initial_state(world, *, display='none'):
    from rotk_env.components import GameTime, RngService, GameStats, MapData, map_briefing
    from rotk_env.prefabs.action_catalog import GAME_ACTIONS, docs_for_names
    from protocol.error_codes import DESCRIPTIONS
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
    vision = next((s for s in world.systems if type(s).__name__ == 'VisionSystem'), None)
    if vision is not None:
        systems['VisionSystem'] = export_vision(vision)
    statistics = next((s for s in world.systems if type(s).__name__ == 'StatisticsSystem'), None)
    if statistics is not None:
        from rotk_env.utils.unit_spatial_index import get_unit_spatial_index
        window = type(statistics).__module__.endswith('window_statistics_system')
        systems['StatisticsSystem'] = {
            'enabled': statistics.enabled, 'window': window,
            'indexed': get_unit_spatial_index(world) is not None,
            'last_update_time': statistics.last_update_time,
            'observation_interval': statistics.observation_interval,
            'batch_size': getattr(statistics, 'batch_size', 128),
            'history_limit': getattr(statistics, 'OBSERVATION_HISTORY_LIMIT', 10000),
            'visibility_limit': getattr(statistics, 'VISIBILITY_HISTORY_LIMIT', 100),
            'cycle': encode(getattr(statistics, '_cycle', None)),
        }
    for system in world.systems:
        name = type(system).__name__
        if name in ('GameTimeSystem', 'AnimationSystem', 'RealtimeSystem', 'TurnSystem', 'TerritorySystem'):
            systems[name] = {'enabled': system.enabled}
            if name == 'RealtimeSystem':
                from rotk_env.utils.unit_spatial_index import get_unit_spatial_index
                systems[name]['indexed'] = ('window_' in type(system).__module__
                                             and get_unit_spatial_index(world) is not None)
            if name == 'TurnSystem':
                systems[name].update(turn_timer=system.turn_timer, auto_turn_duration=system.auto_turn_duration)
    llm = next((s for s in world.systems if type(s).__name__ == 'LLMSystem'), None)
    observer = getattr(getattr(llm, 'action_handler', None), 'observation_system', None)
    systems['LLMObservationSystem'] = {'cache': {
        key: encode(result) for key, (revision, result) in (observer.cache.items() if observer else ())
        if revision == world.revision}}
    from .presentation_state import export_visual_lifecycle
    systems['VisualLifecycle'] = export_visual_lifecycle(world)
    from rotk_env.systems.settlement_report_system import SettlementReportSystem
    report = SettlementReportSystem()
    report.world = world
    map_system = next((s for s in world.systems if type(s).__name__ == 'MapSystem'), None)
    interface = {
        'report_context': {'map_type': report._get_map_type(), 'game_mode': report._detect_game_mode(),
                           'symmetry_type': getattr(map_system, 'symmetry_type', 'unknown')},
        'action_specs': docs_for_names(spec.name for spec in GAME_ACTIONS),
        'system_errors': {str(int(code)): text for code, text in DESCRIPTIONS.items()},
        'game_stats_defaults': encode(GameStats()),
        'map_briefing': map_briefing(world.get_singleton_component(MapData)),
        'movement_system': any(type(s).__name__ == 'MovementSystem' for s in world.systems),
        'combat_system': any(type(s).__name__ == 'CombatSystem' for s in world.systems),
    }
    return {'schema': SCHEMA_VERSION, 'oracle': ORACLE_VERSION, 'display': display,
            'interface': interface,
            'mode': clock.current_mode.value, 'seed': str(rng.seed), 'seed_source': rng.source,
            'entity_counter': world.entity_counter, 'entities': entities, 'singletons': singletons,
            'systems': systems,
            'clock': {'elapsed': clock.game_elapsed_time, 'time_scale': clock.time_scale,
                      'paused': clock.paused, 'realtime': clock.is_real_time(), 'tick': 0},
            'rng': {name: rng_state(stream) for name, stream in rng._rngs.items()},
            'rules': {'max_turns': GameConfig.MAX_TURNS,
                      'max_realtime_seconds': GameConfig.MAX_REALTIME_SECONDS,
                      'hex_size': GameConfig.HEX_SIZE,
                      'hex_orientation': GameConfig.HEX_ORIENTATION.value,
                      'terrain_effects': encode(GameConfig.TERRAIN_EFFECTS),
                      'terrain_coefficients': encode(GameConfig.TERRAIN_COEFFICIENTS),
                      'state_coefficients': encode(GameConfig.STATE_COEFFICIENTS),
                      'unit_stats': encode(GameConfig.UNIT_STATS)}}


def prepare_display_world(**kwargs):
    """Prepare native initial data and retain the independent display components.

    Only call from the application owner thread during scene setup. No Hub/BOT is
    started. Existing event subscriptions are isolated and restored, even on error.
    Returned World has no systems or surviving simulation subscriptions. Its
    components are Python-owned presentation data after the JSON handoff.
    Rendering resources must already be initialized for window preparation.
    """
    from framework import World
    from framework.engine.events import EBS
    from rotk_env.prefabs.world_builder import build_skirmish_world
    if kwargs.get('hub_url') is not None or kwargs.get('enable_mock_ai', False):
        raise ValueError('Native scene preparation cannot start Hub or BOT')
    if kwargs.get('display', 'none') not in ('none', 'dummy', 'window'):
        raise ValueError('Invalid native display configuration')
    listeners = EBS._listeners
    EBS._listeners = {}
    world = World()
    try:
        build_skirmish_world(world=world, **kwargs)
        initial = export_initial_state(world, display=kwargs.get('display', 'none'))
        # Retire every prepared system, including input/network lifecycle hooks,
        # while its listeners still belong to the isolated preparation bus.
        systems, world.systems = world.systems, []
        failures = []
        for system in systems:
            cleanup = getattr(system, 'cleanup', None)
            if cleanup is not None:
                try:
                    cleanup()
                except Exception as exc:
                    failures.append(exc)
        if failures:
            raise ExceptionGroup('Native preparation cleanup failed', failures)
        return world, initial
    except BaseException:
        world.reset()
        raise
    finally:
        EBS._listeners = listeners


def prepare_scene(**kwargs):
    """Prepare and discard display components; return only owned initial data."""
    world, initial = prepare_display_world(**kwargs)
    world.reset()
    return initial
