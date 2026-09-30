"""Statistics row computation preserves ordered commits and partial failures."""
import json

import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.statistics_system import StatisticsSystem
from rotk_env.systems.window_statistics_system import StatisticsSystem as WindowStatistics
from rotk_env.tests.test_native_vision import make_vision_world


def initial_statistics(display):
    world, ids, _ = make_vision_world(display)
    try:
        system = WindowStatistics(batch_size=128) if display == 'window' else StatisticsSystem()
        world.add_system(system)
        initial = export_initial_state(world, display=display)
        initial['systems']['StatisticsSystem']['history_limit'] = 2
        return initial, ids
    finally:
        world.reset()


@pytest.mark.parametrize('display', ['none', 'window'])
@pytest.mark.parametrize('bad_index', [0, 1, 2])
@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('force_compute', [False, True])
def test_first_error_keeps_successful_prefix_and_original_trim_boundary(display, bad_index, threads, force_compute):
    initial, ids = initial_statistics(display)
    units = {e['id']: e['components'] for e in initial['entities']}
    units[ids[bad_index]]['UnitCount']['max_count'] = 0
    old_rows = 10 if display == 'window' else 10000
    initial['singletons']['GameStats']['unit_observation_history'] = [{'prior': i} for i in range(old_rows)]
    n = NativeRuntime(json.dumps(initial), threads)
    def step():
        if force_compute:
            n._statistics_step_json(.25, 1720000000., 0, False)
        else:
            n.step(.25, 1720000000.)
    try:
        with pytest.raises(RuntimeError, match='statistics health division by zero'):
            step()
        after = json.loads(n.export_state_json())
        actual = {e['id']: e['components'] for e in after['entities']}
        assert ['UnitObservation' in actual[i] for i in ids] == [i < bad_index for i in range(3)]
        history = after['singletons']['GameStats']['unit_observation_history']
        assert [row['entity'] for row in history if 'entity' in row] == list(ids[:bad_index])
        if display == 'window':
            assert len(history) == old_rows + bad_index  # final window trim must not run after error
            assert after['systems']['StatisticsSystem']['cycle'] is None
            assert after['systems']['StatisticsSystem']['last_update_time'] == 1720000000.
        else:
            assert len(history) == (old_rows if bad_index == 0 else 4999 + bad_index)
            assert after['systems']['StatisticsSystem']['last_update_time'] == 0.
        assert after['singletons']['GameStats']['total_game_time'] == .25
        assert after['clock']['tick'] == 1
        assert after['systems']['VisionSystem'] == initial['systems']['VisionSystem']
        # Failed reset keeps this precise partially committed world and its pool.
        with pytest.raises(RuntimeError):
            n.reset('{}')
        assert json.loads(n.export_state_json()) == after
        n.reset(json.dumps(initial))
        with pytest.raises(RuntimeError, match='statistics health division by zero'):
            step()
        assert json.loads(n.export_state_json()) == after
    finally:
        n.close()


@pytest.mark.parametrize('threads', [1, 2, 4])
def test_imported_duplicate_missing_rows_and_no_movement_component(threads):
    initial, (a, b, c) = initial_statistics('window')
    units = {e['id']: e['components'] for e in initial['entities']}
    del units[b]['MovementPoints']
    del units[c]['UnitCount']
    stats = initial['systems']['StatisticsSystem']
    stats['history_limit'] = 100
    stats['cycle'] = dict(phase='observations', index=0, observation_entities=[a, a, b, c, 99999],
                         visibility_entities=[a, b, c], faction_counts={}, visibility_cleared=False,
                         fog_disabled_visible_to=None)
    n = NativeRuntime(json.dumps(initial), threads)
    try:
        timing = json.loads(n._statistics_step_json(0., 1720000000., 0))
        after = json.loads(n.export_state_json())
        actual = {e['id']: e['components'] for e in after['entities']}
        history = after['singletons']['GameStats']['unit_observation_history']
        assert [row['entity'] for row in history] == [a, a, b]
        assert actual[a]['UnitObservation']['total_distance_moved'] == 1
        assert actual[a]['UnitObservation']['previous_position'] == actual[a]['UnitObservation']['current_position']
        assert len(actual[a]['UnitObservation']['movement_path']) == 1
        assert actual[b]['UnitObservation']['movement_remaining'] == 0
        assert 'UnitObservation' not in actual[c]
        assert timing['statistics']['observation_rows'] == 3
        assert timing['statistics']['parallel_batches'] == (threads > 1)
        assert timing['statistics']['jobs'] == (0 if threads == 1 else min(threads, 3))
        assert 0 <= timing['statistics']['worker_threads'] <= threads
        assert after['systems']['StatisticsSystem']['cycle']['phase'] == 'visibility'
    finally:
        n.close()
    with pytest.raises(RuntimeError, match='closed'):
        n._step_profile_json(0., 1720000000.)
