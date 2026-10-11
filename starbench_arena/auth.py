from dataclasses import dataclass
import asyncio
import jwt
from mcp.server.auth.provider import AccessToken

@dataclass(frozen=True)
class Principal:
    subject: str
    name: str = ''

class Auth:
    def __init__(self, settings):
        self.settings = settings
        self.keys = jwt.PyJWKClient(settings.jwks_url, timeout=5) if settings.jwks_url else None

    async def claims(self, token):
        if self.settings.development and token.startswith('dev:') and len(token) > 4:
            return {'sub': token[4:], 'name': token[4:], 'scope': 'arena:play', 'exp': 4102444800}
        if self.keys is None:
            raise ValueError('Authentication is not configured')
        key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
        claims = jwt.decode(token, key.key, algorithms=['RS256'], audience=self.settings.audience,
                            issuer=self.settings.issuer, options={'require': ['sub', 'exp', 'iat']})
        if not isinstance(claims['sub'], str) or not claims['sub']:
            raise ValueError('Invalid subject')
        return claims

    async def principal(self, token):
        claims = await self.claims(token)
        if 'arena:play' not in claims.get('scope', '').split():
            raise ValueError('Missing arena:play scope')
        return Principal(claims['sub'], claims.get('name', ''))

    def invited(self, principal):
        if not (self.settings.development or self.settings.open_registration or principal.subject in self.settings.allowed_subjects):
            raise PermissionError('Account is not on the invitation list')

    async def verify_token(self, token):
        try:
            claims = await self.claims(token)
            return AccessToken(token=token, client_id=claims.get('azp', 'arena'),
                scopes=claims.get('scope', '').split(), expires_at=claims['exp'],
                subject=claims['sub'], claims={'iss': self.settings.issuer}, resource=self.settings.public_url.rstrip('/') + '/mcp')
        except (jwt.PyJWTError, ValueError):
            return None
