"""Bounded experiment-only recorder of already-completed profiler frame samples.

Keeps the production rolling horizon/capacity and slow-frame detection unchanged.
No new section timers or subsystem monkeypatches. JSON is emitted at snapshot only.
"""
from collections import deque


def install_trace(profiler_class, capacity=20000):
    finish = profiler_class._finish_frame_at
    reset = profiler_class.reset

    def trace_reset(self):
        result = reset(self)
        self._e8_trace = deque(maxlen=capacity)
        self._e8_trace_dropped = 0
        return result

    def trace_finish(self, end_ns):
        previous = self._frame_index
        result = finish(self, end_ns)
        if self._frame_index == previous:
            return result
        if not hasattr(self, '_e8_trace'):
            self._e8_trace = deque(maxlen=capacity)
            self._e8_trace_dropped = 0
        if len(self._e8_trace) == capacity:
            self._e8_trace_dropped += 1
        self._e8_trace.append({
            'frame_index': self._frame_index,
            'start_ns': self.frame_start_ns[-1],
            'end_ns': self.frame_end_ns[-1],
            'controlled_ns': self.frame_controlled_ns[-1],
            'frame_ns': self.frame_times_ns[-1],
            'self_ns': {k:v[-1] for k,v in self.section_self_ns.items()},
            'inclusive_ns': {k:v[-1] for k,v in self.section_inclusive_ns.items()},
            'metrics': {k:v[-1] for k,v in self.frame_metric_samples.items()},
        })
        return result

    profiler_class.reset = trace_reset
    profiler_class._finish_frame_at = trace_finish
    def restore():
        profiler_class.reset = reset
        profiler_class._finish_frame_at = finish
    return restore


def export_trace(profiler):
    return {'schema':'phase5-e8-completed-frame-trace-v1',
            'capacity':getattr(profiler,'_e8_trace',deque(maxlen=20000)).maxlen,
            'dropped':getattr(profiler,'_e8_trace_dropped',0),
            'frames':list(getattr(profiler,'_e8_trace',()))}
