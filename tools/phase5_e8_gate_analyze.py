#!/usr/bin/env python3
"""Full admitted-trace gate; fixed startup exclusion, no slow-frame filtering."""
import argparse
import json
from pathlib import Path
import numpy as np


def stats(values):
    return {k:float(v) for k,v in zip(('avg','p95','p99','max'),
             [np.mean(values),*np.percentile(values,[95,99]),np.max(values)])}


def analyze(profile, warmup=10, required_seconds=60):
    trace=profile['e8_trace']
    frames=trace['frames']
    if not frames: raise ValueError('empty trace')
    origin=frames[0]['start_ns']
    frames=[f for f in frames if f['start_ns']>=origin+warmup*1e9]
    if not frames: raise ValueError('no frames after warmup')
    start=frames[0]['start_ns']
    coverage=(frames[-1]['end_ns']-start)/1e9
    t=np.array([(f['start_ns']-start)/1e9 for f in frames])
    controlled=np.array([f['controlled_ns']/1e6 for f in frames])
    body=np.array([f['frame_ns']/1e6 for f in frames])
    guards={
        'trace_not_truncated': trace['dropped']==0,
        'coverage_complete':coverage>=required_seconds-.15,
        'diagnostic_instrumentation_off':profile['metadata']['e8_mode']=='off',
        'production_profiler_window_5s':profile['window_target_s']==5,
        'production_profiler_capacity_4096':profile['window_sample_capacity']==4096,
        'contiguous_frame_ids':all(b['frame_index']==a['frame_index']+1 for a,b in zip(frames,frames[1:])),
    }
    expected={'scale_configured_moving_units':10000,'scale_execution_density':1,
              'scale_gc_automatic_enabled':0,'scale_gc_defer_active':1,
              'scale_gc_policy':'realtime_defer','fog_enabled':1,
              'minimap_unit_layer_enabled':0,'input_key_down':0,
              'input_mouse_button':0,'input_mouse_wheel':0}
    for key,value in expected.items():
        guards[key]=all(f['metrics'].get(key)==value for f in frames)
    blocks=[]
    for offset in range(0,int(coverage),30):
        mask=(t>=offset)&(t<offset+30)
        if min(coverage-offset,30)<29.5: continue
        blocks.append(dict(start_s=offset,samples=int(mask.sum()),**stats(controlled[mask])))
    longest=run=0
    for breach in controlled>33.33:
        run=run+1 if breach else 0
        longest=max(longest,run)
    # Descriptive moving-block bootstrap; dependence length is an assumption.
    # It supplements repeated/chronological checks and is never used to drop data.
    rng=np.random.default_rng(42)
    bootstrap=[]
    chunks=[controlled[(t>=s)&(t<s+12)] for s in range(0,int(coverage),12)]
    for _ in range(300):
        indices=rng.integers(0,len(chunks),size=len(chunks))
        sample=np.concatenate([chunks[i] for i in indices])
        bootstrap.append(np.percentile(sample,99))
    out={'samples':len(frames),'warmup_excluded_s':warmup,'coverage_s':coverage,
         'controlled_ms':stats(controlled),'frame_body_ms':stats(body),
         'breach_count':int(np.sum(controlled>33.33)),
         'breach_rate':float(np.mean(controlled>33.33)),
         'longest_breach_run':longest,'chronological_30s_blocks':blocks,
         'all_30s_blocks_pass':all(b['p99']<=33.33 for b in blocks),
         'p99_bootstrap_95pct_ms':np.percentile(bootstrap,[2.5,97.5]).tolist(),
         'bootstrap_assumption':'12-second blocks, 300 resamples, seed 42; descriptive only',
         'guards':guards,'pass':all(guards.values()) and float(np.percentile(controlled,99))<=33.33,
         'position_changes_per_s':sum(f['metrics'].get('effect_position_index_changes',0) for f in frames)/coverage,
         'vision_dirty_per_s':sum(f['metrics'].get('vision_dirty_units',0) for f in frames)/coverage,
         'window':profile['metadata'].get('window'),
         'runtime_sha':profile['metadata']['e8_runtime_sha']}
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('run_dir',type=Path)
    p.add_argument('--seconds',type=float,default=60)
    args=p.parse_args()
    results=[]
    for file in sorted(args.run_dir.glob('repeat-*/profile.json')):
        result=analyze(json.loads(file.read_text()),required_seconds=args.seconds)
        result['repeat']=file.parent.name
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k not in ['guards','chronological_30s_blocks']},ensure_ascii=False))
    (args.run_dir/'gate-analysis.json').write_text(json.dumps(results,indent=2)+'\n')
    if not results or not all(r['pass'] for r in results): raise SystemExit(1)


if __name__=='__main__': main()
