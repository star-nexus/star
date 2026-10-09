"""Real-kernel request/state/VLM compatibility through the production owner."""
from copy import deepcopy
from threading import get_ident

import pytest

pytest.importorskip('star_native')
from framework.engine.frame_capture import capture_rendered_frame
from rotk_env.runtime.authority import AuthorityRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.tests.test_native_vlm import make, screen, REG, VLM
from rotk_env.tests.test_native_request_batch import frozen


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('batch', [False, True])
def test_real_owner_keeps_wire_state_batch_order_and_ui_capture(threads, batch, screen, frozen):
    world, (a, b, _), _ = make('window')
    initial = export_initial_state(world, display='window')
    requests = [ActionRequest('a', 'register_agent_info', REG),
        ActionRequest('a', 'claim_units', {'unit_ids': [a, b]}),
        ActionRequest('a', 'move', {'unit_id': a, 'target_position': {'col': -2, 'row': 0}}),
        ActionRequest('a', VLM, {'faction': 'wei'}),
        ActionRequest('a', 'get_faction_state', {'faction': 'wei'}),
        ActionRequest('a', VLM, {'faction': 'wei', 'unit_ids': []}),
        ActionRequest('a', 'get_faction_state', {'faction': 'wei'})]
    left = RustRuntime(initial, threads=threads)
    packets = []; capture_threads = []
    def capture():
        capture_threads.append(get_ident())
        return capture_rendered_frame()
    right = AuthorityRuntime(RustRuntime(initial, threads=threads),
        on_publication=lambda delta: packets.append(deepcopy(delta)), capture_frame=capture)
    try:
        if batch:
            assert right.execute_actions(deepcopy(requests)) == left.execute_actions(requests)
        else:
            for request in requests:
                args = (request.action, deepcopy(request.parameters))
                kwargs = dict(agent_id=request.agent_id)
                assert right.execute_action(*args, **kwargs) == left.execute_action(*args, **kwargs)
        assert capture_threads == [get_ident(), get_ident()]
        assert len(packets) == 2
        assert right.export_state() == left.export_state()
        left.take_presentation_delta()  # Match the capture fences' extraction.
        for dt in [0, .25, 1/30]:
            left.step(dt, wall_time=frozen[0]); right.step(dt, wall_time=frozen[0])
            assert left.export_state() == right.export_state()
            assert left.take_presentation_delta() == right.take_presentation_delta()
        with pytest.raises(Exception):
            right.reset({})
        assert right.export_state() == left.export_state()
        right.reset(initial); left.reset(initial)
        assert right.export_state() == left.export_state()
    finally:
        right.close(); left.close(); world.reset()
    assert right.scheduling_metrics()['closed']


def test_default_cli_threaded_and_explicit_serial_fallback(monkeypatch):
    from rotk_env.main import parse_arguments, game_scene_kwargs_from_args
    monkeypatch.setattr('sys.argv', ['star'])
    assert parse_arguments().native_scheduling == 'threaded'
    monkeypatch.setattr('sys.argv', ['star', '--backend', 'rust', '--no-hub', '--native-scheduling', 'serial'])
    assert game_scene_kwargs_from_args(parse_arguments())['native_scheduling'] == 'serial'
