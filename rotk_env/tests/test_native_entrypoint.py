"""Formal ENV defaults, provenance readiness and backend-specific dependency scope."""
import inspect
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
import auto_test
from rotk_env.main import parse_arguments


def test_formal_defaults_and_explicit_python(monkeypatch):
    monkeypatch.setattr('sys.argv',['star'])
    args=parse_arguments()
    assert (args.backend,args.native_threads,args.native_scheduling)==('rust',1,'threaded')
    assert inspect.signature(auto_test.run_match).parameters['backend'].default=='rust'
    monkeypatch.setattr('sys.argv',['star','--backend','python','--no-hub','--mock-ai'])
    assert parse_arguments().backend=='python'


def test_batch_passes_backend_and_native_configuration(monkeypatch,tmp_path):
    match=tmp_path/'matches';match.write_text('fixture-a,fixture-b\n')
    received=[]
    monkeypatch.setattr(auto_test,'run_match',lambda *args,**kwargs:received.append(kwargs))
    monkeypatch.setattr('sys.argv',['batch','--list',str(match),'--native-threads','4','--native-scheduling','serial'])
    auto_test.main()
    assert received and received[0]['backend']=='rust'
    assert received[0]['native_threads']==4 and received[0]['native_scheduling']=='serial'

@pytest.mark.parametrize('ready,expected',[
    ({'backend':'rust','hub_connected':True},True),
    ({'backend':'rust','hub_connected':False},False),
    ({'backend':'python','hub_connected':True},False),
    (None,False)])
def test_launcher_requires_confirmed_world_and_hub(ready,expected,monkeypatch,tmp_path):
    log=tmp_path/'env.log'
    log.write_text('LLMSystem connected\nGame started!\n'+('STAR_ENV_READY '+json.dumps(ready)+'\n' if ready else ''))
    clock=iter([0,0,2]);monkeypatch.setattr(auto_test.time,'time',lambda:next(clock))
    monkeypatch.setattr(auto_test.time,'sleep',lambda t:None)
    assert auto_test._wait_for_env_ready(str(log),SimpleNamespace(poll=lambda:None),timeout=1) is expected

@pytest.mark.parametrize('script',['run_env.sh','run_headless_env.sh'])
@pytest.mark.parametrize('args,uses_native',[([],True),(['--backend','python'],False),(['--backend=python'],False),(['--backend','rust','--native-threads','4'],True)])
def test_shell_launchers_load_native_only_for_env(script,args,uses_native,tmp_path):
    executable=tmp_path/'uv';executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');executable.chmod(0o755)
    import os
    root=Path(__file__).resolve().parents[2]
    result=subprocess.check_output(['bash',str(root/script),*args],env={**os.environ,'PATH':str(tmp_path)+':'+os.environ['PATH']},text=True).splitlines()
    assert ('native' in result) is uses_native
    assert '--backend' not in result or result[-len(args):]==args
    assert '--headless' in result if script=='run_headless_env.sh' else '--headless' not in result
