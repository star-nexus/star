"""One-shot authoritative report projection and offline post-game host lifecycle.

No Python simulation is mounted. Full histories cross the boundary only when the
report is generated; the per-frame HUD World is never used as a report source.
"""
from copy import deepcopy
from dataclasses import fields
from framework import World
from rotk_env import components as c
from rotk_env.components.agent_info import AgentInfo, AgentInfoRegistry
from rotk_env.components.settlement_report import SettlementReport
from rotk_env.prefabs.config import Faction, TerrainType, UnitType
from rotk_env.systems.settlement_report_system import SettlementReportSystem
from .world_presentation import _component


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {'$set'}:
            return {_key(_decode(v)) for v in value['$set']}
        if set(value) == {'$map'}:
            return {_key(_decode(k)): _decode(v) for k, v in value['$map']}
        if set(value) == {'$float'}:
            return float.fromhex(value['$float'])
        return {k: _decode(v) for k, v in value.items()}
    return value


def _key(value):
    return tuple(_key(v) for v in value) if isinstance(value, list) else value


def _construct(cls, data):
    names = {f.name for f in fields(cls)}
    component = cls(**{k: v for k, v in data.items() if k in names})
    for name, value in data.items():
        if name not in names:
            setattr(component, name, value)
    return component


def report_world(snapshot):
    """Decode the explicit report component boundary into an owned read view."""
    singletons = _decode(deepcopy(snapshot['singletons']))
    world = World()
    try:
        for cls in (c.GameState, c.GameTime):
            if cls.__name__ in singletons:
                world.add_singleton_component(_component(cls, singletons[cls.__name__]))
        if 'GameStats' in singletons:
            data = singletons['GameStats']
            for key in ('faction_stats', 'initial_unit_counts', 'action_counts_by_faction',
                        'interaction_counts_by_faction', 'strategy_scores_by_faction',
                        'strategy_ping_count_by_faction', 'strategy_evidence', 'last_strategy_ping_ts', 'llm_api_stats'):
                data[key] = {Faction(k): v for k, v in data[key].items()}
            data['agent_id_to_faction'] = {k: Faction(v) for k, v in data['agent_id_to_faction'].items()}
            for key in ('registered_factions', 'received_llm_stats_factions'):
                data[key] = {Faction(v) for v in data[key]}
            world.add_singleton_component(_construct(c.GameStats, data))
        if 'MapData' in singletons:
            data = singletons['MapData']
            data['formations'] = {Faction(k): [tuple(cell) for cell in v] for k, v in data['formations'].items()}
            data['formation_unit_types'] = {Faction(k): [UnitType(t) for t in v] for k, v in data['formation_unit_types'].items()}
            data['home_bases'] = {Faction(k): tuple(v) for k, v in data['home_bases'].items()}
            world.add_singleton_component(_construct(c.MapData, data))
        if 'AgentInfoRegistry' in singletons:
            data = singletons['AgentInfoRegistry']
            data['agents'] = {k: [_construct(AgentInfo, item) for item in v] for k, v in data['agents'].items()}
            world.add_singleton_component(_construct(AgentInfoRegistry, data))
        for row in snapshot['entities']:
            for name in ('Unit', 'UnitCount', 'HexPosition', 'Terrain', 'TerritoryControl'):
                if name not in row['components']:
                    continue
                data = _decode(row['components'][name])
                cls = getattr(c, name)
                if cls is c.Terrain:
                    data['terrain_type'] = TerrainType(data['terrain_type'])
                    component = _construct(cls, data)
                else:
                    component = _component(cls, data)
                world.ensure_entity(row['id'])
                world.add_component(row['id'], component)
        return world
    except BaseException:
        world.reset()
        raise


class NativeSettlementFormatter(SettlementReportSystem):
    """Reuse the user-visible report schema/persistence, with explicit setup facts."""
    def __init__(self, context):
        super().__init__()
        self.context = deepcopy(context)

    def _get_map_type(self):
        return self.context['map_type']

    def _detect_game_mode(self):
        return self.context['game_mode']

    def _collect_map_statistics(self):
        result = super()._collect_map_statistics()
        if self.world.get_singleton_component(c.MapData) is not None:
            result['symmetry_type'] = self.context['symmetry_type']
        return result


class OfflineSettlementHost:
    """Offline equivalent of LLMSystem(100) + SettlementReportSystem(200).

    Called after the native simulation step. Network delivery/ACK/retry and BOT
    remain a separate host integration; this host has no connected Agents.
    """
    def __init__(self, session):
        self.session = session
        self.notified = False
        self.game_end_time = None
        self.report_generated = False
        self.timeout_seconds = 60.0  # Existing Python policy, even when ready.

    def update(self, wall_time):
        self.session._check_open()
        state = self.session.world.get_singleton_component(c.GameState)
        if state is None or not state.game_over:
            return
        if not self.notified:
            self.session.runtime.prepare_game_end([], wall_time=wall_time, expected_epoch=self.session.controls.epoch)
            self.notified = True
        if self.report_generated:
            return
        if self.game_end_time is None:
            self.game_end_time = wall_time
            return
        if wall_time - self.game_end_time < self.timeout_seconds:
            return
        snapshot = self.session.runtime.export_state(expected_epoch=self.session.controls.epoch)
        view = report_world(snapshot)
        try:
            formatter = NativeSettlementFormatter(snapshot['interface']['report_context'])
            formatter.initialize(view)
            formatter._generate_settlement_report()
            report = view.get_singleton_component(SettlementReport)
            if report is not None:
                self.session.world.add_singleton_component(report)
            # Preserve existing report failure/timeout behavior: the formatter
            # catches errors; GameScene eventually exits via its timeout path.
            self.report_generated = True
        finally:
            view.reset()
