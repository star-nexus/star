#!/usr/bin/env python3
"""Prepare and deploy from checked configuration; never evaluates .env as shell."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            raise ValueError('Invalid configuration line')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
            value = value[1:-1]
        values[key] = value
    return values

def make_realm(config, credentials):
    audience = 'https://' + config['ARENA_DOMAIN'] + '/mcp'
    scope = {'name':'arena:play', 'protocol':'openid-connect',
        'attributes':{'include.in.token.scope':'true','display.on.consent.screen':'true'},
        'protocolMappers':[{'name':'arena-audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper',
            'config':{'included.custom.audience':audience,'access.token.claim':'true','id.token.claim':'false'}},
            {'name':'subject','protocol':'openid-connect','protocolMapper':'oidc-sub-mapper',
             'config':{'access.token.claim':'true','introspection.token.claim':'true'}}]}
    def client(cid, public, redirects):
        return {'clientId':cid,'enabled':True,'protocol':'openid-connect','publicClient':public,
            'secret':credentials['CHATGPT_CLIENT_SECRET'] if not public else None,
            'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'implicitFlowEnabled':False,
            'serviceAccountsEnabled':False,'redirectUris':redirects,'webOrigins':[],
            'fullScopeAllowed':False,'attributes':{'pkce.code.challenge.method':'S256'},
            'defaultClientScopes':['arena:play']}
    return {'realm':'starbench','enabled':True,'sslRequired':'external','registrationAllowed':False,
        'resetPasswordAllowed':False,'accessTokenLifespan':600,'ssoSessionIdleTimeout':28800,
        'clientScopes':[scope],
        'clients':[client('starbench-chatgpt',False,config['CHATGPT_REDIRECT_URIS'].split(',')),
                   client('starbench-harness',True,['http://127.0.0.1:8769/callback'])],
        'identityProviders':[{'alias':'github','providerId':'github','enabled':True,'trustEmail':False,
            'storeToken':False,'firstBrokerLoginFlowAlias':'first broker login',
            'config':{'clientId':config['GITHUB_CLIENT_ID'],'clientSecret':config['GITHUB_CLIENT_SECRET'],
                      'defaultScope':'read:user user:email'}}],
        'browserFlow':'github-browser',
        'authenticatorConfig':[{'alias':'github-redirect','config':{'defaultProvider':'github'}}],
        'authenticationFlows':[{'alias':'github-browser','providerId':'basic-flow','topLevel':True,'builtIn':False,
            'authenticationExecutions':[{'authenticator':'auth-cookie','requirement':'ALTERNATIVE','priority':10},
                {'authenticator':'identity-provider-redirector','authenticatorConfig':'github-redirect','requirement':'ALTERNATIVE','priority':20}]}]}

def prepare(directory=ROOT):
    config = read_env(directory / '.env')
    for key in ('ARENA_DOMAIN','AUTH_DOMAIN','ACME_EMAIL','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET','CHATGPT_REDIRECT_URIS'):
        if not config.get(key):
            raise ValueError('Fill ' + key + ' in deploy/arena/.env')
    for key in ('ARENA_DOMAIN','AUTH_DOMAIN'):
        if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?', config[key]) or '.' not in config[key] or config[key].endswith('.example.com'):
            raise ValueError('Set a real DNS name for ' + key)
    if config['ARENA_DOMAIN'] == config['AUTH_DOMAIN']:
        raise ValueError('Arena and auth need separate hostnames')
    if not re.fullmatch(r'[^\s{}]+@[^\s{}]+', config['ACME_EMAIL']):
        raise ValueError('Invalid ACME email')
    for uri in config['CHATGPT_REDIRECT_URIS'].split(','):
        url = urlsplit(uri)
        if url.scheme != 'https' or not url.netloc or url.fragment or '*' in uri:
            raise ValueError('Copy exact HTTPS ChatGPT redirect URLs; no wildcards')
    generated = directory / 'generated'
    generated.mkdir(exist_ok=True, mode=0o700)
    os.chmod(generated, 0o700)
    credentials_path = generated / 'credentials.json'
    credentials = json.loads(credentials_path.read_text()) if credentials_path.exists() else {
        key:secrets.token_hex(32) for key in ('POSTGRES_PASSWORD','ARENA_DB_PASSWORD','AUTH_DB_PASSWORD','KEYCLOAK_ADMIN_PASSWORD','CHATGPT_CLIENT_SECRET')}
    credentials_path.write_text(json.dumps(credentials, indent=2)+'\n'); os.chmod(credentials_path, 0o600)
    realm = make_realm(config, credentials)
    (generated / 'realm.json').write_text(json.dumps(realm, indent=2)+'\n')
    # Host directory is private; imported files must be readable by container UIDs.
    os.chmod(generated / 'realm.json', 0o644)
    revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=directory.parents[1], text=True).strip()
    issuer = 'https://' + config['AUTH_DOMAIN'] + '/realms/starbench'
    settings = {'ARENA_DEV':'0','ARENA_DATABASE_URL':'postgresql+psycopg://arena:'+credentials['ARENA_DB_PASSWORD']+'@postgres/arena',
        'ARENA_PUBLIC_URL':'https://'+config['ARENA_DOMAIN'],'ARENA_ISSUER':issuer,
        'ARENA_JWKS_URL':issuer+'/protocol/openid-connect/certs', 'ARENA_AUDIENCE':'https://'+config['ARENA_DOMAIN']+'/mcp',
        'STAR_HUB_URL':'ws://hub:8000/ws/metaverse',
        'ARENA_ALLOWED_SUBJECTS':config.get('ARENA_ALLOWED_SUBJECTS',''),
        'ARENA_BOSS_SUBJECTS':config.get('ARENA_BOSS_SUBJECTS',''),
        'ARENA_OPEN_REGISTRATION':config.get('ARENA_OPEN_REGISTRATION','0'), 'ARENA_SEASON':config.get('ARENA_SEASON','s1'), 'ARENA_ENV_REVISION':revision}
    override = {'services':{
        'postgres':{'environment':{'POSTGRES_USER':'postgres', **{k:credentials[k] for k in ('POSTGRES_PASSWORD','ARENA_DB_PASSWORD','AUTH_DB_PASSWORD')}}},
        'keycloak':{'environment':{'KC_DB':'postgres','KC_DB_URL':'jdbc:postgresql://postgres:5432/keycloak',
            'KC_DB_USERNAME':'keycloak','KC_DB_PASSWORD':credentials['AUTH_DB_PASSWORD'],
            'KC_BOOTSTRAP_ADMIN_USERNAME':'admin','KC_BOOTSTRAP_ADMIN_PASSWORD':credentials['KEYCLOAK_ADMIN_PASSWORD'],
            'KC_HOSTNAME':'https://'+config['AUTH_DOMAIN'],'KC_HTTP_ENABLED':'true','KC_PROXY_HEADERS':'xforwarded','KC_HEALTH_ENABLED':'true'}},
        'arena':{'image':'starbench-arena:'+revision[:12], 'build':{'args':{'ENV_REVISION':revision}},'environment':settings},
        'hub':{'image':'starbench-hub:5e26985','build':{'args':{'ENV_REVISION':revision}}}}}
    # Compose interpolates dollar signs even in JSON files; escape literal values.
    target = generated / 'config.json'
    target.write_text(json.dumps(override, indent=2).replace('$','$$')+'\n'); os.chmod(target,0o600)
    (generated / 'Caddyfile').write_text('''{
    email %s
}
%s {
    request_body {
        max_size 1MB
    }
    header Referrer-Policy no-referrer
    reverse_proxy arena:8780
    log {
        format json
    }
}
%s {
    reverse_proxy keycloak:8080
    log {
        format json
    }
}
''' % (config['ACME_EMAIL'], config['ARENA_DOMAIN'], config['AUTH_DOMAIN']))
    os.chmod(generated / 'Caddyfile',0o644)
    return config

def compose(*args):
    return subprocess.run(['docker','compose','--env-file',str(ROOT/'images.lock'),'-f',str(ROOT/'compose.yaml'),
        '-f',str(ROOT/'generated/config.json'), *args], cwd=ROOT, check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','up','status','logs','backup','stop'])
    args=parser.parse_args()
    if args.command in ('prepare','up'):
        config=prepare()
        print('Configuration prepared. Secrets remain in deploy/arena/generated/credentials.json.')
        if args.command=='up':
            compose('config','--quiet')
            compose('up','-d','--build','--wait','--wait-timeout','300')
            print('Arena: https://'+config['ARENA_DOMAIN']+' | MCP: https://'+config['ARENA_DOMAIN']+'/mcp')
    elif args.command=='status': compose('ps')
    elif args.command=='logs': compose('logs','--tail','100','arena','hub','keycloak','caddy')
    elif args.command=='stop': compose('stop')
    elif args.command=='backup':
        import datetime
        target=ROOT/'backups'; target.mkdir(exist_ok=True,mode=0o700)
        path=target/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.sql')
        with path.open('xb') as output:
            os.chmod(path,0o600)
            subprocess.run(['docker','compose','--env-file',str(ROOT/'images.lock'),'-f',str(ROOT/'compose.yaml'),'-f',str(ROOT/'generated/config.json'),
                'exec','-T','postgres','pg_dumpall','-U','postgres'],stdout=output,check=True)
        print('Saved database backup:',path)
if __name__=='__main__': main()
