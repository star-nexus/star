"""The public launcher preserves ENV configuration and process exit behaviour."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import starbench


def test_help_needs_no_env_dependencies_or_uv(monkeypatch, capsys):
    monkeypatch.setattr(starbench.shutil, "which", lambda _: pytest.fail("uv lookup"))
    with pytest.raises(SystemExit) as result:
        starbench.main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "--no-hub" in help_text and "no Hub or API key needed" in help_text
    assert "--extra" not in help_text


@pytest.mark.parametrize("args", [["--backend", "unknown"], ["--backend"]])
def test_invalid_backend_rejected_before_dependency_work(args, monkeypatch):
    monkeypatch.setattr(starbench.shutil, "which", lambda _: pytest.fail("uv lookup"))
    with pytest.raises(SystemExit) as result:
        starbench.main(args)
    assert result.value.code == 2


def test_missing_uv_gives_an_actionable_error(monkeypatch, capsys):
    monkeypatch.setattr(starbench.shutil, "which", lambda _: None)
    assert starbench.main([]) == 127
    assert "Install it" in capsys.readouterr().err


@pytest.mark.skipif(os.name != "posix", reason="POSIX exec integration")
@pytest.mark.parametrize("args,native", [
    ([], True),
    (["env", "--headless", "--no-hub", "--env-id", "custom env"], True),
    (["--backend=python", "--mock-ai", "--no-hub"], False),
    (["--backend", "python", "--backend", "rust", "--native-threads", "4"], True),
])
def test_real_entrypoint_preserves_args_cwd_and_exit_status(args, native, tmp_path):
    tools = tmp_path / "tools with spaces"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), 'venv': os.getenv('VIRTUAL_ENV')}))\n"
        "sys.exit(7)\n"
    )
    uv.chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(starbench.ROOT / "starbench.py"), *args],
        cwd=tmp_path,
        env={**os.environ, 'VIRTUAL_ENV': str(tmp_path / 'script-env'),
             "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
        text=True, capture_output=True,
    )
    assert result.returncode == 7, result.stderr
    launched = json.loads(result.stdout.splitlines()[-1])
    original_args = args[1:] if args[:1] == ["env"] else args
    expected = ["run", *( ["--extra", "native"] if native else []),
                '--extra', 'pygame', "rotk_env/main.py", *original_args]
    assert launched == {"args": expected, "cwd": str(starbench.ROOT), 'venv': None}


def test_windows_path_uses_same_command_and_root(monkeypatch):
    invoked = []
    monkeypatch.setattr(starbench.os, "name", "nt")
    monkeypatch.setattr(starbench.shutil, "which", lambda _: "uv.exe")
    monkeypatch.setattr(starbench.subprocess, "call",
                        lambda command, cwd, env: invoked.append((command, cwd, env.get('VIRTUAL_ENV'))) or 9)
    assert starbench.main(["--backend", "python", "--headless"]) == 9
    assert invoked == [(["uv.exe", "run", '--extra', 'pygame', "rotk_env/main.py", "--backend",
                         "python", "--headless"], starbench.ROOT, None)]


def test_web_entrypoint_identifies_renderer_without_pygame_support_banner():
    env = dict(os.environ)
    env.pop('PYGAME_HIDE_SUPPORT_PROMPT', None)
    result = subprocess.run([sys.executable, '-m', 'rotk_env.rendering.web', '--help'],
                            cwd=starbench.ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'server-side Rust' in result.stdout
    assert 'pygame community' not in result.stdout and 'SDL ' not in result.stdout


def test_renderer_launcher_uses_env_owned_module_without_changing_default():
    args = ['--renderer', 'web', '--no-hub', '--scenario', 'chibi-small']
    assert starbench.launch_command(args, 'uv') == [
        'uv', 'run', '--extra', 'native', 'python', '-m', 'rotk_env.rendering.web', *args]
    assert starbench.launch_command(['--renderer=pygame', '--no-hub'], 'uv') == [
        'uv', 'run', '--extra', 'native', '--extra', 'pygame', 'rotk_env/main.py', '--no-hub']
    with pytest.raises(SystemExit):
        starbench.launch_command(['--renderer=web', '--backend=python'], 'uv')
