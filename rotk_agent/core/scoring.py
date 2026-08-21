"""The strategy-reasoning rubric.

This is the *single* rubric for every model and every mode. It used to be
copy-pasted into each agent script, and the copies had drifted: the flagship
real-time agent recognised 15 Chinese keywords while the other six recognised
34, so identical reasoning scored differently depending on which file ran.
Since the resulting score reaches the settlement report, that made the metric
incomparable across models. The narrow list below is authoritative.

The detection is deliberately conservative: a keyword only counts when it sits
near a sequencing word and is not negated, so "do not flank" does not score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

# Tactical vocabulary. Narrow on purpose: these are terms that only appear in
# genuine tactical reasoning, not in generic narration about the game.
ZH_KEYWORDS = [
    "包抄", "侧翼", "伏击", "牵制",
    "佯攻", "集结", "兵力部署",
    "固守", "地形优势", "防线", "绕后", "夹击",
    "协同", "集火", "集中火力",
]

EN_KEYWORDS = [
    "encircle", "outflank", "flank",
    "ambush",
    "pin down", "contain", "tie down",
    "feint", "feigned attack",
    "regroup", "assemble", "concentrate",
    "deployment", "troop deployment",
    "hold", "defend", "hold position",
    "terrain advantage",
    "defense line", "defensive line",
    "pincer", "pincer attack",
    "coordinate", "cooperation", "cooperate",
    "concentrate fire", "focus fire",
    "concentrated fire", "massed fire",
]

# Words indicating the model is ordering steps rather than naming a tactic.
STRUCTURE_TERMS = [
    "先", "然后", "再", "首先", "优先", "目标", "步骤", "顺序", "选择", "方案", "计划",
    "first", "then", "next", "priority", "goal", "objective", "step", "order",
]

NEGATIONS = [
    "不", "不要", "不能", "不可", "停止", "禁止", "避免", "取消",
    "not", "don't", "can't", "won't", "avoid", "stop", "cancel", "never",
]

# Reposition-then-strike (or the reverse) expressed within one clause.
ZH_SEQUENCE_PATTERNS = [
    r"(移动|前进|靠近|靠拢|调整|转移|推进|到达).{0,25}(攻击|开火|打击|交战|冲锋|压制|集火|歼灭|突击)",
    r"(位置|坐标).{0,25}(攻击|开火|打击|交战)",
    r"(攻击|开火|打击|交战|冲锋|压制|集火|突击).{0,25}(移动|前进|靠近|靠拢|调整|转移|撤退|推进|到达)",
]

EN_SEQUENCE_PATTERNS = [
    r"(move|advance|relocate|close in|position).{0,40}(attack|engage|fire|strike|assault)",
    r"(attack|engage|fire|strike|assault).{0,40}(move|advance|relocate|retreat|position)",
]

MOVE_TERMS_ZH = ["移动", "前进", "靠近", "靠拢", "调整", "转移", "推进", "到达"]
ATTACK_TERMS_ZH = [
    "攻击", "开火", "打击", "交战", "冲锋", "压制", "集火", "歼灭", "突击",
    "支援", "协同", "集中火力",
]
MOVE_TERMS_EN = ["move", "advance", "relocate", "close in", "retreat"]
ATTACK_TERMS_EN = ["attack", "engage", "fire", "strike", "assault", "charge", "suppress"]

KEYWORD_PROXIMITY_WINDOW = 50
NEGATION_WINDOW = 20
SEQUENCE_NEGATION_WINDOW = 15


@dataclass(frozen=True)
class StrategyHit:
    """Outcome of scoring one assistant message."""

    keywords: bool
    sequence: bool

    def __bool__(self) -> bool:
        return self.keywords or self.sequence

    @property
    def score(self) -> float:
        """A concrete reposition-then-strike plan is worth more than vocabulary."""
        return 1.0 if self.sequence else 0.5


def _negated_near(text: str, start: int, end: int, window: int) -> bool:
    context = text[max(0, start - window) : min(len(text), end + window)].lower()
    return any(neg in context for neg in NEGATIONS)


def contains_strategy_keywords(text: str) -> bool:
    """Tactical vocabulary sitting near a sequencing word, without negation."""
    if not text:
        return False

    lowered = text.lower()

    keyword_spans = []
    for kw in ZH_KEYWORDS:
        for match in re.finditer(re.escape(kw), text):
            keyword_spans.append(match.span())
    for kw in EN_KEYWORDS:
        for match in re.finditer(re.escape(kw), lowered):
            keyword_spans.append(match.span())

    if not keyword_spans:
        return False

    structure_spans = []
    for term in STRUCTURE_TERMS:
        # Chinese terms must match the original casing-preserved text.
        haystack = text if any(c >= "\u4e00" for c in term) else lowered
        for match in re.finditer(re.escape(term), haystack):
            structure_spans.append(match.span())

    if not structure_spans:
        return False

    for kw_start, kw_end in keyword_spans:
        if _negated_near(text, kw_start, kw_end, NEGATION_WINDOW):
            continue
        for st_start, st_end in structure_spans:
            distance = min(abs(kw_start - st_end), abs(st_start - kw_end))
            if distance <= KEYWORD_PROXIMITY_WINDOW:
                return True

    return False


def _terms_present_unnegated(
    segment: str, terms_zh: List[str], terms_en: List[str]
) -> bool:
    lowered = segment.lower()
    found = [t for t in terms_zh if t in segment] + [t for t in terms_en if t in lowered]
    if not found:
        return False

    for term in found:
        pos = segment.find(term)
        if pos == -1:
            pos = lowered.find(term)
        if pos == -1:
            continue
        if not _negated_near(segment, pos, pos + len(term), SEQUENCE_NEGATION_WINDOW):
            return True
    return False


def _unnegated_positions(text: str, terms: List[str]) -> List[int]:
    lowered = text.lower()
    positions = []
    for term in terms:
        term_lower = term.lower()
        start = 0
        while True:
            pos = lowered.find(term_lower, start)
            if pos == -1:
                break
            if not _negated_near(
                lowered, pos, pos + len(term_lower), SEQUENCE_NEGATION_WINDOW
            ):
                positions.append(pos)
            start = pos + 1
    return positions


def contains_strategy_sequence(text: str) -> bool:
    """A reposition-then-strike plan, stated in one clause or across clauses."""
    if not text:
        return False

    lowered = text.lower()

    for pattern in ZH_SEQUENCE_PATTERNS:
        for match in re.finditer(pattern, text):
            if not _negated_near(
                text, *match.span(), window=SEQUENCE_NEGATION_WINDOW
            ):
                return True
    for pattern in EN_SEQUENCE_PATTERNS:
        for match in re.finditer(pattern, lowered):
            if not _negated_near(
                lowered, *match.span(), window=SEQUENCE_NEGATION_WINDOW
            ):
                return True

    # Across clauses: a move in one sentence, a strike within the next two.
    segments = [s.strip() for s in re.split(r"[。；;\.!?\n]+", text) if s.strip()]
    for i in range(len(segments)):
        for j in range(i + 1, min(i + 3, len(segments))):
            first, second = segments[i], segments[j]
            if _terms_present_unnegated(
                first, MOVE_TERMS_ZH, MOVE_TERMS_EN
            ) and _terms_present_unnegated(second, ATTACK_TERMS_ZH, ATTACK_TERMS_EN):
                return True
            if _terms_present_unnegated(
                first, ATTACK_TERMS_ZH, ATTACK_TERMS_EN
            ) and _terms_present_unnegated(second, MOVE_TERMS_ZH, MOVE_TERMS_EN):
                return True

    # Same clause: allow a wider gap in longer passages.
    move_positions = _unnegated_positions(text, MOVE_TERMS_ZH + MOVE_TERMS_EN)
    attack_positions = _unnegated_positions(text, ATTACK_TERMS_ZH + ATTACK_TERMS_EN)
    threshold = int(40 * min(len(text) / 200, 2.0))

    return any(
        abs(move_pos - attack_pos) <= threshold
        for move_pos in move_positions
        for attack_pos in attack_positions
    )


def detect_strategy(text: str) -> StrategyHit:
    """Score one assistant message. The two checks are independent."""
    return StrategyHit(
        keywords=contains_strategy_keywords(text),
        sequence=contains_strategy_sequence(text),
    )


__all__ = [
    "StrategyHit",
    "contains_strategy_keywords",
    "contains_strategy_sequence",
    "detect_strategy",
]
