"""Self-hosted deployment orchestration. Networking is invoked over its JSON CLI."""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(data, file, indent=2)
        file.write('\n')
    os.replace(temp, path)


def initialize(path, public_url, platform='macos', lifecycle='attach', ingress='direct'):
    if path.exists():
        raise FileExistsError('Configuration already exists')
    state = path.resolve().parent
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    network_root = ROOT.parent / 'star-network'
    config = {'schema_version': 1, 'deployment_id': re.sub('[^a-z0-9-]', '-', state.name.lower())[:64], 'platform': platform,
        'lifecycle': lifecycle, 'ingress_adapter': ingress, 'public_url': public_url.rstrip('/'),
        'auth_public_url': public_url.rstrip('/') + '/auth',
        'hub_url': 'ws://127.0.0.1:8000/ws/metaverse' if platform=='macos' else 'ws://hub:8000/ws/metaverse',
        'attachment': {'env_id': 'public-test-turn-001', 'mode': 'turn_based'},
        'arena_port': 8781, 'auth_port': 8081, 'database_port': 15432,
        'colima_profile': 'starbench', 'colima_cpu': 2, 'colima_memory_gib': 4,
        'min_free_disk_gib': 10,
        'network_source': str(network_root), 'network_config': str(state / 'network.json'),
        'secrets_file': str(state / 'secrets.json'), 'allowed_subjects': [], 'boss_subjects': []}
    from deploy.arena.deploy import public_urls
    public_urls({'ARENA_PUBLIC_URL':config['public_url'], 'AUTH_PUBLIC_URL':config['auth_public_url']})
    dns = {k: os.getenv(v, '') for k,v in (
        ('ALIYUN_ACCESS_KEY_ID','ALIYUN_ACCESSKEY_ID'), ('ALIYUN_ACCESS_KEY_SECRET','ALIYUN_ACCESSKEY_SECRET'))}
    if ingress == 'direct':
        write(state / 'dns.json', dns)
    write(state / 'secrets.json', {'GITHUB_CLIENT_ID': '', 'GITHUB_CLIENT_SECRET': '',
        'CHATGPT_REDIRECT_URIS': '', 'POSTGRES_PASSWORD': secrets.token_hex(32),
        'ARENA_DB_PASSWORD': secrets.token_hex(32), 'AUTH_DB_PASSWORD': secrets.token_hex(32),
        'KEYCLOAK_ADMIN_PASSWORD': secrets.token_hex(32), 'CHATGPT_CLIENT_SECRET': secrets.token_hex(32)})
    net = {'schema_version':1, 'deployment_id':config['deployment_id'],
        'ingress':{'adapter':'direct', 'runtime':'host' if platform=='macos' else 'compose',
            'bind':'::', 'port':urlsplit(public_url).port or 443, 'binary':str(network_root/'bin/caddy')},
        'tls':{'mode':'dns01-alidns', 'email':''}, 'dns':{'expected_addresses':[]},
        'secrets':{'dns_file':str(state/'dns.json')},
        'services':routes(config)}
    if ingress == 'existing':
        net['ingress']={'adapter':'existing'}
        net.pop('tls');net.pop('secrets')
    write(state/'network.json', net)
    write(path, config)
    return {'config':str(path.resolve()), 'mcp_url':public_url.rstrip('/')+'/mcp',
        'github_callback':config['auth_public_url']+'/realms/starbench/broker/github/endpoint',
        'secrets_template':str(state/'secrets.json')}


def routes(config):
    host = config['platform']=='macos' or config.get('ingress_adapter')=='existing'
    arena = f'127.0.0.1:{config["arena_port"]}' if host else 'arena:8780'
    auth = f'127.0.0.1:{config["auth_port"]}' if host else 'keycloak:8080'
    prefix = urlsplit(config['auth_public_url']).path.rstrip('/')
    discovery = prefix+'/realms/starbench/.well-known/openid-configuration'
    return [
        {'id':'identity', 'public_url':config['auth_public_url'], 'upstream':'http://'+auth,
         'routes':[{'path':prefix+'/realms/starbench/*'}, {'path':prefix+'/resources/*'},
            {'path':'/.well-known/oauth-authorization-server'+prefix+'/realms/starbench', 'rewrite':discovery},
            {'path':'/.well-known/openid-configuration'+prefix+'/realms/starbench', 'rewrite':discovery}]},
        {'id':'arena', 'public_url':config['public_url'], 'upstream':'http://'+arena,
         'routes':[{'path':p} for p in ('/mcp', '/.well-known/oauth-protected-resource',
             '/.well-known/oauth-protected-resource/mcp', '/api/*', '/ws/metaverse/env/*',
             '/', '/leaderboard/*', '/watch/*')]}]


def load(path):
    config = json.loads(path.read_text())
    if config.get('schema_version') != 1 or config['platform'] not in ('macos','linux') or config['lifecycle'] not in ('attach','managed'):
        raise ValueError('Unsupported deployment configuration')
    if not config['deployment_id'].replace('-','').isalnum():
        raise ValueError('Invalid deployment_id')
    from deploy.arena.deploy import public_urls
    public_urls({'ARENA_PUBLIC_URL':config['public_url'], 'AUTH_PUBLIC_URL':config['auth_public_url']})
    for key in ('arena_port','auth_port','database_port'):
        if not isinstance(config[key],int) or not 1 <= config[key] <= 65535:
            raise ValueError('Invalid '+key)
    config['ingress_adapter']=json.loads(Path(config['network_config']).read_text())['ingress']['adapter']
    return config


def private(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError('Secret files require mode 0600')
    return json.loads(path.read_text())


def network(config, state, command, *, probe=False):
    spec = json.loads(Path(config['network_config']).read_text())
    if spec['deployment_id'] != config['deployment_id']:
        raise ValueError('Network deployment identity mismatch')
    spec['services'] = routes(config)
    if probe:
        spec['services'] = [dict(spec['services'][1], routes=[{'path':'/mcp'}])]
    netfile = state / ('probe-network.json' if probe else 'active-network.json')
    write(netfile, spec)
    env = {**os.environ, 'PYTHONPATH':config['network_source']}
    run = subprocess.run([sys.executable, '-m', 'star_network', command, '--config', str(netfile),
        '--state-dir',str(state/'network')], env=env, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError('Network operation failed: '+run.stderr[-1500:])
    result = json.loads(run.stdout)
    if command in ('plan','apply'):
        expected = {s['id']:s['public_url'] for s in spec['services']}
        if result['deployment_id'] != config['deployment_id'] or result['endpoints'] != expected:
            raise ValueError('Network output does not match the requested service identities')
    return result


def tunnel_control(config, state, command):
    """Optional transport stays behind the independent network project's CLI."""
    path=state/'tunnel.json'
    if not path.exists():
        raise ValueError('Configure this instance tunnel.json before using the optional tunnel')
    env={**os.environ,'PYTHONPATH':config['network_source']}
    result=subprocess.run([sys.executable,'-m','star_network.tunnel',command,
        '--config',str(path),'--state-dir',str(state/'tunnel')],env=env,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('Tunnel operation failed: '+result.stderr[-1200:])
    return json.loads(result.stdout)


def generated(config, state, *, require_oauth=True):
    from deploy.arena.deploy import make_realm, read_env
    credentials = private(config['secrets_file'])
    if require_oauth and any(not credentials.get(k) for k in ('GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','CHATGPT_REDIRECT_URIS')):
        raise ValueError('Fill GitHub OAuth client ID/secret and exact ChatGPT redirect URIs in secrets.json')
    for uri in credentials.get('CHATGPT_REDIRECT_URIS','').split(','):
        if uri and (urlsplit(uri).scheme!='https' or '*' in uri or urlsplit(uri).fragment):
            raise ValueError('ChatGPT callback must be an exact HTTPS URL')
    images = read_env(ROOT/'deploy/arena/images.lock')
    realm = make_realm({'ARENA_PUBLIC_URL':config['public_url'], 'AUTH_PUBLIC_URL':config['auth_public_url'],
        **{k:credentials.get(k,'') for k in ('GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','CHATGPT_REDIRECT_URIS')}}, credentials)
    write(state/'realm.json', realm)
    # Parent directory is private; container UID must be able to read the mount.
    os.chmod(state/'realm.json', 0o644)
    host = config['platform']=='macos'
    issuer = config['auth_public_url']+'/realms/starbench'
    dbhost = '127.0.0.1:'+str(config['database_port']) if host else 'postgres:5432'
    runtime = {'database_url':f'postgresql+psycopg://arena:{credentials["ARENA_DB_PASSWORD"]}@{dbhost}/arena',
        'public_url':config['public_url'], 'issuer':issuer, 'audience':config['public_url']+'/mcp',
        'jwks_url':issuer+'/protocol/openid-connect/certs',
        'hub_url':config['hub_url'],
        'allowed_subjects':config['allowed_subjects'], 'boss_subjects':config['boss_subjects'],
        'development':False, 'open_registration':False,
        'attachment':config['attachment'] if config['lifecycle']=='attach' else None}
    write(state/'runtime.json', runtime)
    health_path = (urlsplit(config['auth_public_url']).path or '').rstrip('/') + '/health/ready'
    services = {
        'postgres':{'image':images['POSTGRES_IMAGE'],'restart':'unless-stopped',
            'environment':{'POSTGRES_USER':'postgres',**{k:credentials[k] for k in ('POSTGRES_PASSWORD','ARENA_DB_PASSWORD','AUTH_DB_PASSWORD')}},
            'volumes':['postgres-data:/var/lib/postgresql/data', str(ROOT/'deploy/arena/init-db.sh')+':/docker-entrypoint-initdb.d/10-arena.sh:ro'],
            'healthcheck':{'test':['CMD-SHELL','pg_isready -U postgres'],'interval':'5s','timeout':'5s','retries':30}},
        'keycloak':{'image':images['KEYCLOAK_IMAGE'],'command':['start','--import-realm'],'restart':'unless-stopped',
            'depends_on':{'postgres':{'condition':'service_healthy'}},
            'environment':{'KC_DB':'postgres','KC_DB_URL':'jdbc:postgresql://postgres:5432/keycloak',
                'KC_DB_USERNAME':'keycloak','KC_DB_PASSWORD':credentials['AUTH_DB_PASSWORD'],
                'KC_BOOTSTRAP_ADMIN_USERNAME':'admin','KC_BOOTSTRAP_ADMIN_PASSWORD':credentials['KEYCLOAK_ADMIN_PASSWORD'],
                'KC_HOSTNAME':config['auth_public_url'],'KC_HTTP_RELATIVE_PATH':urlsplit(config['auth_public_url']).path or '/',
                'KC_HTTP_ENABLED':'true','KC_PROXY_HEADERS':'xforwarded','KC_HEALTH_ENABLED':'true'},
            'volumes':[str(state/'realm.json')+':/opt/keycloak/data/import/starbench-realm.json:ro'],
            'healthcheck':{'test':['CMD','/bin/bash','-c',f'exec 3<>/dev/tcp/127.0.0.1/9000; printf "GET {health_path} HTTP/1.0\\r\\n\\r\\n" >&3; read -r status <&3; [[ "$status" == *" 200 "* ]]'], 'interval':'10s','timeout':'5s','retries':40}}
    }
    if host:
        services['postgres']['ports']=[f'127.0.0.1:{config["database_port"]}:5432']
        services['keycloak']['ports']=[f'127.0.0.1:{config["auth_port"]}:8080']
    else:
        revision=source_revision(ROOT)
        args={k:v for k,v in images.items() if k in ('PYTHON_IMAGE','NODE_IMAGE','RUST_IMAGE')}
        args['ENV_REVISION']=revision
        for name,target in (('arena','runtime'),('hub','hub')):
            services[name]={'build':{'context':str(ROOT),'dockerfile':'deploy/arena/Dockerfile','target':target,'args':args},
                'restart':'unless-stopped','init':True}
        services['arena'].update({'command':['python','-m','starbench_arena.self_hosted','--config','/run/arena/runtime.json','--host','0.0.0.0','--port','8780'],
            'volumes':[str(state/'runtime.json')+':/run/arena/runtime.json:ro','arena-data:/app/.arena'],
            'depends_on':{'postgres':{'condition':'service_healthy'},'keycloak':{'condition':'service_healthy'}}})
        # Container runtime UID needs access to the read-only secret file, not its parent.
        os.chmod(state/'runtime.json',0o644)
        net = network(config,state,'plan')
        if config.get('ingress_adapter')=='existing':
            services['arena']['ports']=[f'127.0.0.1:{config["arena_port"]}:8780']
            services['keycloak']['ports']=[f'127.0.0.1:{config["auth_port"]}:8080']
        else:
            add_container_ingress(config,state,services,net)
    for name,service in services.items():
        service['networks']=['private'] if name in ('postgres','hub') else ['edge','private'] if name in ('arena','keycloak') else ['edge']
        service['logging']={'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}
    compose={'name':'starbench-'+config['deployment_id'],'services':services,
        'networks':{'edge':{},'private':{'internal':True}},
        'volumes':{name:{} for name in ('postgres-data','arena-data','caddy-data')}}
    write(state/'compose.json', json.loads(json.dumps(compose).replace('$','$$')))
    return {'runtime_config':str(state/'runtime.json'), 'compose_config':str(state/'compose.json'),
        'github_callback':issuer+'/broker/github/endpoint', 'mcp_url':config['public_url']+'/mcp'}


def add_container_ingress(config,state,services,net):
    spec=json.loads(Path(config['network_config']).read_text())
    proxy=net['caddy_config']; proxy['admin']={'disabled':True}; proxy['storage']['root']='/data'
    volumes=[str(state/'caddy.json')+':/etc/caddy/config.json:ro','caddy-data:/data']
    environment={}
    if spec['tls']['mode']=='dns01-alidns':
        dns=private(spec['secrets']['dns_file'])
        environment={key:dns[key] for key in ('ALIYUN_ACCESS_KEY_ID','ALIYUN_ACCESS_KEY_SECRET')}
    else:
        proxy['apps']['tls']['certificates']['load_files']=[{'certificate':'/run/cert.pem','key':'/run/key.pem'}]
        volumes.extend([spec['tls']['certificate']+':/run/cert.pem:ro',spec['tls']['key']+':/run/key.pem:ro'])
    write(state/'caddy.json',proxy); os.chmod(state/'caddy.json',0o644)
    public_port=urlsplit(config['public_url']).port or 443
    listen_port=spec['ingress']['port']
    services['ingress']={'build':{'context':config['network_source'],'dockerfile':'Dockerfile'},
        'command':['caddy','run','--config','/etc/caddy/config.json'], 'restart':'unless-stopped',
        'ports':[f'{public_port}:{listen_port}'],'environment':environment,'volumes':volumes}


def compose(config,state,*args,stdout=None,stdin=None):
    env=dict(os.environ)
    command=['docker']
    if config['platform']=='macos':
        # Isolated CLI config avoids rewriting the user's global Docker settings/context.
        folder=state/'docker-cli'
        plugin=Path(shutil.which('docker-compose') or '/opt/homebrew/bin/docker-compose').resolve().parent
        write(folder/'config.json',{'cliPluginsExtraDirs':[str(plugin)]})
        env['DOCKER_HOST']='unix://'+str(Path.home()/'.colima'/config['colima_profile']/'docker.sock')
        env.pop('DOCKER_CONTEXT',None)
        command.extend(['--config',str(folder)])
    return subprocess.run(command+['compose','-f',str(state/'compose.json'),*args],env=env,check=True,stdout=stdout,stdin=stdin)


def process_identity(pid):
    r=subprocess.run(['ps','-p',str(pid),'-o','lstart=','-o','command='],capture_output=True,text=True)
    return r.stdout.strip() if r.returncode==0 else ''


def stop_gateway(state):
    file=state/'gateway.json'
    if not file.exists(): return
    proc=json.loads(file.read_text())
    if proc['identity'] and process_identity(proc['pid'])==proc['identity']:
        os.kill(proc['pid'],signal.SIGTERM)
        for _ in range(100):
            if process_identity(proc['pid'])!=proc['identity']: break
            time.sleep(.1)
        else: raise RuntimeError('Gateway did not exit; not forcing termination')
    file.unlink(missing_ok=True)


def start_gateway(config,state,probe=False):
    mode='probe' if probe else 'arena'
    file=state/'gateway.json'
    if file.exists():
        proc=json.loads(file.read_text())
        if proc['identity'] and process_identity(proc['pid'])==proc['identity']:
            if proc['mode']==mode:return
            stop_gateway(state)
    command=[str(ROOT/'.venv/bin/python'),'-m','starbench_arena.probe' if probe else 'starbench_arena.self_hosted']
    command+=['--public-url',config['public_url']] if probe else ['--config',str(state/'runtime.json')]
    command+=['--port',str(config['arena_port'])]
    fd=os.open(state/'gateway.log',os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
    with os.fdopen(fd,'ab') as log:
        child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    time.sleep(.5)
    if child.poll() is not None:raise RuntimeError('Gateway exited; inspect private gateway.log')
    write(file,{'pid':child.pid,'identity':process_identity(child.pid),'mode':mode})



def source_revision(root):
    marker=root/'SOURCE_REVISION'
    if marker.exists():return marker.read_text().strip()
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()


def bundle(config,output):
    """Export committed sources only; never include runtime configs or credentials."""
    import io
    import tarfile
    roots={'star-main':ROOT,'star-network':Path(config['network_source'])}
    revisions={}
    pinned=json.loads((ROOT/'deploy/arena/network.lock.json').read_text())
    if source_revision(roots['star-network'])!=pinned['source_revision']:
        raise ValueError('Network source differs from deploy/arena/network.lock.json')
    for name,root in roots.items():
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True).strip():
            raise ValueError('Commit source changes before creating a release bundle: '+name)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as file,tarfile.open(fileobj=file,mode='w:gz') as target:
        for name,root in roots.items():
            revisions[name]=source_revision(root)
            archive=subprocess.check_output(['git','archive','--format=tar','HEAD'],cwd=root)
            with tarfile.open(fileobj=io.BytesIO(archive)) as source:
                for member in source:
                    member.name=name+'/'+member.name
                    content=source.extractfile(member) if member.isfile() else None
                    target.addfile(member,content)
            data=(revisions[name]+'\n').encode();member=tarfile.TarInfo(name+'/SOURCE_REVISION');member.size=len(data)
            target.addfile(member,io.BytesIO(data))
    return {'bundle':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'revisions':revisions}


def check_disk(config, state):
    # Image pulls/builds can exhaust the host volume before Docker reports it.
    # This is a configurable deployment guard, not a game performance setting.
    minimum = float(config.get('min_free_disk_gib', 10))
    if minimum <= 0:
        raise ValueError('min_free_disk_gib must be positive')
    free = shutil.disk_usage(state).free / 1024**3
    if free < minimum:
        raise ValueError(f'Deployment requires at least {minimum:g} GiB free on the host; '
            f'{free:.1f} GiB available. Free space before starting containers.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['init','plan','prepare','probe','up','status','diagnose','stop','down','backup','restore','bundle','grant','revoke','tunnel-start','tunnel-status','tunnel-stop'])
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--public-url',help='Explicit HTTPS origin for a new deployment')
    p.add_argument('--platform',choices=['macos','linux'],default='macos')
    p.add_argument('--lifecycle',choices=['attach','managed'],default='attach')
    p.add_argument('--ingress',choices=['direct','existing'],default='direct')
    p.add_argument('--subject');p.add_argument('--faction',choices=['wei','shu']);p.add_argument('--match-id')
    p.add_argument('--backup-file',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.command=='init':
        if not a.public_url:p.error('init requires --public-url; no shared domain is assumed')
        print(json.dumps(initialize(a.config,a.public_url,a.platform,a.lifecycle,a.ingress),indent=2));return
    config=load(a.config);state=a.config.resolve().parent
    # All deployment mutations are serialized independently of the network process lock.
    with (state/'deployment.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.command.startswith('tunnel-'):
            print(json.dumps(tunnel_control(config,state,a.command.removeprefix('tunnel-')),indent=2))
        elif a.command=='plan':
            print(json.dumps(network(config,state,'plan'),indent=2))
        elif a.command=='probe':
            if config['platform']!='macos':raise ValueError('Probe orchestration is currently a Mac host command')
            start_gateway(config,state,True)
            print(json.dumps(network(config,state,'apply',probe=True),indent=2))
        elif a.command in ('prepare','up'):
            if a.command=='up':check_disk(config,state)
            result=generated(config,state)
            if a.command=='up':
                if config['platform']=='macos':
                    subprocess.run(['colima','start','--profile',config['colima_profile'],'--cpu',str(config['colima_cpu']),
                        '--memory',str(config['colima_memory_gib']),'--activate=false'],check=True)
                compose(config,state,'up','-d','--build','--wait','--wait-timeout','300')
                if config['platform']=='macos':
                    start_gateway(config,state)
                    network(config,state,'apply')
            print(json.dumps(result,indent=2))
        elif a.command in ('status','diagnose'):
            print(json.dumps(network(config,state,'status'),indent=2))
        elif a.command in ('stop','down'):
            if config['platform']=='macos':
                network(config,state,'stop');stop_gateway(state)
            if (state/'compose.json').exists():compose(config,state,'stop')
        elif a.command=='bundle':
            if not a.output:raise ValueError('--output required')
            print(json.dumps(bundle(config,a.output),indent=2))
        elif a.command=='backup':
            import zipfile
            import tempfile
            target=state/'backups'/ (time.strftime('%Y%m%dT%H%M%S')+'.zip')
            target.parent.mkdir(exist_ok=True,mode=0o700)
            with tempfile.TemporaryDirectory(dir=state) as folder:
                for database in ('arena','keycloak'):
                    with (Path(folder)/(database+'.dump')).open('wb') as output:
                        compose(config,state,'exec','-T','postgres','pg_dump','-U','postgres','-Fc',database,stdout=output)
                fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as output, zipfile.ZipFile(output,'w') as archive:
                    for database in ('arena','keycloak'):
                        archive.write(Path(folder)/(database+'.dump'),database+'.dump')
                    archive.writestr('manifest.json',json.dumps({'schema_version':1,'issuer':config['auth_public_url']+'/realms/starbench'}))
            print(json.dumps({'backup':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
        elif a.command=='restore':
            import zipfile
            if not a.backup_file:raise ValueError('--backup-file required; restore into a fresh deployment')
            if (state/'gateway.json').exists():raise ValueError('Stop gateway before restoring')
            running=compose(config,state,'ps','--status','running','--services',stdout=subprocess.PIPE).stdout.decode().split()
            if any(name!='postgres' for name in running):raise ValueError('Only PostgreSQL may run during restore')
            with zipfile.ZipFile(a.backup_file) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                if manifest['schema_version']!=1 or manifest['issuer']!=config['auth_public_url']+'/realms/starbench':
                    raise ValueError('Backup identity differs; explicit identity migration required')
                for database in ('arena','keycloak'):
                    count=compose(config,state,'exec','-T','postgres','psql','-U','postgres','-d',database,'-Atc',
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",stdout=subprocess.PIPE).stdout.decode().strip()
                    if count!='0':raise ValueError('Restore requires empty destination databases')
                import tempfile
                for database in ('arena','keycloak'):
                    with tempfile.TemporaryFile() as source:
                        source.write(archive.read(database+'.dump'));source.seek(0)
                        compose(config,state,'exec','-T','postgres','pg_restore','-U','postgres','--no-owner','--no-acl','--role',database,
                            '--exit-on-error','-d',database,stdin=source)
            print(json.dumps({'restored':str(a.backup_file)}))
        else:
            if not a.subject or not a.faction:raise ValueError('--subject and --faction required')
            if config['lifecycle']!='attach':raise ValueError('Seat grants require attach mode')
            if config['platform']=='linux':
                args=['exec','-T','arena','python','-m','starbench_arena.admin',a.command,
                    '--config','/run/arena/runtime.json','--subject',a.subject,'--faction',a.faction]
                if a.match_id:args+=['--match-id',a.match_id]
                compose(config,state,*args)
            else:
                from starbench_arena.admin import grant_from_config
                private(state/'runtime.json')
                print(json.dumps(grant_from_config(state/'runtime.json',a.subject,a.faction,
                    a.match_id,active=a.command=='grant')))

if __name__=='__main__':main()
