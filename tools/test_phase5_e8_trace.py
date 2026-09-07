import performance_profiler as perf
from tools.phase5_e8_trace import install_trace, export_trace


def test_trace_keeps_completed_frames_past_rolling_prune_and_clears_on_reset():
    restore=install_trace(perf.PerformanceProfiler,capacity=4)
    try:
        p=perf.PerformanceProfiler(sample_window=10,sample_window_seconds=.05)
        p.enabled=True
        for i in range(5):
            p.start_frame()
            p.set_frame_metric('sequence',i)
            p.end_frame()
        trace=export_trace(p)
        assert trace['dropped']==1
        assert [x['metrics']['sequence'] for x in trace['frames']]==[1,2,3,4]
        # Production samples/timings remain separate and unchanged.
        assert len(p.frame_controlled_ns)==5
        assert trace['frames'][-1]['controlled_ns']==p.frame_controlled_ns[-1]
        p.reset()
        assert export_trace(p)['frames']==[]
        assert export_trace(p)['dropped']==0
    finally: restore()
