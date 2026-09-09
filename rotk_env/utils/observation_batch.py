"""Private, synchronous observation scratch space; never survives a read batch."""
from collections import Counter, defaultdict

from ..components import ActionPoints, HexPosition, Unit, UnitCount


class ObservationBatchContext:
    def __init__(self, handler, reuse=True):
        self.handler = handler
        self.world = handler.world
        self.reuse = reuse
        self.revision = self.world.revision
        self.invalidated = False
        self.metrics = Counter()
        self._cache = {}
        self._components = {}
        self._rows = None

    def memo(self, kind, key, build):
        cache_key = kind, key
        if self.reuse and cache_key in self._cache:
            self.metrics[kind + '_hits'] += 1
            return self._cache[cache_key]
        self.metrics[kind + '_builds'] += 1
        value = build()
        if self.reuse:
            self._cache[cache_key] = value
        return value

    def component(self, uid, kind):
        key = uid, kind
        if key not in self._components:
            self._components[key] = self.world.get_component(uid, kind)
        return self._components[key]

    def census(self):
        def build():
            totals, living, actionable = Counter(), Counter(), Counter()
            alive = defaultdict(list)
            rows = []
            for uid in self.world.query().with_component(Unit).entities():
                unit = self.component(uid, Unit)
                count = self.component(uid, UnitCount)
                position = self.component(uid, HexPosition)
                rows.append((uid, unit, count, position))
                totals[unit.faction] += 1
                if count is None or count.current_count <= 0:
                    continue
                living[unit.faction] += 1
                alive[unit.faction].append(uid)
                ap = self.component(uid, ActionPoints)
                actionable[unit.faction] += bool(ap and ap.current_ap > 0)
            self._rows = rows
            return totals, living, actionable, alive
        return self.memo('census', None, build)

    def unit_rows(self):
        if self._rows is None:
            self.census()
        return self._rows

    def close(self):
        self._cache.clear()
        self._components.clear()
        self._rows = None
        self.invalidated = True
