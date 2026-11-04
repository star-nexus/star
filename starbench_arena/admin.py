"""Local operator commands. This module is never exposed as an MCP tool or HTTP route."""
import argparse
import json
from pathlib import Path
from .hosted import set_grant
from .store import Store


def grant_from_config(path, subject, faction, match_id=None, *, active=True):
    runtime = json.loads(Path(path).read_text())
    attachment = runtime.get('attachment')
    if not attachment:
        raise ValueError('Seat grants require an OAuth attachment')
    store = Store(runtime['database_url'])
    try:
        set_grant(store, runtime['issuer'], subject, match_id or attachment['env_id'], faction, active=active)
    finally:
        store.engine.dispose()
    return {'subject': subject, 'faction': faction, 'active': active}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['grant', 'revoke'])
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--faction', required=True, choices=['wei', 'shu'])
    parser.add_argument('--match-id')
    args = parser.parse_args()
    print(json.dumps(grant_from_config(args.config, args.subject, args.faction,
        args.match_id, active=args.command == 'grant')))


if __name__ == '__main__':
    main()
