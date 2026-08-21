"""Provider config loading, including `inherits` variants."""

import pytest

from rotk_agent.core.config import load_config, resolve_section

CONFIG = {
    "deepseek-v4-flash": {
        "model_id": "deepseek-v4-flash",
        "api_key": "sk-test",
        "base_url": "https://api.deepseek.com/chat/completions",
    },
    "deepseek-v4-flash-off": {
        "inherits": "deepseek-v4-flash",
        "enable_thinking": False,
    },
    "deepseek-v4-flash-on": {
        "inherits": "deepseek-v4-flash",
        "enable_thinking": True,
    },
    "override-model": {
        "inherits": "deepseek-v4-flash",
        "model_id": "deepseek-v4-pro",
    },
    "two-hops": {"inherits": "deepseek-v4-flash-off"},
    "dangling": {"inherits": "nonexistent"},
    "loop-a": {"inherits": "loop-b"},
    "loop-b": {"inherits": "loop-a"},
    "not-a-table": "oops",
}


class TestSectionResolution:
    def test_a_plain_section_is_returned_as_is(self):
        assert resolve_section(CONFIG, "deepseek-v4-flash")["model_id"] == (
            "deepseek-v4-flash"
        )

    def test_a_variant_borrows_credentials_and_endpoint(self):
        # The whole point: an A/B pair without duplicating the API key.
        section = resolve_section(CONFIG, "deepseek-v4-flash-off")
        assert section["model_id"] == "deepseek-v4-flash"
        assert section["api_key"] == "sk-test"
        assert section["enable_thinking"] is False

    def test_the_child_wins_over_what_it_inherits(self):
        assert resolve_section(CONFIG, "override-model")["model_id"] == (
            "deepseek-v4-pro"
        )

    def test_inherits_chains(self):
        section = resolve_section(CONFIG, "two-hops")
        assert section["api_key"] == "sk-test"
        assert section["enable_thinking"] is False

    def test_the_inherits_key_does_not_leak_into_the_result(self):
        assert "inherits" not in resolve_section(CONFIG, "deepseek-v4-flash-off")

    def test_a_missing_parent_names_the_child_that_wanted_it(self):
        with pytest.raises(ValueError, match="inherited by 'dangling'"):
            resolve_section(CONFIG, "dangling")

    def test_a_missing_section_is_reported_plainly(self):
        with pytest.raises(ValueError, match="Invalid provider: nope"):
            resolve_section(CONFIG, "nope")

    def test_a_cycle_is_reported_rather_than_hanging(self):
        with pytest.raises(ValueError, match="Circular 'inherits'"):
            resolve_section(CONFIG, "loop-a")

    def test_a_non_table_section_is_rejected(self):
        with pytest.raises(ValueError, match="is not a table"):
            resolve_section(CONFIG, "not-a-table")


class TestLoadConfig:
    @staticmethod
    def write(tmp_path, body):
        path = tmp_path / ".configs.toml"
        path.write_text(body, encoding="utf-8")
        return str(path)

    def test_variants_resolve_end_to_end(self, tmp_path):
        path = self.write(
            tmp_path,
            """
[deepseek-v4-flash]
model_id = "deepseek-v4-flash"
api_key = "sk-test"
base_url = "https://api.deepseek.com/chat/completions"

[deepseek-v4-flash-off]
inherits = "deepseek-v4-flash"
enable_thinking = false
""",
        )
        config = load_config(path, provider="deepseek-v4-flash-off")

        assert config.provider == "deepseek-v4-flash-off"  # what the logs report
        assert config.model_id == "deepseek-v4-flash"
        assert config.enable_thinking is False

    def test_an_explicit_flag_beats_the_profile_default(self, tmp_path):
        path = self.write(
            tmp_path, '[p]\nmodel_id = "m"\nenable_thinking = false\n'
        )
        config = load_config(path, provider="p", enable_thinking_default=True)
        assert config.enable_thinking is False

    def test_the_profile_default_applies_when_the_config_is_silent(self, tmp_path):
        path = self.write(tmp_path, '[p]\nmodel_id = "m"\n')
        assert load_config(path, provider="p", enable_thinking_default=False).enable_thinking is False
        assert load_config(path, provider="p", enable_thinking_default=True).enable_thinking is True

    def test_the_code_default_applies_when_the_config_is_silent(self, tmp_path):
        from rotk_agent.core.config import DEFAULT_MAX_TOKENS, DEFAULT_REASONING_EFFORT

        path = self.write(tmp_path, '[p]\nmodel_id = "m"\n')
        config = load_config(path, provider="p")
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.reasoning_effort == DEFAULT_REASONING_EFFORT

    def test_toml_overrides_the_code_defaults(self, tmp_path):
        path = self.write(
            tmp_path,
            '[p]\nmodel_id = "m"\nmax_tokens = 1024\nreasoning_effort = "max"\n',
        )
        config = load_config(path, provider="p")
        assert config.max_tokens == 1024
        assert config.reasoning_effort == "max"

    def test_inherited_max_tokens_reaches_the_child(self, tmp_path):
        path = self.write(
            tmp_path,
            """
[parent]
model_id = "m"
max_tokens = 4096

[child]
inherits = "parent"
""",
        )
        assert load_config(path, provider="child").max_tokens == 4096

    def test_a_missing_file_is_reported(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_path / "absent.toml"), provider="p")

    def test_a_section_without_a_model_id_is_reported(self, tmp_path):
        path = self.write(tmp_path, '[p]\napi_key = "k"\n')
        with pytest.raises(ValueError, match="Model ID not found"):
            load_config(path, provider="p")


class TestCliDefaults:
    def test_reasoning_effort_defaults_to_low(self):
        from rotk_agent.main import parse_args

        assert parse_args([]).reasoning_effort == "low"

    def test_carry_reasoning_defaults_on(self):
        from rotk_agent.main import parse_args

        assert parse_args([]).carry_reasoning is True
        assert parse_args(["--no-carry-reasoning"]).carry_reasoning is False
