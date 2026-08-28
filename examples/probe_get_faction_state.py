"""Live probe for get_faction_state against a running ENV.

Isolated pytest lives in rotk_env/tests/test_faction_state_fow.py and
test_faction_state_affordances.py. This script talks to the Hub the same way
an agent does, so you can press 1 in the game window and see fog /
visible_enemy_units / reachable counts change.

It prints a one-line mask summary per own unit (reachable hex count,
attackable ids). It cannot prove mask ≡ execute over the wire without
issuing a real move; that check is the isolated pytest.

Prerequisites
-------------

    * Hub:  python framework/cli.py hub
            (default ws://localhost:8000/ws/metaverse)
    * ENV:  uv run rotk_env/main.py   (the window you already started)
    * If a local proxy is set, bypass loopback:

            export NO_PROXY="localhost,127.0.0.1,::1"

Usage
-----

    uv run python examples/probe_get_faction_state.py --faction wei
    uv run python examples/probe_get_faction_state.py --faction wei --watch

--watch re-queries on Enter so you can toggle key 1 (fog) and compare.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import AgentClient, MessageType
from rotk_agent.profiles import FACTIONS

os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1,::1")

DEFAULT_HUB = "ws://localhost:8000/ws/metaverse"
ENEMY_SECRETS = ("capabilities", "commandable", "owner", "available_skills")


def _parse_outcome(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _request_id(value: Any) -> Any:
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


class LiveProbe:
    """AgentClient plus awaitable outcomes, without the full agent runner."""

    def __init__(self, hub_url: str, env_id: str, agent_id: str):
        self.client = AgentClient(hub_url, env_id, agent_id)
        self._pending: dict[Any, asyncio.Future] = {}
        self._next_id = 1
        self.client.add_hub_listener("message", self._on_message)
        self.client.add_hub_listener("error", self._on_error)
        self.client.add_hub_listener("disconnect", self._on_disconnect)

    def _fail_pending(self, error: Any, request_id: Any = None) -> None:
        result = {
            "success": False,
            "error": error,
            "error_code": None,
        }
        if isinstance(error, dict):
            result["error"] = error.get("error") or error.get("message") or error
            result["error_code"] = error.get("error_code")
        targets = (
            [self._pending[request_id]]
            if request_id in self._pending
            else list(self._pending.values())
        )
        for future in targets:
            if not future.done():
                future.set_result(result)

    def _on_message(self, data: dict) -> None:
        payload = data.get("payload") if isinstance(data, dict) else None
        if not isinstance(payload, dict) or payload.get("type") != "outcome":
            return
        request_id = _request_id(payload.get("id"))
        future = self._pending.get(request_id)
        if future is None or future.done():
            return
        future.set_result(_parse_outcome(payload.get("outcome")))

    def _on_error(self, data: Any) -> None:
        print(f"Hub error: {data}")
        payload = data.get("payload") if isinstance(data, dict) else None
        request_id = (
            _request_id(payload.get("id")) if isinstance(payload, dict) else None
        )
        self._fail_pending(payload if payload is not None else data, request_id)

    def _on_disconnect(self, data: Any) -> None:
        print(f"Hub disconnected: {data}")
        self._fail_pending(f"Hub disconnected: {data}")

    async def connect(self) -> None:
        await self.client.connect()
        await asyncio.sleep(0.3)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def call(
        self, action: str, parameters: Optional[dict] = None, timeout: float = 8.0
    ) -> Any:
        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future
        try:
            sent = await self.client.send_message(
                MessageType.MESSAGE.value,
                {
                    "type": "action",
                    "id": request_id,
                    "action": action,
                    "parameters": parameters or {},
                },
                target={"type": "env", "id": self.client.env_id},
            )
            if not sent:
                raise RuntimeError(f"Failed to send {action}")
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)


def _pos(unit: dict) -> str:
    position = unit.get("position") or {}
    return f"({position.get('col')}, {position.get('row')})"


def _own_line(unit: dict) -> str:
    status = unit.get("unit_status") or {}
    caps = (unit.get("capabilities") or {}).get("unit_resources") or {}
    ap = caps.get("remaining_action_points", caps.get("action_points", "?"))
    mp = caps.get("remaining_movement_points", caps.get("movement_points", "?"))
    reachable = unit.get("reachable")
    attackable = unit.get("attackable")
    reach_n = len(reachable) if isinstance(reachable, list) else "?"
    fire = attackable if isinstance(attackable, list) else "?"
    return (
        f"  #{unit.get('unit_id')}  {unit.get('unit_type')}  {_pos(unit)}  "
        f"count={status.get('current_count')}  AP={ap} MP={mp}  "
        f"reachable={reach_n} attackable={fire}  "
        f"owner={unit.get('owner')} commandable={unit.get('commandable')}"
    )


def _enemy_line(unit: dict) -> str:
    status = unit.get("unit_status") or {}
    return (
        f"  #{unit.get('unit_id')}  {unit.get('unit_type')}  "
        f"{unit.get('faction')}  {_pos(unit)}  "
        f"count={status.get('current_count')}"
    )


def print_faction_state(payload: dict) -> None:
    print()
    print("=" * 60)
    print(
        f"get_faction_state  faction={payload.get('faction')}  "
        f"fog={payload.get('fog')}"
    )
    print("=" * 60)
    units = payload.get("units") or []
    enemies = payload.get("visible_enemy_units") or []
    print(
        f"own units: {len(units)} alive "
        f"(total={payload.get('total_units')}, "
        f"actionable={payload.get('actionable_units')})"
    )
    for unit in units:
        print(_own_line(unit))
    if not units:
        print("  (none)")
    print(f"visible_enemy_units: {len(enemies)}")
    for unit in enemies:
        print(_enemy_line(unit))
    if not enemies:
        print("  (none)")


class Check:
    def __init__(self) -> None:
        self.failed = 0

    def expect(self, ok: bool, label: str, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        suffix = f"  — {detail}" if detail else ""
        print(f"  [{mark}] {label}{suffix}")
        if not ok:
            self.failed += 1


def check_own_payload(payload: Any, faction: str, checks: Check) -> None:
    checks.expect(isinstance(payload, dict), "own query returned a dict")
    if not isinstance(payload, dict):
        return
    success_detail = ""
    if payload.get("success") is not True:
        success_detail = str(
            payload.get("error") or payload.get("message") or payload
        )
    checks.expect(
        payload.get("success") is True,
        "own query success=True",
        success_detail,
    )
    if payload.get("success") is not True:
        return
    checks.expect(payload.get("faction") == faction, f"faction == {faction}")
    checks.expect(payload.get("fog") in ("active", "disabled"), "fog is active|disabled")
    units = payload.get("units") or []
    enemies = payload.get("visible_enemy_units") or []
    checks.expect(isinstance(units, list), "units is a list")
    checks.expect(isinstance(enemies, list), "visible_enemy_units is a list")
    if units:
        sample = units[0]
        checks.expect(
            "capabilities" in sample or "commandable" in sample,
            "own units include command panel (capabilities / commandable)",
        )
        missing_masks = [
            f"#{u.get('unit_id')}"
            for u in units
            if not isinstance(u.get("reachable"), list)
            or not isinstance(u.get("attackable"), list)
        ]
        checks.expect(
            not missing_masks,
            "own units include reachable list and attackable ids",
            ", ".join(missing_masks),
        )
        here_in_reach = []
        for u in units:
            if not isinstance(u.get("reachable"), list):
                continue
            pos = u.get("position") or {}
            here = (pos.get("col"), pos.get("row"))
            reach = {
                (t.get("col"), t.get("row"))
                for t in u["reachable"]
                if isinstance(t, dict)
            }
            if here in reach:
                here_in_reach.append(f"#{u.get('unit_id')}")
        checks.expect(
            not here_in_reach,
            "reachable omits the unit's current hex",
            ", ".join(here_in_reach),
        )
        enemy_ids = {
            e.get("unit_id") for e in enemies if e.get("unit_id") is not None
        }
        stray_fire = [
            f"#{u.get('unit_id')}->{tid}"
            for u in units
            if isinstance(u.get("attackable"), list)
            for tid in u["attackable"]
            if tid not in enemy_ids
        ]
        checks.expect(
            not stray_fire,
            "attackable ids are a subset of visible_enemy_units",
            ", ".join(stray_fire),
        )
    leaked = []
    for enemy in enemies:
        for key in ENEMY_SECRETS + ("reachable", "attackable"):
            if key in enemy:
                leaked.append(f"#{enemy.get('unit_id')}.{key}")
        status = enemy.get("unit_status") or {}
        extra = [k for k in status if k != "current_count"]
        if extra:
            leaked.append(f"#{enemy.get('unit_id')}.unit_status.{extra}")
    checks.expect(
        not leaked,
        "visible enemies are id/type/position/count only",
        ", ".join(str(x) for x in leaked) if leaked else "",
    )
    checks.expect("map" not in payload, "get_faction_state has no map/bases noise")


def check_cross_faction(payload: Any, checks: Check) -> None:
    checks.expect(isinstance(payload, dict), "enemy query returned a dict")
    if not isinstance(payload, dict):
        return
    code = payload.get("error_code")
    checks.expect(payload.get("success") is False, "enemy query success=False")
    checks.expect(code == 2005, "enemy query error_code=2005", f"got {code}")
    checks.expect(
        "visible_enemy_units" not in payload and "units" not in payload,
        "enemy query does not dump army lists",
    )


async def run(args: argparse.Namespace) -> int:
    opponent = FACTIONS.get(args.faction, FACTIONS["wei"])["enemy"]
    probe = LiveProbe(args.hub_url, args.env_id, args.agent_id)
    print(f"Connecting {args.agent_id} → {args.hub_url} env={args.env_id} …")
    try:
        await probe.connect()
    except Exception as exc:
        print(
            f"Connect failed: {exc}\n"
            "Is the Hub running, and does --env-id match the ENV window?"
        )
        return 1

    checks = Check()
    try:
        register = await probe.call(
            "register_agent_info",
            {
                "faction": args.faction,
                "provider": "probe",
                "model_id": "get-faction-state",
                "base_url": "http://localhost",
                "agent_id": args.agent_id,
                "note": "live get_faction_state probe",
            },
        )
        print(f"register_agent_info → {register}")
        registered = (
            isinstance(register, dict) and register.get("success") is not False
        )
        checks.expect(registered, "register_agent_info succeeded", str(register))
        if not registered:
            print(
                "\nHub is up, but no ENV is listening as "
                f"{args.env_id!r}. In the ENV window check --env-id "
                "(default env_1), and that it connected to the Hub."
            )
            return 1
        briefing = (register or {}).get("map") or {}
        home_bases = briefing.get("home_bases") or {}
        print(
            f"map {briefing.get('width')}x{briefing.get('height')}  "
            f"home_bases: {home_bases}"
        )
        if briefing.get("home_bases_meaning"):
            print(f"  meaning: {briefing['home_bases_meaning']}")
        checks.expect(
            isinstance(home_bases, dict) and len(home_bases) >= 2,
            "map.home_bases at join",
        )
        checks.expect(
            args.faction in home_bases and opponent in home_bases,
            f"map.home_bases has {args.faction} and {opponent}",
            str(home_bases),
        )

        own = await probe.call("get_faction_state", {"faction": args.faction})
        print_faction_state(own if isinstance(own, dict) else {})
        if not isinstance(own, dict):
            print(f"raw outcome: {own!r}")
        print("\nChecks (own faction):")
        check_own_payload(own, args.faction, checks)

        enemy = await probe.call("get_faction_state", {"faction": opponent})
        print(f"\nCross-faction query ({opponent}): {enemy}")
        print("Checks (enemy faction):")
        check_cross_faction(enemy, checks)

        if args.watch:
            print(
                "\n--watch: press Enter to query again after toggling key 1 "
                "(fog) in the ENV window. Ctrl+C to quit."
            )
            while True:
                await asyncio.to_thread(input)
                own = await probe.call(
                    "get_faction_state", {"faction": args.faction}
                )
                print_faction_state(own if isinstance(own, dict) else {})
                print("Checks (own faction):")
                round_checks = Check()
                check_own_payload(own, args.faction, round_checks)
                checks.failed += round_checks.failed
    except TimeoutError:
        print(
            "Timed out waiting for ENV. Start the ENV window and match --env-id "
            f"(current: {args.env_id})."
        )
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        await probe.disconnect()

    print()
    if checks.failed:
        print(f"{checks.failed} check(s) failed.")
        return 1
    print("All checks passed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-url", default=DEFAULT_HUB)
    parser.add_argument("--env-id", default="env_1")
    parser.add_argument("--agent-id", default="probe_faction_state")
    parser.add_argument("--faction", default="wei", choices=sorted(FACTIONS))
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Re-query on Enter so you can toggle fog (key 1) and compare.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
