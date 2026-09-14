"""Trusted human controls over a native world and an independent display World.

The caller owns scene lifecycle and supplies the original scene capabilities.
Commands publish a fresh display delta before returning, including after errors
that may follow a partial write. No Protocol identity or synthetic Agent is used.
"""


class LocalControls:
    def __init__(self, runtime, presentation, initial_state, *, on_events=None):
        self.runtime = runtime
        self.presentation = presentation
        self.systems = frozenset(initial_state["systems"])
        self.interface = dict(initial_state["interface"])
        self.on_events = on_events

    def refresh(self):
        events = self.presentation.apply(self.runtime.take_presentation_delta())
        if self.on_events is not None and events:
            self.on_events(events)
        return events

    def _call(self, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        finally:
            self.refresh()

    def execute(self, kind, **parameters):
        required = {"move": "movement_system", "attack": "combat_system"}.get(kind)
        if required and not self.interface.get(required):
            return None
        if kind == "fortify" and "TerritorySystem" not in self.systems:
            return None
        return self._call(self.runtime.execute_control, kind, **parameters)

    def finish_turn(self):
        if "TurnSystem" in self.systems:
            self._call(self.runtime.finish_human_turn)

    def start_capture(self, unit_id, position):
        if "TerritorySystem" in self.systems:
            return self._call(self.runtime.start_capture, unit_id, position)
        return None
