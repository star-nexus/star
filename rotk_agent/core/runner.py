"""Connection lifecycle and the expedition loop.

The runner owns everything around the agent: the hub connection, the listeners
that turn incoming envelopes into `RemoteContext` state, and the outer loop that
relaunches `chat()` until the game is over.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, List, Optional

from protocol import AgentClient

from .agent import RoTKChatAgent
from .bridge import RemoteContext
from .console import console, console_system
from .errors import is_terminal_chat_result

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..modes.base import ModeStrategy

DEFAULT_HUB_URL = "ws://localhost:8000/ws/metaverse"
CONNECT_SETTLE_SECONDS = 1.0
EXPEDITION_GAP_SECONDS = 0.1
RECENT_MESSAGE_LIMIT = 10

AgentFactory = Callable[[], RoTKChatAgent]


class AgentRunner:
    """Connects to the hub and keeps one agent playing."""

    def __init__(
        self,
        agent_factory: AgentFactory,
        mode: "ModeStrategy",
        faction: str,
        hub_url: str = DEFAULT_HUB_URL,
        env_id: str = "env_1",
        agent_id: str = "agent_1",
    ):
        self.agent_factory = agent_factory
        self.mode = mode
        self.faction = faction
        self.hub_url = hub_url
        self.env_id = env_id
        self.agent_id = agent_id

        self.messages: List[str] = []
        self.current_agent: Optional[RoTKChatAgent] = None

        self.agent_client = AgentClient(hub_url, env_id, agent_id)
        RemoteContext.set_client(self.agent_client)
        RemoteContext.set_status({"self_status": {}, "env_status": {}})
        self._setup_hub_listeners()

    # ---- hub wiring ----

    def _setup_hub_listeners(self) -> None:
        def on_connect(data):
            message = f"✅ Agent connected successfully: {data}"
            console.print(message, style="cyan")
            self.messages.append(message)

        def on_message(data):
            payload = data.get("payload") or {}
            msg_type = payload.get("type")
            message = f"📨 Agent received message: {data}"

            if msg_type == "action":
                message += (
                    f"\n   action: {payload.get('action')}, "
                    f"parameters: {payload.get('parameters')}"
                )

            elif msg_type == "outcome":
                outcome = payload.get("outcome")
                RemoteContext.get_id_map().update({payload["id"]: outcome})
                RemoteContext.update_status(
                    self_status={f"Task{payload['id']}": outcome}
                )
                message += (
                    f"\n   outcome: {outcome}, "
                    f"type: {payload.get('outcome_type')}"
                )

            elif msg_type == "game_end_notification":
                console.print(
                    "🏁 Received game end notification, triggering LLM stats report",
                    style="yellow bold",
                )
                status = RemoteContext.update_status(game_ended=True)
                console.print(f"🔧 State updated: {status}", style="cyan")
                asyncio.create_task(self._report_now())
                message += f"\n    Game end notification: {payload}"

            elif msg_type == "turn_start":
                # Stored rather than acted on: the turn-based mode consumes it
                # so that turn bookkeeping stays in one place.
                RemoteContext.update_status(
                    turn_start={
                        "type": msg_type,
                        "faction": payload.get("faction"),
                        "turn_number": payload.get("turn_number"),
                        "timestamp": payload.get("timestamp"),
                        "message": payload.get("message"),
                    }
                )
                console.print(
                    f"📬 Received turn_start: faction={payload.get('faction')}, "
                    f"turn={payload.get('turn_number')}",
                    style="cyan",
                )

            self.messages.append(message)

        def on_disconnect(data):
            message = f"❌ Agent disconnected: {data}"
            console.print(message, style="red")
            self.messages.append(message)

        def on_error(data):
            payload = data.get("payload") or {}
            message = f"⚠️ Agent error: {data}"
            console.print(message, style="red")
            if "id" in payload:
                RemoteContext.get_id_map().update(
                    {payload["id"]: payload.get("error", "Unknown error")}
                )
            self.messages.append(message)

        self.agent_client.add_hub_listener("connect", on_connect)
        self.agent_client.add_hub_listener("message", on_message)
        self.agent_client.add_hub_listener("disconnect", on_disconnect)
        self.agent_client.add_hub_listener("error", on_error)

    async def _report_now(self) -> None:
        """Report stats the moment the game ends, without waiting for the loop."""
        if self.current_agent is None:
            console.print(
                "⚠️ Cannot trigger immediate report: no agent running", style="yellow"
            )
            return
        try:
            await self.current_agent.report_llm_stats()
        except Exception as e:
            console.print(f"❌ Immediate report failed: {e}", style="red")

    # ---- lifecycle ----

    async def connect(self) -> bool:
        console_system.print("🤖 Create Agent client", style="bold blue")
        console_system.print(f"📡 Server: {self.hub_url}")
        console_system.print(f"🌍 Environment ID: {self.env_id}")
        console_system.print(f"🆔 Agent ID: {self.agent_id}")
        console_system.print(f"⚔️ Faction: {self.faction}")
        console_system.print(f"🎮 Mode: {self.mode.name}")
        console_system.print("=" * 50)

        console_system.print("🔗 Connecting to server...", style="cyan")
        try:
            await self.agent_client.connect()
            console_system.print("✅ Agent connected successfully!", style="bold cyan")
            await asyncio.sleep(CONNECT_SETTLE_SECONDS)
            return True
        except Exception as e:
            console_system.print(f"❌ Connection failed: {e}", style="bold red")
            return False

    async def play(self) -> None:
        """Relaunch the agent until something says to stop."""
        expedition = 0
        while True:
            expedition += 1
            console_system.print(
                f"🔄 Launch expedition {expedition}...", style="bold cyan"
            )
            try:
                agent = self.agent_factory()
                self.current_agent = agent
                # The factory may reuse a mode; reset so turn-gate bookkeeping
                # cannot leak from a previous expedition (stale last-turn
                # numbers make the next turn_start look already-consumed).
                self.mode = agent.mode
                self.mode.reset()
                result = await agent.chat(self.mode.opening_prompt(self.faction))
                console_system.print(f"Chat task completed: {result}")

                if is_terminal_chat_result(result):
                    console_system.print(
                        f"🏁 Expedition {expedition} ended the run "
                        f"({result.get('reason')}), stopping.",
                        style="bold yellow",
                    )
                    break

                await asyncio.sleep(EXPEDITION_GAP_SECONDS)

            except KeyboardInterrupt:
                console_system.print("\n👋 User interrupted, exiting")
                break
            except Exception as e:
                console_system.print(f"❌ Expedition error: {e}", style="red")

    def show_summary(self) -> None:
        console_system.print("\n📊 Agent run summary", style="bold blue")
        console_system.print("=" * 25)
        console_system.print(f"📈 Total messages: {len(self.messages)}")
        console_system.print(f"🆔 Agent ID: {self.agent_id}")
        console_system.print(f"🌍 Environment ID: {self.env_id}")

        if self.current_agent is not None:
            console_system.print(
                f"📊 API stats: {self.current_agent.stats.get_api_stats()}"
            )
            console_system.print(
                f"📊 Errors: {self.current_agent.stats.get_error_breakdown()}"
            )

        if self.messages:
            console_system.print(
                f"\n📝 Message history (last {RECENT_MESSAGE_LIMIT}):"
            )
            for i, msg in enumerate(self.messages[-RECENT_MESSAGE_LIMIT:], 1):
                console_system.print(f"   {i}. {msg}")

    async def cleanup(self) -> None:
        console_system.print("\n🧹 Cleaning up connection...", style="cyan")
        try:
            if self.current_agent is not None:
                await self.current_agent.adapter.close()
            await self.agent_client.disconnect()
            console_system.print("✅ Agent connection closed", style="cyan")
        except Exception as e:
            console_system.print(f"⚠️ Error closing connection: {e}", style="red")

    async def run(self) -> None:
        """Connect, play, report, and always clean up."""
        try:
            if not await self.connect():
                return
            await self.play()
            self.show_summary()
        except KeyboardInterrupt:
            console_system.print("\n⚠️ User interrupted")
        except Exception as e:
            console_system.print(f"\n❌ Error during run: {e}", style="red")
        finally:
            await self.cleanup()


__all__ = ["AgentRunner", "DEFAULT_HUB_URL"]
