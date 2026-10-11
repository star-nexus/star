import pytest
pytest.importorskip('star_native')

from rotk_env.rendering.commands import CommandGateway, ViewGrant
from rotk_env.runtime.session import NativeSession
from rotk_env.prefabs.config import Faction, PlayerType
from rotk_env.tests.test_native_request_batch import frozen


@pytest.fixture
def scene(frozen):
    with NativeSession(renderer='web', scenario='chibi-small', seed=42,
                       players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.HUMAN}) as s:
        yield s


def request(scene, command, **parameters):
    return dict(epoch=str(scene.controls.epoch), command=command, parameters=parameters)


def test_web_button_uses_human_resource_reset_and_keeps_agent_accounting_untouched(scene):
    gate = CommandGateway(scene); uid = scene.renderer.model.snapshot('wei')['units'][0]['id']
    grant = ViewGrant('wei', True)
    for _ in range(2): assert gate.dispatch(grant, request(scene, 'wait', unit_id=uid)) is True
    assert scene.renderer.model.snapshot('wei')['units'][0]['ap'] == 0
    before = scene.runtime.export_state()
    assert gate.dispatch(grant, request(scene, 'end_turn')) is True
    assert scene.renderer.model.snapshot('wei')['units'][0]['ap'] == 2
    assert scene.runtime.host_status()['current_player'] == 'shu'
    after = scene.runtime.export_state()
    assert before['singletons']['AgentInfoRegistry'] == after['singletons']['AgentInfoRegistry']
    assert scene.failure is None
    with pytest.raises(PermissionError, match='turn'):
        gate.dispatch(grant, request(scene, 'end_turn'))
    assert scene.runtime.host_status()['current_player'] == 'shu' and scene.failure is None
    assert gate.dispatch(ViewGrant('shu', True), request(scene, 'end_turn')) is True


@pytest.mark.parametrize('grant,cmd,params,error', [
    (ViewGrant('spectator'), 'end_turn', {}, PermissionError),
    (ViewGrant('wei', True), 'set_fog', {'enabled': False}, ValueError),
    (ViewGrant('wei', True), 'end_turn', {'faction': 'shu'}, ValueError),
    (ViewGrant('wei', True), 'move', {'unit_id': True, 'position': [0, 0]}, ValueError),
    (ViewGrant('wei', True), 'move', {'unit_id': '227', 'position': [True, 0]}, ValueError),
    (ViewGrant('wei', True), 'move', {'unit_id': '+227', 'position': [0, 0]}, ValueError),
    (ViewGrant('wei', True), 'move', {'unit_id': str(2**64), 'position': [0, 0]}, ValueError),
    (ViewGrant('wei', True), 'wait', {'unit_id': '232'}, PermissionError),
    (ViewGrant('wei', True), 'capture', {'unit_id': '227', 'position': [1, 3]}, ValueError),
    (ViewGrant('wei', True), 'fortify', {'unit_id': '227', 'position': [1, 3]}, ValueError),
    (ViewGrant('wei', True), 'attack', {'unit_id': '227', 'target_id': '232'}, PermissionError),
])
def test_untrusted_command_rejected_without_retiring_or_mutating_scene(scene, grant, cmd, params, error):
    before = scene.runtime.export_state()
    with pytest.raises(error): CommandGateway(scene).dispatch(grant, request(scene, cmd, **params))
    assert scene.runtime.export_state() == before and scene.failure is None


def test_scene_epoch_and_owner_turn_checks_cannot_be_bypassed(scene):
    gate = CommandGateway(scene)
    with pytest.raises(ValueError, match='Scene changed'):
        gate.dispatch(ViewGrant('wei', True), dict(epoch='0', command='end_turn'))
    # Bypass browser admission to verify permission checks inside the owner.
    scene.runtime.finish_human_turn(expected_epoch=scene.controls.epoch)
    with pytest.raises(PermissionError, match='turn'):
        scene.runtime.execute_human_command('end_turn', {}, faction='wei', expected_epoch=scene.controls.epoch)
    scene.refresh()
    assert scene.runtime.host_status()['current_player'] == 'shu'


def test_agent_slot_does_not_become_human_even_with_a_forged_grant(frozen):
    with NativeSession(renderer='web', scenario='chibi-small', seed=42) as s:
        s.controls.finish_turn()
        with pytest.raises(PermissionError, match='human-controlled'):
            CommandGateway(s).dispatch(ViewGrant('shu', True), request(s, 'end_turn'))
