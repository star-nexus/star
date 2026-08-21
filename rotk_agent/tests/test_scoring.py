"""The strategy rubric is a measured quantity, so it gets pinned down here.

Whatever these tests assert is what every model is scored against. Changing
them changes benchmark numbers, so a diff to this file should be deliberate.
"""

from rotk_agent.core import scoring


class TestKeywordDetection:
    def test_tactic_near_sequencing_word_scores(self):
        assert scoring.contains_strategy_keywords("首先包抄敌方侧翼，然后集火")

    def test_tactic_without_sequencing_word_does_not_score(self):
        # Vocabulary alone is narration, not a plan.
        assert not scoring.contains_strategy_keywords("这是一次包抄")

    def test_sequencing_word_without_tactic_does_not_score(self):
        assert not scoring.contains_strategy_keywords("首先，然后，最后")

    def test_negated_tactic_does_not_score(self):
        assert not scoring.contains_strategy_keywords("首先不要包抄敌方侧翼")

    def test_english_tactic_scores(self):
        assert scoring.contains_strategy_keywords(
            "First, outflank the enemy, then concentrate fire"
        )

    def test_empty_text_does_not_score(self):
        assert not scoring.contains_strategy_keywords("")

    def test_narrow_rubric_excludes_generic_vocabulary(self):
        # These words were in the wider list that six of the seven old agents
        # used. The narrow rubric deliberately ignores them, so a model is not
        # credited for merely saying "strategy".
        for generic in ("策略", "战略", "战术", "推进", "防守", "进攻", "视野"):
            assert generic not in scoring.ZH_KEYWORDS

    def test_rubric_size_is_pinned(self):
        assert len(scoring.ZH_KEYWORDS) == 15
        assert len(scoring.EN_KEYWORDS) == 29


class TestSequenceDetection:
    def test_move_then_attack_in_one_clause_scores(self):
        assert scoring.contains_strategy_sequence("移动到高地然后攻击敌方弓兵")

    def test_attack_then_move_scores(self):
        assert scoring.contains_strategy_sequence("先攻击敌方前锋，再移动到侧翼")

    def test_across_sentences_scores(self):
        assert scoring.contains_strategy_sequence("骑兵移动到桥头。随后攻击敌方主力。")

    def test_english_sequence_scores(self):
        assert scoring.contains_strategy_sequence(
            "Move the cavalry to the ridge and then attack their archers"
        )

    def test_negated_sequence_does_not_score(self):
        assert not scoring.contains_strategy_sequence("不要移动，也不要攻击")

    def test_unrelated_text_does_not_score(self):
        assert not scoring.contains_strategy_sequence("我在等待更多的战场情报。")


class TestScoreWeighting:
    def test_sequence_hit_is_worth_more_than_vocabulary(self):
        sequence_only = scoring.StrategyHit(keywords=False, sequence=True)
        keywords_only = scoring.StrategyHit(keywords=True, sequence=False)

        assert sequence_only.score == 1.0
        assert keywords_only.score == 0.5
        assert sequence_only.score > keywords_only.score

    def test_a_miss_is_falsy_and_a_hit_is_truthy(self):
        assert not scoring.StrategyHit(keywords=False, sequence=False)
        assert scoring.StrategyHit(keywords=True, sequence=False)

    def test_detect_runs_both_checks_independently(self):
        hit = scoring.detect_strategy("首先包抄侧翼，然后移动到高地并攻击。")
        assert hit.keywords
        assert hit.sequence
        assert hit.score == 1.0
