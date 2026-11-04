import time
from types import SimpleNamespace
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starbench_arena.auth import Auth, Principal
from starbench_arena.config import Settings

@pytest.mark.asyncio
async def test_jwt_resource_issuer_expiry_scope_and_invitation():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    auth = Auth(Settings(issuer='https://auth.example/realms/star', audience='starbench-arena', allowed_subjects=frozenset({'alice'})))
    auth.keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    claims = {'sub':'alice','iss':auth.settings.issuer,'aud':'starbench-arena','iat':int(time.time()),'exp':int(time.time())+60,'scope':'arena:play'}
    def token(**changes): return jwt.encode({**claims, **changes}, key, algorithm='RS256')
    assert (await auth.principal(token())).subject == 'alice'
    for changes in ({'aud':'another-resource'},{'iss':'https://attacker'},{'exp':1},{'scope':'openid'}):
        with pytest.raises((jwt.PyJWTError, ValueError)):
            await auth.principal(token(**changes))
    auth.invited(Principal('alice'))
    with pytest.raises(PermissionError): auth.invited(Principal('bob'))
    assert await auth.verify_token('dev:alice') is None


@pytest.mark.asyncio
async def test_small_issuance_clock_skew_does_not_extend_expiry():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    auth=Auth(Settings(issuer='https://identity.test',audience='arena'))
    auth.keys=SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key()))
    now=time.time()
    claims={'sub':'alice','iss':auth.settings.issuer,'aud':'arena','iat':now+3,'exp':now+60,'scope':'arena:play'}
    def token(**changes):return jwt.encode({**claims,**changes},key,algorithm='RS256')
    assert (await auth.principal(token())).subject=='alice'
    for changes in ({'iat':now+60},{'iat':'invalid'},{'iat':True},{'iat':None},{'iat':float('inf')},
                    {'exp':now-1},{'nbf':now+60}):
        with pytest.raises(jwt.PyJWTError):await auth.principal(token(**changes))
