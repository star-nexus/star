"""Attach lifecycle shared by local-token and OAuth gateways; never owns the ENV."""
import asyncio
import time
from .backend import Workers
from .service import Arena
from . import store as db

class ExternalWorkers(Workers):
    """Use existing HUB connections only. Never spawn, stop, or reset an ENV."""
    async def launch(self, match):
        raise ValueError('Launch the Rust ENV in its own terminal first')

    async def control(self, worker, command):
        raise ValueError('External ENV lifecycle belongs to its local operator')

    async def close_match(self, match):
        for key, client in list(self.clients.items()):
            if client.env_id == match['id']:
                await client.disconnect()
                del self.clients[key]

    async def client(self, agent, *, verify=True):
        previous = self.clients.get(agent['id'])
        client = await super().client(agent)
        if agent.get('registered') and (verify or client is not previous):
            # Reusing the config after replacing/resetting its ENV would make
            # persisted operation results belong to another world. Fail closed.
            record = await client.call('get_operation', {'operation_id': 'arena-registration-v1'})
            if record.get('state') != 'completed':
                await client.disconnect()
                raise RuntimeError('ENV identity was lost. Start a fresh ENV ID and local configuration.')
        return client


class AttachedArena(Arena):
    async def receive_event(self, agent, payload):
        await super().receive_event(agent, payload)
        if payload['type'] == 'game_end_notification':
            mid = agent['match_id']
            if not self.store.one(db.results, match_id=mid):
                with self.store.transaction() as c:
                    c.execute(db.results.insert().values(match_id=mid, body={
                        'source': 'external_env_notification', 'rated': False, 'notification': payload}))
                    c.execute(db.matches.update().where(db.matches.c.id == mid).values(status='finished'))
                self.emit(mid, 'game_finished', {'match_id': mid, 'notification': payload})

    async def watch(self):
        # Reopen the known Agents' connections after a gateway restart so turn
        # notifications don't depend on the model first making a tool call.
        while True:
            for agent in self.store.all(db.agents, registered=True):
                if self.store.one(db.matches, id=agent['match_id'])['status'] != 'running':
                    continue
                try:
                    # Healthy idle sockets need no application-level query.
                    # Reconnects still verify identity; real calls also verify
                    # because the ENV can reset while the HUB socket stays open.
                    await self.workers.client(agent, verify=False)
                except RuntimeError as exc:
                    self.store.update(db.matches, {'id': agent['match_id']}, status='aborted')
                    self.emit(agent['match_id'], 'match_aborted', {'reason': str(exc)})
                except Exception:
                    # A temporary HUB outage does not erase ownership or reset a turn.
                    pass
            await asyncio.sleep(1)
