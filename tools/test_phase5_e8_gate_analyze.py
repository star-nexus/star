from copy import deepcopy
from tools.phase5_e8_gate_analyze import analyze


def fixture():
    metrics={'scale_configured_moving_units':10000,'scale_execution_density':1,
             'scale_gc_automatic_enabled':0,'scale_gc_defer_active':1,
             'scale_gc_policy':'realtime_defer','fog_enabled':1,
             'minimap_unit_layer_enabled':0,'input_key_down':0,
             'input_mouse_button':0,'input_mouse_wheel':0,
             'effect_position_index_changes':600,'vision_dirty_units':600}
    frames=[{'frame_index':i+1,'start_ns':i*33333334,'end_ns':(i+1)*33333334,
             'controlled_ns':30000000,'frame_ns':32000000,'metrics':dict(metrics)}
            for i in range(2100)]
    return {'e8_trace':{'frames':frames,'dropped':0},
            'metadata':{'e8_mode':'off','e8_runtime_sha':'test','window':'test'},
            'window_target_s':5,'window_sample_capacity':4096}


def test_gate_uses_all_admitted_frames_and_checks_full_trace_guards():
    d=fixture()
    result=analyze(d)
    assert result['pass']
    assert result['samples']==1800
    assert result['all_30s_blocks_pass']
    # Early startup is excluded by time, not by how slow it was.
    for f in d['e8_trace']['frames'][:300]: f['controlled_ns']=90000000
    assert analyze(d)['pass']
    # Two percent of admitted samples cannot be hidden by a good final window.
    for f in d['e8_trace']['frames'][400:450]: f['controlled_ns']=40000000
    result=analyze(d)
    assert not result['pass']
    assert result['longest_breach_run']==50
    d=fixture()
    d['e8_trace']['frames'][600]['metrics']['fog_enabled']=0
    assert not analyze(d)['pass']
    d=fixture(); d['e8_trace']['dropped']=1
    assert not analyze(d)['pass']
