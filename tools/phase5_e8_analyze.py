#!/usr/bin/env python3
"""Analyze complete E8 sequences; volume associations are not causal proof."""
import argparse
import json
from pathlib import Path
import numpy as np


def corr(x,y):
    x,y=np.asarray(x,dtype=float),np.asarray(y,dtype=float)
    valid=np.isfinite(x)&np.isfinite(y)
    x,y=x[valid],y[valid]
    if len(x)<3 or np.ptp(x)==0 or np.ptp(y)==0: return None
    return float(np.corrcoef(x,y)[0,1])


def describe(x):
    x=np.asarray(x,dtype=float)
    return {k:float(v) for k,v in zip(('avg','p50','p95','p99','max'),
                [np.mean(x),*np.percentile(x,[50,95,99]),np.max(x)])}


def analyze(profile):
    data=profile['e8_aligned']
    y=np.array(data['controlled_ns'])/1e6
    n=len(y)
    lo,hi,cut=np.percentile(y,[25,75,95])
    ref=(y>=lo)&(y<=hi)
    tail=y>=cut
    out={'samples':n,'controlled_ms':describe(y),'frame_ms':describe(np.array(data['frame_ns'])/1e6),
         'breach_rate':float(np.mean(y>33.33)), 'tail_count':int(tail.sum()),'metrics':{},'sections':{}}
    longest=run=0
    for b in y>33.33:
        run=run+1 if b else 0
        longest=max(run,longest)
    out['longest_breach_run']=longest
    def conditional(x):
        return dict(reference=float(x[ref].mean()),tail=float(x[tail].mean()),
                    uplift=float(x[tail].mean()-x[ref].mean()),r=corr(x,y))
    for k,v in data['metrics'].items():
        if not (k.startswith('e8_') or k in ['render_commands','vision_dirty_units','effect_position_index_changes']): continue
        if any(x is None or not isinstance(x,(int,float)) for x in v): continue
        x=np.array(v,dtype=float)
        out['metrics'][k]=dict(**conditional(x),min=float(x.min()),max=float(x.max()),
                              first_quarter=float(x[:n//4].mean()),last_quarter=float(x[-n//4:].mean()),
                              r_first_difference=corr(np.diff(x),np.diff(y)))
    for k,v in data['inclusive_ns'].items():
        if k.startswith('e8_') or k in ['AnimationSystem','UnitRenderSystem','VisionSystem','unit_visible_cull']:
            x=np.array(v)/1e6
            out['sections'][k]=dict(**describe(x),**conditional(x))
    m=data['metrics']
    if 'e8_visible_units' in m:
        arr=lambda k:np.array(m[k],dtype=float)
        out['count_checks']={
          'visible_partition':bool(np.all(arr('e8_visible_units')==arr('e8_animated_units')+arr('e8_static_units'))),
          'command_partition':bool(np.all(arr('e8_unit_commands')==arr('e8_animated_commands')+arr('e8_static_commands'))),
          'one_command_per_animated':bool(np.all(arr('e8_animated_commands')==arr('e8_animated_units'))),
        }
        dt=arr('e8_dt_ms')/1000
        commits=arr('e8_movement_commits')
        out['commit_dt']={'r':corr(dt,commits),'rate_per_sim_s':float(commits.sum()/dt.sum()),
                         'rate_frame_normalized':conditional(commits/dt)}
        out['lag_prior_frame_to_commits']={str(lag):corr(y[:-lag],commits[lag:]) for lag in (1,2,3)}
        out['lag_prior_full_frame_to_dt']=corr(np.array(data['frame_ns'][:-1])/1e6,arr('e8_dt_ms')[1:])
        out['cpu_wall']={name:{'cpu_ms':describe(arr(f'e8_{name}_cpu_ms')),
                              'wall_minus_cpu_ms':describe(arr(f'e8_{name}_wall_ms')-arr(f'e8_{name}_cpu_ms'))}
                         for name in ['unit','animation','vision']}
        out['volume_models']={}
        for section,predictor in [('e8_unit_classify','e8_visible_units'),('e8_unit_animated_draw','e8_animated_units'),('UnitRenderSystem','e8_visible_units')]:
            x=arr(predictor)
            target=np.array(data['inclusive_ns'][section])/1e6
            design=np.column_stack([np.ones(n),x])
            beta=np.linalg.lstsq(design,target,rcond=None)[0]
            residual=target-design@beta
            out['volume_models'][section]={'predictor':predictor,'intercept_ms':float(beta[0]),
              'ms_per_object':float(beta[1]),'r2':float(1-np.var(residual)/np.var(target)),
              'residual_tail_uplift':float(residual[tail].mean()-residual[ref].mean())}
    out['worst_frames']=[dict(index=int(i),ms=float(y[i]),metrics={k:v[i] for k,v in m.items() if k.startswith('e8_')},
                        self_ms={k:round(v[i]/1e6,5) for k,v in data['self_ns'].items() if v[i]>200000})
                         for i in np.argsort(y)[-5:][::-1]]
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('run_dir',type=Path)
    args=p.parse_args()
    results=[]
    for file in sorted(args.run_dir.glob('repeat-*/profile.json')):
        result=analyze(json.loads(file.read_text()))
        result['repeat']=file.parent.name
        results.append(result)
        print(result['repeat'],result['controlled_ms'])
        for k in ['e8_visible_units','e8_animated_units','e8_static_units','e8_static_groups','e8_unit_commands','e8_dt_ms','e8_movement_commits']:
            if k in result['metrics']: print(k,result['metrics'][k])
        print('sections',result['sections'])
        print('models',result.get('volume_models'))
        print('dt',result.get('commit_dt'))
    (args.run_dir/'analysis.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
