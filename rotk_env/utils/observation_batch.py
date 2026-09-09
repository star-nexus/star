"""Private, synchronous observation scratch space; never survives a read batch."""
from collections import Counter, defaultdict

from ..components import ActionPoints, Unit, UnitCount


class ObservationBatchContext:
    def __init__(self, handler, reuse=True):
        self.handler = handler
        self.world = handler.world
        self.reuse = reuse
        self.revision = self.world.revision
        self.invalidated = False
        self.metrics = Counter()
        self._cache = defaultdict(dict)
        self._components = defaultdict(dict)

    def memo(self, kind, key, build):
        cache = self._cache[kind]
        if self.reuse and key in cache:
            self.metrics[kind + '_hits'] += 1
            return cache[key]
        self.metrics[kind + '_builds'] += 1
        value = build()
        if self.reuse:
            cache[key] = value
        return value

    def component(self, uid, kind):
        cache = self._components[kind]
        if uid not in cache:
            cache[uid] = self.world.get_component(uid, kind)
        return cache[uid]

    def census(self):
        def build():
            totals, living = defaultdict(int), defaultdict(int)
            alive = defaultdict(list)
            units, counts = self._components[Unit], self._components[UnitCount]
            get_component = self.world.get_component
            for uid in self.world.query().with_component(Unit).entities():
                unit = units[uid] = get_component(uid, Unit)
                count = counts[uid] = get_component(uid, UnitCount)
                totals[unit.faction] += 1
                if count is None or count.current_count <= 0:
                    continue
                living[unit.faction] += 1
                alive[unit.faction].append(uid)
            return totals, living, alive
        return self.memo('census', None, build)

    def actionable(self, faction, alive_units):
        def build():
            return sum(bool(ap and ap.current_ap > 0)
                       for ap in (self.component(uid, ActionPoints) for uid in alive_units))
        return self.memo('actionable', faction, build)

    def close(self):
        self._cache.clear()
        self._components.clear()
        self.invalidated = True
