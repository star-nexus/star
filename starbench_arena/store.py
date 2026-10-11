"""Durable application identities, operations, events and ordered settlements."""
from contextlib import contextmanager
from sqlalchemy import JSON, Column, Float, Integer, MetaData, String, Table, UniqueConstraint, create_engine, select
from sqlalchemy.pool import StaticPool

metadata = MetaData()
entries = Table('arena_entries', metadata,
    Column('id', String, primary_key=True), Column('owner', String, nullable=False),
    Column('name', String, nullable=False), Column('version', String, nullable=False),
    Column('details', JSON, nullable=False), UniqueConstraint('owner', 'name', 'version'))
matches = Table('arena_matches', metadata,
    Column('id', String, primary_key=True), Column('mode', String, nullable=False),
    Column('kind', String, nullable=False), Column('status', String, nullable=False),
    Column('season', String, nullable=False), Column('created', Float, nullable=False),
    Column('prepared', Float), Column('started', Float), Column('seed', Integer, nullable=False),
    Column('scenario', String, nullable=False), Column('players', JSON, nullable=False),
    Column('worker', JSON), Column('rules', JSON, nullable=False))
agents = Table('arena_agents', metadata,
    Column('id', String, primary_key=True), Column('match_id', String, nullable=False),
    Column('owner', String, nullable=False), Column('faction', String, nullable=False),
    Column('name', String, nullable=False), Column('generation', Integer, nullable=False, default=0),
    UniqueConstraint('match_id', 'owner', 'name'))
operations = Table('arena_operations', metadata,
    Column('agent_id', String, primary_key=True), Column('id', String, primary_key=True),
    Column('fingerprint', String, nullable=False), Column('state', String, nullable=False),
    Column('result', JSON), Column('received', Float, nullable=False), Column('completed', Float))
events = Table('arena_events', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True), Column('match_id', String, nullable=False),
    Column('owner', String), Column('kind', String, nullable=False), Column('body', JSON, nullable=False),
    Column('created', Float, nullable=False))
results = Table('arena_results', metadata,
    Column('sequence', Integer, primary_key=True, autoincrement=True),
    Column('match_id', String, nullable=False, unique=True), Column('body', JSON, nullable=False))
usage = Table('arena_usage', metadata,
    Column('agent_id', String, primary_key=True), Column('body', JSON, nullable=False))
subscriptions = Table('arena_subscriptions', metadata,
    Column('id', String, primary_key=True), Column('owner', String, nullable=False),
    Column('match_id', String, nullable=False), Column('event', String, nullable=False),
    Column('url', String, nullable=False), Column('secret', String, nullable=False),
    Column('cursor', Integer, nullable=False, default=0))

class Store:
    def __init__(self, url):
        kw = {'pool_pre_ping': True}
        if url.startswith('sqlite'):
            kw['connect_args'] = {'check_same_thread': False}
            if ':memory:' in url:
                kw['poolclass'] = StaticPool
        self.engine = create_engine(url, **kw)

    def initialize(self):
        metadata.create_all(self.engine)

    @contextmanager
    def transaction(self):
        with self.engine.begin() as connection:
            yield connection

    def one(self, table, **where):
        with self.engine.connect() as c:
            return c.execute(select(table).filter_by(**where)).mappings().first()

    def all(self, table, **where):
        with self.engine.connect() as c:
            return list(c.execute(select(table).filter_by(**where)).mappings())

    def insert(self, table, **values):
        with self.transaction() as c:
            c.execute(table.insert().values(**values))

    def update(self, table, where, **values):
        with self.transaction() as c:
            c.execute(table.update().filter_by(**where).values(**values))
