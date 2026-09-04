import sys

from rotk_env.main import parse_arguments


def test_uncapped_cli_flag_is_opt_in(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert parse_arguments().uncapped is False

    monkeypatch.setattr(sys, "argv", ["main.py", "--uncapped"])
    assert parse_arguments().uncapped is True
