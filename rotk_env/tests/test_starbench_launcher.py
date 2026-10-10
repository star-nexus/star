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
        "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}))\n"
        "sys.exit(7)\n"
    )
    uv.chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(starbench.ROOT / "starbench.py"), *args],
        cwd=tmp_path,
        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
        text=True, capture_output=True,
    )
    assert result.returncode == 7, result.stderr
    launched = json.loads(result.stdout.splitlines()[-1])
    original_args = args[1:] if args[:1] == ["env"] else args
    expected = ["run", *( ["--extra", "native"] if native else []),
                "rotk_env/main.py", *original_args]
    assert launched == {"args": expected, "cwd": str(starbench.ROOT)}


def test_windows_path_uses_same_command_and_root(monkeypatch):
    invoked = []
    monkeypatch.setattr(starbench.os, "name", "nt")
    monkeypatch.setattr(starbench.shutil, "which", lambda _: "uv.exe")
    monkeypatch.setattr(starbench.subprocess, "call",
                        lambda command, cwd: invoked.append((command, cwd)) or 9)
    assert starbench.main(["--backend", "python", "--headless"]) == 9
    assert invoked == [(["uv.exe", "run", "rotk_env/main.py", "--backend",
                         "python", "--headless"], starbench.ROOT)]
