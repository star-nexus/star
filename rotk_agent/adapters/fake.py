"""A scripted adapter, for exercising the agent without an LLM.

This is the harness's safety net. Every layer below the model — the chat loop,
tool dispatch, result filtering, the protocol round trip, turn gating, and the
stats that get reported at game end — can be driven deterministically and for
free. Point it at a running hub with `--provider fake` and the only thing not
under test is the model itself.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from ..core.console import console
from ..core.types import Message, NormalizedReply, ToolCall, ToolDefinition
from .base import ModelAdapter

Script = Union[Sequence[NormalizedReply], Callable[[List[Message], List[str]], NormalizedReply]]


def _call(name: str, arguments: Dict[str, Any], call_id: str) -> ToolCall:
    return ToolCall(
        id=call_id, name=name, arguments=json.dumps(arguments, ensure_ascii=False)
    )


class ProbeScript:
    """Plays a short but realistic game: look, move, attack, end turn.

    Unit ids are not known ahead of time, so the script reads them out of the
    most recent `get_faction_state` result in the conversation.
    """

    def __init__(self, faction: str = "wei", target: Dict[str, int] | None = None):
        self.faction = faction
        self.target = target or {"col": 0, "row": 0}
        self.step = 0

    @staticmethod
    def _latest_units(messages: List[Message]) -> List[Any]:
        """Pull the unit list out of the newest tool result that has one."""
        for msg in reversed(messages):
            if msg.role != "tool" or not msg.content:
                continue
            try:
                payload = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                continue
            units = payload.get("units") if isinstance(payload, dict) else None
            if isinstance(units, list) and units:
                return units
        return []

    @staticmethod
    def _unit_id(unit: Any) -> Optional[int]:
        if isinstance(unit, dict):
            unit_id = unit.get("unit_id")
        elif isinstance(unit, (list, tuple)) and unit:
            unit_id = unit[0]
        else:
            return None
        return unit_id if isinstance(unit_id, int) else None

    def _first_unit_id(self, messages: List[Message]) -> Optional[int]:
        for unit in self._latest_units(messages):
            unit_id = self._unit_id(unit)
            if unit_id is not None:
                return unit_id
        return None

    @staticmethod
    def _reachable_target(unit: Any) -> Optional[Dict[str, int]]:
        """Copy the first listed hex so the probe does not invent a coordinate."""
        reachable = None
        if isinstance(unit, list) and len(unit) > 12 and isinstance(unit[12], dict):
            reachable = unit[12].get("reachable")
        elif isinstance(unit, dict):
            reachable = unit.get("reachable")
        if not isinstance(reachable, list) or not reachable:
            return None
        hexes = reachable[0]
        if isinstance(hexes, dict) and "col" in hexes and "row" in hexes:
            return {"col": int(hexes["col"]), "row": int(hexes["row"])}
        if isinstance(hexes, (list, tuple)) and len(hexes) >= 2:
            return {"col": int(hexes[0]), "row": int(hexes[1])}
        return None

    def _move_target(self, messages: List[Message], unit_id: int) -> Dict[str, int]:
        for unit in self._latest_units(messages):
            if self._unit_id(unit) != unit_id:
                continue
            copied = self._reachable_target(unit)
            if copied is not None:
                return copied
        return self.target

    def __call__(
        self, messages: List[Message], tool_names: List[str]
    ) -> NormalizedReply:
        self.step += 1
        call_id = f"fake_call_{self.step}"

        # Strategy-shaped narration, so the scoring path gets exercised too.
        reasoning = (
            "首先集结兵力，然后移动到敌方侧翼位置，再发起攻击形成夹击。"
        )

        if self.step == 1:
            return NormalizedReply(
                text=reasoning,
                tool_calls=[
                    _call("perform_action",
                          {"action": "get_faction_state", "params": {"faction": self.faction}},
                          call_id)
                ],
                finish_reason="tool_calls",
            )

        unit_id = self._first_unit_id(messages)

        if self.step == 2 and unit_id is not None:
            return NormalizedReply(
                text=reasoning,
                tool_calls=[
                    _call("perform_action",
                          {"action": "move",
                           "params": {
                               "unit_id": unit_id,
                               "target_position": self._move_target(messages, unit_id),
                           }},
                          call_id)
                ],
                finish_reason="tool_calls",
            )

        if self.step == 3 and "end_turn" in tool_names:
            return NormalizedReply(
                text="本回合行动完毕，结束回合。",
                tool_calls=[_call("end_turn", {}, call_id)],
                finish_reason="tool_calls",
            )

        # Nothing left to do: a plain reply, which the mode turns into a nudge.
        return NormalizedReply(text="等待新的战场情报。", finish_reason="stop")


class FakeAdapter(ModelAdapter):
    """Returns canned replies instead of calling a model."""

    name = "fake"

    def __init__(self, config, stats, script: Optional[Script] = None):
        super().__init__(config, stats)
        self.script: Script = script if script is not None else ProbeScript()
        self._index = 0

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: str = "",
    ) -> NormalizedReply:
        self.stats.add_total_api_call_count()
        tool_names = [t.name for t in tools or []]

        if callable(self.script):
            reply = self.script(messages, tool_names)
        else:
            if self._index >= len(self.script):
                reply = NormalizedReply(text="script exhausted", finish_reason="stop")
            else:
                reply = self.script[self._index]
                self._index += 1

        console.print(
            f"🎭 FakeAdapter reply: finish_reason={reply.finish_reason}, "
            f"tool_calls={[c.name for c in reply.tool_calls]}",
            style="magenta",
        )
        return reply


__all__ = ["FakeAdapter", "ProbeScript", "Script"]
