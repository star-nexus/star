#!/usr/bin/env python3
"""Archive complete E8 evidence in the local STAR Lab case, with SHA256 coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
LAB=Path('/Users/liyang/Developer/star-lab/experiments/2026-09-10k-e8-volume')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('run_dirs',nargs='+',type=Path)
    args=p.parse_args()
    (LAB/'results').mkdir(parents=True,exist_ok=True)
    (LAB/'artifacts').mkdir(exist_ok=True)
    for run in args.run_dirs:
        run=run.resolve()
        raw=LAB/'artifacts'/f'{run.name}-raw.zip'
        compact=[]
        with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(run.rglob('*')):
                if f.is_file() and f.name!='SHA256SUMS': z.write(f,str(f.relative_to(run)))
        for f in sorted(run.glob('repeat-*/profile.json')):
            d=json.loads(f.read_text())
            point=json.loads((f.parent/'point.json').read_text())
            compact.append(dict(repeat=f.parent.name,samples=d['sample_count'],
              controlled=d['controlled_work_frame_ms'],frame_p99=d['p99_frame_ms'],
              window_s=d['window_coverage_s'],metrics=d['frame_metrics'],sections=d['sections'],
              guards=json.loads((f.parent/'guards.json').read_text()),
              point={k:v for k,v in point.items() if k!='profile'},
              profile_sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
        (LAB/'results'/f'{run.name}-compact.json').write_text(json.dumps(dict(
            manifest=json.loads((run/'manifest.json').read_text()),repeats=compact,
            analyses={f.name:json.loads(f.read_text()) for f in run.glob('*analysis.json')},
            raw_path=f'artifacts/{raw.name}',raw_size_bytes=raw.stat().st_size,
            raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest()),indent=2)+'\n')
    fixture=ROOT/'rotk_env/maps/chibi-144k-scale-10000.json'
    fixture_zip=LAB/'artifacts/scenario.zip'
    if not fixture_zip.exists():
        with zipfile.ZipFile(fixture_zip,'w',zipfile.ZIP_DEFLATED) as z: z.write(fixture,fixture.name)
    sums=[]
    for directory in ('results','artifacts'):
        for f in sorted((LAB/directory).glob('*')):
            if f.is_file() and f.name!='SHA256SUMS':
                sums.append(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(LAB)}')
    (LAB/'artifacts/SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(LAB)


if __name__=='__main__': main()
