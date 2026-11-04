"""Opt-in local Keycloak protocol test. No GitHub/browser/public-network assertion."""
import base64
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4
import httpx
import jwt
import pytest
from deploy.arena.self_hosted import load,private
from starbench_arena.auth import Auth
from starbench_arena.config import Settings


class LoginForm(HTMLParser):
    action=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='form' and attrs.get('id')=='kc-form-login':self.action=attrs['action']


@pytest.mark.asyncio
async def test_real_keycloak_pkce_resource_refresh_and_identity():
    path=os.getenv('STAR_ARENA_IDENTITY_TEST_CONFIG')
    if not path:pytest.skip('Opt-in isolated Keycloak regression instance required')
    config=load(Path(path))
    assert config['deployment_id']=='identity-regression' and config['platform']=='macos'
    credentials=private(config['secrets_file'])
    base=f'http://127.0.0.1:{config["auth_port"]}/auth'
    public=config['public_url'];resource=public+'/mcp'
    headers={'X-Forwarded-Proto':'https','X-Forwarded-Host':urlsplit(public).netloc,'X-Forwarded-Port':str(urlsplit(public).port or 443)}
    name='regression-'+uuid4().hex
    issuer=public+'/auth/realms/'+name
    verifier='v'*64
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    with httpx.Client(trust_env=False,timeout=20,headers=headers,follow_redirects=False) as http:
        admin=http.post(base+'/realms/master/protocol/openid-connect/token',data={
            'client_id':'admin-cli','grant_type':'password','username':'admin','password':credentials['KEYCLOAK_ADMIN_PASSWORD']})
        assert admin.status_code==200, 'Local regression admin authentication failed'
        admin_headers={'Authorization':'Bearer '+admin.json()['access_token']}
        from deploy.arena.deploy import make_realm
        realm=make_realm({'ARENA_PUBLIC_URL':public,'AUTH_PUBLIC_URL':public+'/auth',
            'CHATGPT_REDIRECT_URIS':'https://client.test/callback','GITHUB_CLIENT_ID':'test',
            'GITHUB_CLIENT_SECRET':'unused-test-value'}, {'CHATGPT_CLIENT_SECRET':'unused-test-value'})
        realm.update(realm=name,browserFlow='browser',users=[{'username':'alice','enabled':True,
            'email':'alice@example.test','emailVerified':True,'firstName':'Test','lastName':'Player',
            'credentials':[{'type':'password','value':'local-test-password','temporary':False}]}])
        # Use the production scope/mappers and PKCE contract with a temporary public test client.
        realm['clients']=[dict(realm['clients'][1],clientId='regression-client',
            redirectUris=['https://client.test/callback'])]
        created=http.post(base+'/admin/realms',headers=admin_headers,json=realm)
        assert created.status_code==201,'Cannot create isolated regression realm'
        try:
            endpoint=base+'/realms/'+name
            discovery=http.get(endpoint+'/.well-known/openid-configuration').json()
            assert discovery['issuer']==issuer
            assert 'S256' in discovery['code_challenge_methods_supported']
            params={'client_id':'regression-client','redirect_uri':'https://client.test/callback',
                'response_type':'code','scope':'openid profile email arena:play','state':'test-state',
                'code_challenge':challenge,'code_challenge_method':'S256','resource':resource}
            missing=dict(params);missing.pop('code_challenge');missing.pop('code_challenge_method')
            invalid=http.get(endpoint+'/protocol/openid-connect/auth',params=missing)
            assert invalid.status_code in (302,400) and 'code=' not in invalid.headers.get('location','')
            page=http.get(endpoint+'/protocol/openid-connect/auth',params=params)
            assert page.status_code==200,'Authorization page failed'
            form=LoginForm();form.feed(page.text)
            assert form.action and urlsplit(form.action).hostname==urlsplit(public).hostname
            local_action=form.action.replace(public,'http://127.0.0.1:'+str(config['auth_port']),1)
            # This isolated test addresses Keycloak through loopback HTTP while its
            # canonical origin is HTTPS. Forward its Secure cookies explicitly only
            # here; production browsers use the real HTTPS origin.
            cookies='; '.join(f'{c.name}={c.value}' for c in http.cookies.jar)
            accepted=http.post(local_action,headers={'Cookie':cookies},data={'username':'alice','password':'local-test-password'})
            assert accepted.status_code==302,'Login did not produce an authorization response'
            location=accepted.headers['location'];q=parse_qs(urlsplit(location).query)
            assert q.get('state')==['test-state'] and q.get('iss')==[issuer] and q.get('code')
            exchange={'client_id':'regression-client','grant_type':'authorization_code','code':q['code'][0],
                'redirect_uri':'https://client.test/callback','code_verifier':verifier,'resource':resource}
            token=http.post(endpoint+'/protocol/openid-connect/token',data=exchange)
            assert token.status_code==200,'PKCE token exchange failed'
            body=token.json()
            auth=Auth(Settings(public_url=public,issuer=issuer,audience=resource,jwks_url=issuer+'/protocol/openid-connect/certs'))
            auth.keys=jwt.PyJWKClient(endpoint+'/protocol/openid-connect/certs')
            claims=await auth.claims(body['access_token'])
            assert claims['email']=='alice@example.test' and claims['email_verified'] is True
            assert claims['preferred_username']=='alice'
            assert {'profile','email','arena:play'} <= set(claims['scope'].split())
            principal=await auth.principal(body['access_token'])
            assert principal.subject and principal.issuer==issuer
            refreshed=http.post(endpoint+'/protocol/openid-connect/token',data={
                'client_id':'regression-client','grant_type':'refresh_token','refresh_token':body['refresh_token'],'resource':resource})
            assert refreshed.status_code==200
            assert (await auth.principal(refreshed.json()['access_token'])).subject==principal.subject
            # Code replay can revoke the login session; check after refresh.
            assert http.post(endpoint+'/protocol/openid-connect/token',data=exchange).status_code==400
        finally:
            removed=http.delete(base+'/admin/realms/'+name,headers=admin_headers)
            assert removed.status_code==204,'Regression realm cleanup failed'
