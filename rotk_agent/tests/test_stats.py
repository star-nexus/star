"""Token accounting and cache-hit rollups."""

from types import SimpleNamespace

from rotk_agent.core.stats import ErrorStatsCollector, parse_usage


class TestParseUsage:
    def test_chat_completions_shape(self):
        parsed = parse_usage(
            {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
                "completion_tokens_details": {"reasoning_tokens": 30},
            }
        )
        assert parsed == {
            "prompt_tokens": 100,
            "completion_tokens": 40,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
            "reasoning_tokens": 30,
        }

    def test_responses_api_shape(self):
        # OpenAI Responses uses input/output + cached_tokens on a nested object.
        parsed = parse_usage(
            SimpleNamespace(
                input_tokens=200,
                output_tokens=50,
                input_tokens_details=SimpleNamespace(cached_tokens=150),
                output_tokens_details=SimpleNamespace(reasoning_tokens=40),
            )
        )
        assert parsed["prompt_tokens"] == 200
        assert parsed["completion_tokens"] == 50
        assert parsed["prompt_cache_hit_tokens"] == 150
        assert parsed["prompt_cache_miss_tokens"] == 50
        assert parsed["reasoning_tokens"] == 40

    def test_missing_usage_is_zeros(self):
        assert parse_usage(None)["prompt_tokens"] == 0
        assert parse_usage({})["prompt_cache_hit_tokens"] == 0

    def test_miss_is_inferred_when_the_provider_only_reports_hits(self):
        parsed = parse_usage({"prompt_tokens": 100, "prompt_cache_hit_tokens": 75})
        assert parsed["prompt_cache_miss_tokens"] == 25


class TestRecordUsage:
    def test_totals_accumulate_and_hit_rate_is_over_prompt_tokens(self):
        stats = ErrorStatsCollector()
        stats.record_usage(
            {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
            }
        )
        stats.record_usage(
            {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "prompt_cache_hit_tokens": 20,
                "prompt_cache_miss_tokens": 80,
            }
        )

        summary = stats.get_api_stats()
        assert summary["prompt_tokens"] == 200
        assert summary["completion_tokens"] == 20
        assert summary["prompt_cache_hit_tokens"] == 100
        assert summary["prompt_cache_miss_tokens"] == 100
        assert summary["cache_hit_rate"] == 50.0

    def test_hit_rate_is_zero_before_any_tokens(self):
        assert ErrorStatsCollector().cache_hit_rate() == 0.0
