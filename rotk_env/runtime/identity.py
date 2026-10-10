"""ENV provenance outside the wire protocol and authoritative state."""
import hashlib
import json
from pathlib import Path
import subprocess


def runtime_identity(backend, *, env_id, mode, scenario, seed, scheduling, threads):
    from .bootstrap import ORACLE_VERSION, NATIVE_API_VERSION
    from ..ui.context import VISUAL_VERSION
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        try:
            return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    result = dict(backend=backend, env_id=env_id, source_sha=git('rev-parse', 'HEAD'),
                  oracle=ORACLE_VERSION, mode=mode, scenario=scenario, seed=seed,
                  native_scheduling=scheduling if backend == 'rust' else None,
                  native_threads=threads if backend == 'rust' else None,
                  visual_version=VISUAL_VERSION)
    if backend == 'rust':
        from star_native import _native
        result.update(native_api=NATIVE_API_VERSION, native_schema=5,
                      extension_sha256=hashlib.sha256(Path(_native.__file__).read_bytes()).hexdigest())
    return result


def announce_ready(identity, *, hub_connected, manifest=None):
    record = dict(identity, hub_connected=bool(hub_connected))
    if manifest is not None:
        path = Path(manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    print('STAR_ENV_READY '+json.dumps(record, ensure_ascii=False), flush=True)
