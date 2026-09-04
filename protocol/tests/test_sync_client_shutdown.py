import asyncio

from protocol.star_client_v2.sync_client import SyncWebSocketClient


class _ConcreteSyncClient(SyncWebSocketClient):
    def url(self) -> str:
        return self.server_url


class _FakeWebSocket:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeStopEvent:
    def __init__(self):
        self.was_set = False

    def set(self):
        self.was_set = True


class _FakeThread:
    def __init__(self):
        self.alive = True
        self.joined = False

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined = True
        self.alive = False


def _bare_client() -> SyncWebSocketClient:
    client = object.__new__(_ConcreteSyncClient)
    client.websocket = None
    client._loop = None
    client._loop_thread = None
    client._stop_event = None
    client._loop_ready = None
    client._message_task = None
    client._heartbeat_task = None
    client.connected = False
    client.hub_event_handlers = {}
    return client


def test_async_disconnect_cancels_and_awaits_background_tasks():
    async def scenario():
        client = _bare_client()
        websocket = _FakeWebSocket()
        client.websocket = websocket
        client.connected = True

        message_task = asyncio.create_task(asyncio.sleep(60))
        heartbeat_task = asyncio.create_task(asyncio.sleep(60))
        client._message_task = message_task
        client._heartbeat_task = heartbeat_task

        await client._async_disconnect()

        assert client.connected is False
        assert websocket.closed is True
        assert client.websocket is None
        assert message_task.done()
        assert heartbeat_task.done()
        assert client._message_task is None
        assert client._heartbeat_task is None

    asyncio.run(scenario())


def test_disconnect_stops_loop_thread_even_if_connection_already_false():
    client = _bare_client()
    stop_event = _FakeStopEvent()
    thread = _FakeThread()
    client._stop_event = stop_event
    client._loop_thread = thread
    client.connected = False

    client.disconnect()

    assert stop_event.was_set is True
    assert thread.joined is True
    assert client._loop_thread is None
