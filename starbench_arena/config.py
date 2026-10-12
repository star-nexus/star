from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv('ARENA_DATABASE_URL', 'sqlite:///arena.db'))
    hub_url: str = field(default_factory=lambda: os.getenv('STAR_HUB_URL', 'ws://127.0.0.1:8000/ws/metaverse'))
    public_url: str = field(default_factory=lambda: os.getenv('ARENA_PUBLIC_URL', 'http://127.0.0.1:8780'))
    issuer: str = field(default_factory=lambda: os.getenv('ARENA_ISSUER', ''))
    audience: str = field(default_factory=lambda: os.getenv('ARENA_AUDIENCE', 'starbench-arena'))
    jwks_url: str = field(default_factory=lambda: os.getenv('ARENA_JWKS_URL', ''))
    allowed_subjects: frozenset[str] = field(default_factory=lambda: frozenset(filter(None, os.getenv('ARENA_ALLOWED_SUBJECTS', '').split(','))))
    open_registration: bool = field(default_factory=lambda: os.getenv('ARENA_OPEN_REGISTRATION') == '1')
    development: bool = field(default_factory=lambda: os.getenv('ARENA_DEV') == '1')
    boss_subjects: frozenset[str] = field(default_factory=lambda: frozenset(filter(None, os.getenv('ARENA_BOSS_SUBJECTS', '').split(','))))
    season: str = field(default_factory=lambda: os.getenv('ARENA_SEASON', 's1'))
    scenario: str = 'chibi-small'
    prepare_seconds: float = 300
    turn_seconds: float = 300
    max_agents: int = 1000
    max_matches_per_user: int = 1
    worker_host: str = field(default_factory=lambda: os.getenv('ARENA_WORKER_HOST', '127.0.0.1'))
    worker_bind: str = field(default_factory=lambda: os.getenv('ARENA_WORKER_BIND', '127.0.0.1'))

    def validate(self):
        if not self.development:
            if not self.issuer.startswith('https://') or not self.jwks_url.startswith('https://'):
                raise ValueError('Production requires HTTPS ARENA_ISSUER and ARENA_JWKS_URL')
            if not self.public_url.startswith('https://'):
                raise ValueError('Production requires HTTPS ARENA_PUBLIC_URL')
        return self
