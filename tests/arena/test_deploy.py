import json
from pathlib import Path
import pytest
from deploy.arena.deploy import make_realm, prepare

def test_deployment_config_separates_resources_and_enforces_pkce(tmp_path, monkeypatch):
    config={'ARENA_DOMAIN':'arena.test.org','AUTH_DOMAIN':'auth.test.org','ACME_EMAIL':'test@test.org',
        'GITHUB_CLIENT_ID':'github-id','GITHUB_CLIENT_SECRET':'github-secret','CHATGPT_REDIRECT_URIS':'https://chatgpt.com/callback'}
    (tmp_path/'.env').write_text('\n'.join(k+'='+v for k,v in config.items()))
    monkeypatch.setattr('deploy.arena.deploy.subprocess.check_output', lambda *a,**k:'a'*40)
    prepare(tmp_path)
    generated=tmp_path/'generated'
    settings=json.loads((generated/'config.json').read_text())
    arena=settings['services']['arena']['environment']
    assert arena['ARENA_DEV']=='0' and arena['ARENA_OPEN_REGISTRATION']=='0'
    assert arena['ARENA_AUDIENCE']=='https://arena.test.org/mcp'
    realm=json.loads((generated/'realm.json').read_text())
    for client in realm['clients']:
        assert client['attributes']['pkce.code.challenge.method']=='S256'
        assert not client['directAccessGrantsEnabled'] and not client['implicitFlowEnabled']
    secrets=(generated/'credentials.json').read_bytes()
    prepare(tmp_path)
    assert (generated/'credentials.json').read_bytes()==secrets
    assert (generated/'credentials.json').stat().st_mode & 0o777 == 0o600
    assert 'private-test-secret' not in (generated/'Caddyfile').read_text()

def test_example_values_are_not_deployable(tmp_path):
    source=Path('deploy/arena/.env.example').read_text()
    (tmp_path/'.env').write_text(source)
    with pytest.raises(ValueError): prepare(tmp_path)
