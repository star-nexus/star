#!/usr/bin/env python3
"""Sequential, exact-SHA E8 diagnostic or instrumentation-off gate runner."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e7ba18b31870577110b591104ef8fa7b4713e43c'
SCENARIO = 'chibi-144k-scale-10000'
MAP_SHA = 'e5bacb41c499fdfb9e91a917a1427515f2be1dae5ca4961692e921c05b816d25'


def run(args):
    sha = subprocess.check_output(['git','rev-parse',args.sha], cwd=ROOT,text=True).strip()
    tooling = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tracked = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
    if tracked.strip():
        raise RuntimeError('commit tracked changes before measurement')
    scenario = ROOT/'rotk_env/maps'/f'{SCENARIO}.json'
    assert hashlib.sha256(scenario.read_bytes()).hexdigest() == MAP_SHA
    run_id = datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + args.label
    output = ROOT/'results/phase5-e8'/run_id
    output.mkdir(parents=True)
    env_extra = {'STAR_SCALE_MINIMAP_UNITS':'off', 'STAR_E8_MODE':args.mode,
                 'STAR_E8_RUNTIME_SHA':sha, 'STAR_E8_WINDOW':str(args.window)}
    manifest = dict(runtime_sha=sha, tooling_sha=tooling, args=vars(args), environment=env_extra,
                    scenario_sha256=MAP_SHA, commands=[], run_id=run_id,
                    uname=list(os.uname()), started_at=datetime.datetime.now().isoformat())
    manifest['hardware'] = subprocess.check_output(['system_profiler','SPHardwareDataType'],text=True).split('Serial Number')[0]
    manifest_path = output/'manifest.json'
    def save():
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    save()
    print(f'OUTPUT={output}',flush=True)
    with tempfile.TemporaryDirectory(prefix='star-e8-') as temp:
        wt = Path(temp)/'runtime'
        subprocess.run(['git','worktree','add','--detach',str(wt),sha],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        try:
            shutil.copy2(scenario,wt/'rotk_env/maps'/scenario.name)
            shutil.copy2(ROOT/'tools/phase5_e8_snapshot.py',wt/'tools/phase5_e8_snapshot.py')
            # uv's shared cache provides the same locked runtime to every worktree.
            subprocess.run(['uv','run','--frozen','python','-c','import pygame, rotk_env.main'],cwd=wt,check=True,stdout=subprocess.DEVNULL)
            for repeat in range(1,args.repeats+1):
                point = output/f'repeat-{repeat}'
                point.mkdir()
                sock = f'/tmp/star-e8-{os.getpid()}-{repeat}.sock'
                command = ['uv','run','--frozen','python','tools/phase5_e8_snapshot.py',
                           '--skip-start','--mode','real_time','--scenario',SCENARIO,
                           '--players','human_vs_two_ai','--no-hub','--seed','42',
                           '--uncapped','--scale-harness-socket',sock]
                driver = ['uv','run','--frozen','python','tools/scale_driver.py',
                          '--socket',sock,'--command-timeout','120','density-point',
                          '--density',str(args.density),'--phase','staggered','--seed','42',
                          '--phase-seed',str(args.phase_seed),'--route-steps','12',
                          '--duration',str(args.window+15),'--warmup','5',
                          '--sample-after',str(args.window+10),'--ready-timeout','120',
                          '--gc-policy','realtime_defer','--profile',str(point/'profile.json'),
                          '--output',str(point/'point.json')]
                manifest['commands'].append(dict(repeat=repeat,cwd=str(wt),env=command,driver=driver))
                save()
                print(f'START repeat={repeat} mode={args.mode} sha={sha[:12]}',flush=True)
                with (point/'env.log').open('w') as log:
                    proc = subprocess.Popen(command,cwd=wt,env=dict(os.environ,**env_extra),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:
                        with (point/'driver.log').open('w') as driver_log:
                            result = subprocess.run(driver,cwd=wt,stdout=driver_log,stderr=subprocess.STDOUT,timeout=args.window+260)
                        if result.returncode:
                            raise RuntimeError(f'driver failed: {point}/driver.log')
                    finally:
                        if proc.poll() is None:
                            os.killpg(proc.pid,signal.SIGTERM)
                            try: proc.wait(timeout=8)
                            except subprocess.TimeoutExpired:
                                os.killpg(proc.pid,signal.SIGKILL)
                                proc.wait()
                        Path(sock).unlink(missing_ok=True)
                data = json.loads((point/'profile.json').read_text())
                guard_data = json.loads((point/'point.json').read_text())
                guards = dict(guard_data['guards'])
                guards.update(resident_10000=guard_data['status']['living_units']==10000,
                    e8_window_full=data['window_coverage_s']>=args.window-.2,
                    minimap_off=data['frame_metrics']['minimap_unit_layer_enabled']['max']==0,
                    runtime_matches=data['metadata']['e8_runtime_sha']==sha,
                    mode_matches=data['metadata']['e8_mode']==args.mode,
                    aligned=data['sample_count']==data['e8_aligned']['sample_count'])
                (point/'guards.json').write_text(json.dumps(guards,indent=2)+'\n')
                if not all(guards.values()):
                    raise RuntimeError(f'failed guards: {guards}')
                print(f'DONE repeat={repeat} n={data["sample_count"]} controlled={data["controlled_work_frame_ms"]}',flush=True)
                time.sleep(3)
        finally:
            subprocess.run(['git','worktree','remove','--force',str(wt)],cwd=ROOT,check=True)
    sums=[]
    for path in sorted(output.rglob('*')):
        if path.is_file(): sums.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output)}')
    (output/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(f'COMPLETE={output}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--sha',default=BASE)
    p.add_argument('--mode',choices=['off','volume','ui'],default='volume')
    p.add_argument('--window',type=float,default=30)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--density',type=float,default=1)
    p.add_argument('--phase-seed',type=int,default=42)
    p.add_argument('--label',default='volume')
    run(p.parse_args())
