"""
Multi-agent team example — two LLM agents share a single faction.

This demonstrates the multi-agent collaboration primitives added in item 10:

    1. Each agent registers under faction "wei" with a distinct `agent_id`.
    2. Both agents query `list_team` to learn who else is on their team.
    3. The "vanguard" agent claims the front-line units (0, 1, 2) and the
       "rearguard" agent claims the rest. After this, `move`/`attack` for
       claimed units is rejected for the non-owner with a 2005 error.
    4. Vanguard broadcasts a tactical note. Rearguard drains its inbox
       and reads the broadcast.

This is a deliberately minimal show-and-tell script — it does NOT run a
full game loop. Use it as a recipe when writing real coordinated agents.

Prerequisites
-------------

    * A running Star Hub (`python framework/cli.py hub`) — typically on
      `ws://localhost:8000/ws/metaverse`.
    * A running RoTK environment (`python -m rotk_env.main --headless ...`)
      with `--env-id env_demo` (or whatever you pass below).

Usage
-----

    python examples/multiagent_team.py \
        --env-id env_demo \
        --hub-url ws://localhost:8000/ws/metaverse

"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import AgentClient


async def run_agent(
    hub_url: str,
    env_id: str,
    agent_id: str,
    role: str,
    units_to_claim: list[int],
) -> None:
    """Drive one agent through register → claim → broadcast/read."""
    client = AgentClient(hub_url, env_id, agent_id)
    await client.connect()
    print(f"[{agent_id}] connected as {role}")

    # 1) Register so the env knows our faction.
    reg_id = await client.send_action(
        "register_agent_info",
        {
            "faction": "wei",
            "provider": "demo",
            "model_id": f"demo-{role}",
            "base_url": "http://localhost",
            "agent_id": agent_id,
            "note": f"multi-agent team demo: {role}",
        },
    )
    print(f"[{agent_id}] sent register_agent_info (request_id={reg_id})")

    # Give the env time to broadcast back its handshake; in a real agent
    # you'd await the response via your tool-execution loop.
    await asyncio.sleep(0.5)

    # 2) Ask who's on our team.
    list_id = await client.send_action("list_team", {})
    print(f"[{agent_id}] sent list_team (request_id={list_id})")

    # 3) Claim our portion of the army.
    claim_id = await client.send_action(
        "claim_units",
        {"unit_ids": units_to_claim, "exclusive": True},
    )
    print(
        f"[{agent_id}] sent claim_units (request_id={claim_id}) "
        f"for units {units_to_claim}"
    )

    # 4) Team chat: vanguard broadcasts, rearguard reads.
    if role == "vanguard":
        await asyncio.sleep(1.0)  # give rearguard time to register first
        broadcast_id = await client.send_action(
            "broadcast_to_team",
            {
                "text": "Engaging center hex. Hold the flank.",
                "metadata": {"priority": "high", "hex": [0, 0]},
            },
        )
        print(f"[{agent_id}] broadcast sent (request_id={broadcast_id})")
    else:
        await asyncio.sleep(2.0)  # wait for vanguard's broadcast
        read_id = await client.send_action("read_team_messages", {})
        print(f"[{agent_id}] requested inbox (request_id={read_id})")

    await asyncio.sleep(2.0)
    await client.disconnect()
    print(f"[{agent_id}] disconnected")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-url", default="ws://localhost:8000/ws/metaverse")
    parser.add_argument("--env-id", default="env_demo")
    args = parser.parse_args()

    # Vanguard takes front-line units; Rearguard takes the rest.
    # Adjust to match the unit ids in your scenario.
    vanguard_task = asyncio.create_task(
        run_agent(
            args.hub_url,
            args.env_id,
            agent_id="wei_vanguard",
            role="vanguard",
            units_to_claim=[0, 1, 2],
        )
    )
    # Stagger the launches so the registration order is deterministic.
    await asyncio.sleep(0.3)
    rearguard_task = asyncio.create_task(
        run_agent(
            args.hub_url,
            args.env_id,
            agent_id="wei_rearguard",
            role="rearguard",
            units_to_claim=[3, 4],
        )
    )

    await asyncio.gather(vanguard_task, rearguard_task)


if __name__ == "__main__":
    asyncio.run(main())
