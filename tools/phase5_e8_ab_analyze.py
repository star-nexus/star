#!/usr/bin/env python3
"""Decision-grade local metrics for E8 interleaved runs; no causal gate fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def analyze(profile):
    aligned = profile['e8_aligned']
    commands = np.asarray(aligned['metrics']['render_commands'], dtype=float)
    inclusive = aligned['inclusive_ns']
    unit_ms = np.asarray(inclusive['UnitRenderSystem']) / 1e6
    design = np.column_stack([np.ones(len(commands)), commands])
    beta = np.linalg.lstsq(design, unit_ms, rcond=None)[0]
    residual = unit_ms - design @ beta
    coverage = (aligned['frame_end_ns'][-1] - aligned['frame_start_ns'][0]) / 1e9
    return {
        'controlled_ms': profile['controlled_work_frame_ms'],
        'samples': len(commands), 'coverage_s': coverage,
        'inclusive_avg_ms': {k:float(np.mean(v)/1e6) for k,v in inclusive.items()},
        'commands': {'min':float(commands.min()), 'max':float(commands.max()),
                     'avg':float(commands.mean())},
        'unit_command_model': {
            'method':'per-run ordinary least squares, inclusive time ~ 1 + render_commands',
            'intercept_ms':float(beta[0]), 'ms_per_command':float(beta[1]),
            'r2':float(1-np.var(residual)/np.var(unit_ms)),
            'at_3450_commands_ms':float(beta @ [1,3450]),
            'reference_in_observed_range':bool(commands.min() <=3450<=commands.max()),
            'interpretation':'descriptive matched-volume estimate; not randomized unit-level causality'},
        'rates_per_wall_s': {k:sum(aligned['metrics'][k])/coverage for k in
                            ('effect_position_index_changes','vision_dirty_units')},
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('run_dirs',nargs='+',type=Path)
    args=p.parse_args()
    for run in args.run_dirs:
        out=[]
        for file in sorted(run.glob('repeat-*/profile.json')):
            value=analyze(json.loads(file.read_text()))
            value.update(repeat=file.parent.name,
                         profile_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            out.append(value)
        if not out: raise ValueError(f'No profiles: {run}')
        (run/'ab-analysis.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
        print(run.name,[(r['controlled_ms']['p99'],r['unit_command_model']['at_3450_commands_ms']) for r in out])


if __name__=='__main__': main()
