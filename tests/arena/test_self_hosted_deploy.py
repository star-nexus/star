import json
from pathlib import Path
import pytest
from deploy.arena.self_hosted import initialize,load,generated,routes
from deploy.arena.deploy import public_urls


def test_origin_port_auth_path_and_legacy_compatibility():
    assert public_urls({'ARENA_DOMAIN':'arena.test.org','AUTH_DOMAIN':'auth.test.org'})==('https://arena.test.org','https://auth.test.org')
    assert public_urls({'ARENA_PUBLIC_URL':'https://mcp.test.org:10000','AUTH_PUBLIC_URL':'https://mcp.test.org:10000/auth'})==('https://mcp.test.org:10000','https://mcp.test.org:10000/auth')
    with pytest.raises(ValueError):public_urls({'ARENA_DOMAIN':'old.test.org','ARENA_PUBLIC_URL':'https://new.test.org','AUTH_DOMAIN':'auth.test.org'})


def test_mac_template_private_loopback_and_oauth_metadata(tmp_path,monkeypatch):
    monkeypatch.delenv('ALIYUN_ACCESSKEY_ID',raising=False);monkeypatch.delenv('ALIYUN_ACCESSKEY_SECRET',raising=False)
    config_path=tmp_path/'deployment.json'
    initialize(config_path,'https://mcp.test.org:10000')
    c=load(config_path)
    secret_path=tmp_path/'secrets.json';s=json.loads(secret_path.read_text())
    s.update(GITHUB_CLIENT_ID='test-client',GITHUB_CLIENT_SECRET='private-not-in-plan',CHATGPT_REDIRECT_URIS='https://chatgpt.com/callback')
    secret_path.write_text(json.dumps(s))
    generated(c,tmp_path)
    realm=json.loads((tmp_path/'realm.json').read_text())
    audience=realm['clientScopes'][0]['protocolMappers'][0]['config']['included.custom.audience']
    assert audience=='https://mcp.test.org:10000/mcp'
    compose=json.loads((tmp_path/'compose.json').read_text())
    assert compose['services']['keycloak']['environment']['KC_HTTP_RELATIVE_PATH']=='/auth'
    assert compose['services']['keycloak']['ports']==['127.0.0.1:8081:8080']
    assert compose['services']['postgres']['ports']==['127.0.0.1:15432:5432']
    runtime=json.loads((tmp_path/'runtime.json').read_text())
    assert runtime['issuer']=='https://mcp.test.org:10000/auth/realms/starbench'
    assert runtime['development'] is False
    assert (tmp_path/'secrets.json').stat().st_mode&0o777==0o600
    assert (tmp_path/'runtime.json').stat().st_mode&0o777==0o600
    mapping=routes(c)
    assert not any('/admin' in rule['path'] for item in mapping for rule in item['routes'])
    assert mapping[0]['routes'][2]['rewrite']=='/auth/realms/starbench/.well-known/openid-configuration'
    assert 'private-not-in-plan' not in json.dumps(mapping)
    with pytest.raises(FileExistsError):initialize(config_path,c['public_url'])


def test_existing_ingress_never_copies_dns_credentials_or_builds_proxy(tmp_path,monkeypatch):
    monkeypatch.setenv('ALIYUN_ACCESSKEY_ID','must-not-copy')
    path=tmp_path/'deployment.json'
    initialize(path,'https://star.test.org',platform='linux',lifecycle='managed',ingress='existing')
    assert not (tmp_path/'dns.json').exists()
    config=load(path)
    assert json.loads((tmp_path/'network.json').read_text())['ingress']=={'adapter':'existing'}
    monkeypatch.setattr('deploy.arena.self_hosted.network',lambda *a,**k:{'adapter':'existing'})
    generated(config,tmp_path,require_oauth=False)
    compose=json.loads((tmp_path/'compose.json').read_text())
    assert 'ingress' not in compose['services']
    assert compose['services']['arena']['ports']==['127.0.0.1:8781:8780']
    assert 'ports' not in compose['services']['hub']
    assert 'ports' not in compose['services']['postgres']
    assert compose['networks']['private']['internal']
    assert 'must-not-copy' not in json.dumps(compose)


def test_custom_identity_prefix_healthcheck(tmp_path):
    path=tmp_path/'deployment.json'
    initialize(path,'https://star.test.org',ingress='existing')
    config=load(path)
    config['auth_public_url']='https://star.test.org/identity'
    generated(config,tmp_path,require_oauth=False)
    compose=json.loads((tmp_path/'compose.json').read_text())
    check=compose['services']['keycloak']['healthcheck']['test'][-1]
    assert 'GET /identity/health/ready ' in check
    assert '/auth/health' not in check


def test_disk_guard_reports_insufficient_space(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from deploy.arena.self_hosted import check_disk
    monkeypatch.setattr('deploy.arena.self_hosted.shutil.disk_usage',lambda path:SimpleNamespace(free=1024**3))
    with pytest.raises(ValueError,match='1.0 GiB available'):
        check_disk({'min_free_disk_gib':10},tmp_path)


def test_init_requires_explicit_public_origin(tmp_path,monkeypatch):
    from deploy.arena.self_hosted import main
    monkeypatch.setattr('sys.argv',['self_hosted','init','--config',str(tmp_path/'deployment.json')])
    with pytest.raises(SystemExit) as result:main()
    assert result.value.code==2
    assert not (tmp_path/'deployment.json').exists()


def test_source_bundle_omits_untracked_files_and_rejects_modified_source(tmp_path,monkeypatch):
    import subprocess
    import tarfile
    from deploy.arena.self_hosted import bundle
    roots={}
    def git(root,*args):
        return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
    for name in ('star-main','star-network'):
        root=tmp_path/name;root.mkdir();roots[name]=root
        git(root,'init','-q');git(root,'config','user.email','test@example.test');git(root,'config','user.name','Test')
        (root/'source.py').write_text('# release input\n')
        git(root,'add','source.py');git(root,'commit','-qm','source')
        (root/'private-local.txt').write_text('must never be packaged')
    revision=git(roots['star-network'],'rev-parse','HEAD')
    lock=roots['star-main']/'deploy/arena/network.lock.json';lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({'source_revision':revision}))
    git(roots['star-main'],'add','deploy');git(roots['star-main'],'commit','-qm','pin network')
    monkeypatch.setattr('deploy.arena.self_hosted.ROOT',roots['star-main'])
    output=tmp_path/'release.tar.gz';config={'network_source':str(roots['star-network'])}
    result=bundle(config,output)
    assert result['revisions']['star-network']==revision
    with tarfile.open(output) as archive:
        assert 'star-main/source.py' in archive.getnames()
        assert 'star-network/SOURCE_REVISION' in archive.getnames()
        assert not any('private-local' in name for name in archive.getnames())
    (roots['star-network']/'source.py').write_text('# uncommitted change\n')
    with pytest.raises(ValueError,match='Commit source changes'):
        bundle(config,tmp_path/'rejected.tar.gz')
    assert not (tmp_path/'rejected.tar.gz').exists()


def test_optional_tunnel_uses_network_cli_without_application_tokens(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from deploy.arena.self_hosted import tunnel_control
    config={'network_source':'/independent/network'}
    with pytest.raises(ValueError,match='Configure this instance tunnel.json'):
        tunnel_control(config,tmp_path,'status')
    (tmp_path/'tunnel.json').write_text('{}')
    captured={}
    def run(args,**kwargs):
        captured.update(args=args,**kwargs)
        return SimpleNamespace(returncode=0,stdout='{"owned_process": true}',stderr='')
    monkeypatch.setattr('deploy.arena.self_hosted.subprocess.run',run)
    assert tunnel_control(config,tmp_path,'status')['owned_process']
    assert captured['args'][1:4]==['-m','star_network.tunnel','status']
    assert captured['env']['PYTHONPATH']=='/independent/network'
    assert str(tmp_path/'tunnel.json') in captured['args']
    assert not any('Bearer' in str(item) for item in captured['args'])
