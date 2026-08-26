"""auto_test preflight must resolve `inherits`, same as the agent."""

from auto_test import _validate_providers


def _write(tmp_path, body: str) -> str:
    path = tmp_path / ".configs.toml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_a_variant_that_only_inherits_is_accepted(tmp_path):
    path = _write(
        tmp_path,
        """
[deepseek-v4-flash]
model_id = "deepseek-v4-flash"
api_key = "sk-test"

[deepseek-v4-flash-off]
inherits = "deepseek-v4-flash"
enable_thinking = false
""",
    )
    ok, err = _validate_providers(
        "deepseek-v4-flash-off", "deepseek-v4-flash-off", path
    )
    assert ok is True
    assert err == ""


def test_a_missing_section_is_still_rejected(tmp_path):
    path = _write(tmp_path, '[p]\nmodel_id = "m"\n')
    ok, err = _validate_providers("nope", "p", path)
    assert ok is False
    assert "not found" in err


def test_a_dangling_parent_is_reported(tmp_path):
    path = _write(tmp_path, '[child]\ninherits = "missing"\n')
    ok, err = _validate_providers("child", "child", path)
    assert ok is False
    assert "inherited by 'child'" in err


def test_a_section_without_model_id_after_inherit_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        """
[parent]
api_key = "k"

[child]
inherits = "parent"
""",
    )
    ok, err = _validate_providers("child", "child", path)
    assert ok is False
    assert "has no 'model_id'" in err
