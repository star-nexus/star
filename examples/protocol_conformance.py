"""Live Agent–ENV protocol conformance probe.

Talks to Hub+ENV the way a third-party agent must: ``protocol.AgentClient``
only. No ``rotk_agent``, no ``rotk_env``.

This checks the wire contract in ``docs/agent-protocol.md``, not the LLM chat
loop. Isolated checks (join shape, stats payload, the MUST sequence against a
fake session) live in ``protocol/tests/test_agent_protocol.py`` and do not
need a Hub.

Prerequisites
-------------

    * Hub:  python framework/cli.py hub
            (default ws://localhost:8000/ws/metaverse)
    * ENV:  uv run rotk_env/main.py   (mode must match --mode)
    * If a local proxy is set, bypass loopback:

            export NO_PROXY="localhost,127.0.0.1,::1"

Usage
-----

    uv run python examples/protocol_conformance.py --faction wei --mode turn_based
    uv run python examples/protocol_conformance.py --faction wei --mode real_time

Turn-based waits for ``turn_start`` then ACKs. ``end_turn`` and
``report_llm_stats`` are off by default so a probe does not steal a live
faction's turn or trip settlement. Pass ``--full`` against a dedicated ENV
to exercise those too.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import ActionTimeout, AgentClient, AgentClientError
from protocol.conformance import ConformanceError, run_must_sequence

os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1,::1")

DEFAULT_HUB = "ws://localhost:8000/ws/metaverse"


def _parse_outcome(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


class LiveSession:
    """AgentClient plus ENV push events.

    Correlation used to be reimplemented here -- a third copy, with its own
    pending dict, its own id counter and its own int/str coercion. It now comes
    from `AgentClient`, and this class only adds what is specific to a
    conformance run: JSON-decoding outcomes and queueing unsolicited pushes.
    """

    def __init__(self, hub_url: str, env_id: str, agent_id: str):
        self.client = AgentClient(hub_url, env_id, agent_id)
        self._pushes: asyncio.Queue[dict] = asyncio.Queue()
        self.client.add_hub_listener("message", self._on_push)
        self.client.add_hub_listener("error", lambda data: print(f"Hub error: {data}"))
        self.client.add_hub_listener(
            "disconnect", lambda data: print(f"Hub disconnected: {data}")
        )

    def _on_push(self, data: dict) -> None:
        """Queue unsolicited ENV events. Outcomes are the client's business."""
        payload = data.get("payload") if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            return
        if payload.get("type") in ("turn_start", "game_end_notification"):
            self._pushes.put_nowait(payload)

    async def connect(self) -> None:
        await self.client.connect()
        await asyncio.sleep(0.3)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def call(
        self, action: str, parameters: Optional[dict] = None, timeout: float = 8.0
    ) -> Any:
        """Run one action, returning a decoded outcome or an error-shaped dict.

        The conformance sequence inspects `success`/`error_code`, so transport
        and protocol failures are reported in that shape rather than raised.
        """
        try:
            outcome = await self.client.call(action, parameters or {}, timeout=timeout)
        except ActionTimeout as e:
            return {"success": False, "error": str(e), "error_code": None}
        except AgentClientError as e:
            return {"success": False, "error": str(e), "error_code": None}
        return _parse_outcome(outcome)

    async def wait_push(self, event_type: str, timeout: float = 30.0) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for {event_type}")
            event = await asyncio.wait_for(self._pushes.get(), timeout=remaining)
            if event.get("type") == event_type:
                return event
            if event.get("type") == "game_end_notification":
                raise ConformanceError(
                    f"game ended while waiting for {event_type}: {event}"
                )


async def _run(args: argparse.Namespace) -> int:
    session = LiveSession(args.hub_url, args.env_id, args.agent_id)
    await session.connect()
    try:
        passed = await run_must_sequence(
            session,
            faction=args.faction,
            agent_id=args.agent_id,
            turn_based=args.mode == "turn_based",
            wait_turn_timeout=args.timeout,
            end_turn=args.end_turn,
            report_stats=args.report_stats,
        )
    finally:
        await session.disconnect()

    print("passed:", ", ".join(passed))
    if args.mode == "turn_based" and "turn_start" not in passed:
        print("turn_start was not exercised (sequence stopped earlier)")
    if not args.end_turn:
        print("skipped end_turn (pass --end-turn or --full)")
    if not args.report_stats:
        print("skipped report_llm_stats (pass --report-stats or --full)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-url", default=DEFAULT_HUB)
    parser.add_argument("--env-id", default="env_1")
    parser.add_argument("--agent-id", default="conformance_1")
    parser.add_argument("--faction", default="wei", choices=("wei", "shu", "wu"))
    parser.add_argument(
        "--mode",
        default="turn_based",
        choices=("turn_based", "real_time"),
        help="Must match how the ENV was started.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for turn_start in turn-based mode.",
    )
    parser.add_argument(
        "--end-turn",
        action="store_true",
        help="Call end_turn after ACK. Off by default so a live match is not stolen.",
    )
    parser.add_argument(
        "--report-stats",
        action="store_true",
        help="Call report_llm_stats. Off by default so settlement is not tripped early.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Exercise end_turn and report_llm_stats (use a dedicated ENV).",
    )
    args = parser.parse_args()
    if args.full:
        args.end_turn = True
        args.report_stats = True

    try:
        raise SystemExit(asyncio.run(_run(args)))
    except (ConformanceError, TimeoutError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
