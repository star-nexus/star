"""Profile and prompt resolution.

These encode the dispatch a shell script used to do by picking one of six
near-identical agent files from the provider name.
"""

import pytest

from rotk_agent import profiles


class TestProfileResolution:
    @pytest.mark.parametrize(
        "provider,expected",
        [
            ("vllm_nvidia_9b", "nemotron"),
            ("vllm_gpt_oss", "gpt_oss"),
            ("vllm_qwen3_14b", "qwen3"),
            ("deepseek", "qwen3"),
            ("siliconflow_qwen3", "qwen3"),
            ("fake", "fake"),
        ],
    )
    def test_infers_profile_from_provider(self, provider, expected):
        assert profiles.resolve_profile(provider).name == expected

    def test_explicit_profile_overrides_inference(self):
        assert profiles.resolve_profile("vllm_gpt_oss", "baseline").name == "baseline"

    def test_unknown_profile_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            profiles.resolve_profile("deepseek", "nope")

    def test_baseline_is_only_reachable_explicitly(self):
        # It is a control group, so no provider name should select it by accident.
        assert profiles.PROFILES["baseline"].provider_match == ()


class TestThinkingDefaults:
    def test_reasoning_is_on_everywhere_except_baseline(self):
        for name, profile in profiles.PROFILES.items():
            if name in ("baseline", "fake"):
                assert not profile.enable_thinking
            else:
                assert profile.enable_thinking, name


class TestPromptResolution:
    def test_prompt_exists_for_every_mode_and_language(self):
        for kind in ("realtime", "turn"):
            for language in ("cn", "en"):
                assert profiles.load_prompt(kind, language)

    def test_baseline_gets_its_own_realtime_prompt(self):
        # The baseline prompt drops the tactical priming. Loading the primed
        # prompt instead would defeat the point of the control group, which is
        # exactly what the old baseline agent did.
        primed = profiles.load_prompt("realtime", "cn")
        control = profiles.load_prompt("realtime", "cn", variant="baseline")
        assert control != primed
        assert "思考进攻战术" in primed
        assert "思考进攻战术" not in control

    def test_variant_falls_back_when_absent(self):
        # There is no turn-based baseline prompt, so it uses the plain one.
        assert profiles.load_prompt("turn", "cn", variant="baseline") == (
            profiles.load_prompt("turn", "cn")
        )

    def test_missing_prompt_names_what_it_tried(self):
        with pytest.raises(FileNotFoundError, match="system_prompt_turn_fr"):
            profiles.load_prompt("turn", "fr")

    def test_candidate_order_prefers_the_variant(self):
        assert profiles.prompt_candidates("realtime", "cn", "baseline") == [
            "system_prompt_realtime_cn_baseline",
            "system_prompt_realtime_cn",
        ]


class TestPromptRendering:
    def test_fills_faction_placeholders(self):
        rendered = profiles.render_prompt(
            "$faction_name ($faction) vs $opponent_name ($opponent)", "shu"
        )
        assert rendered == "蜀 (shu) vs 魏 (wei)"

    def test_every_prompt_renders_without_leftover_faction_placeholders(self):
        for kind in ("realtime", "turn"):
            for language in ("cn", "en"):
                rendered = profiles.render_prompt(
                    profiles.load_prompt(kind, language), "wei"
                )
                assert "$faction" not in rendered
                assert "$opponent" not in rendered
                assert "$home_bases_block" in rendered

    def test_map_briefing_fills_home_bases_in_the_system_prompt(self):
        template = profiles.load_prompt("turn", "cn")
        rendered = profiles.render_prompt(template, "wei")
        filled = profiles.apply_map_briefing_to_prompt(
            rendered,
            {
                "home_bases": {
                    "wei": {"col": 2, "row": 3, "kind": "home_base"},
                    "shu": {"col": -2, "row": -4, "kind": "home_base"},
                },
                "home_bases_meaning": "各阵营基地坐标",
            },
        )
        assert "$home_bases_block" not in filled
        assert "**魏 (wei) 基地 / home base**: `(2, 3)`" in filled
        assert "**蜀 (shu) 基地 / home base**: `(-2, -4)`" in filled
        assert "各阵营基地坐标" in filled

    def test_unknown_faction_falls_back_to_wei(self):
        assert profiles.faction_info("qi") == profiles.faction_info("wei")


class TestRealtimeOpeningLanguage:
    def test_follows_language(self):
        from rotk_agent.modes.realtime import RealTimeMode

        assert "我方势力" in RealTimeMode(language="cn").opening_prompt("shu")
        assert "Our faction" in RealTimeMode(language="en").opening_prompt("shu")


class TestHistoryLimits:
    def test_both_modes_trim_at_one_hundred_messages(self):
        from rotk_agent.modes.realtime import RealTimeMode
        from rotk_agent.modes.turn import TurnBasedMode

        assert RealTimeMode.history_limit == 100
        assert TurnBasedMode.history_limit == 100
