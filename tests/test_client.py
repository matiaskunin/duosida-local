from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from duosida_local import (
    ChargerState,
    CommandStatus,
    DuosidaClient,
    DuosidaCommandError,
    DuosidaCommandUnconfirmedError,
    DuosidaConnectionError,
)


class FakeTransport:
    def __init__(self, identity: bytes, available: bytes, charging: bytes, stopped: bytes) -> None:
        self.connected = False
        self.device_id: str | None = None
        self.messages_queue: asyncio.Queue[bytes | BaseException] = asyncio.Queue()
        self.writes: list[bytes] = []
        self.identity = identity
        self.available = available
        self.charging = charging
        self.stopped = stopped
        self.command_responses = True

    async def connect(self) -> str:
        self.connected = True
        self.device_id = "0000000000000000000"
        await self.messages_queue.put(self.identity)
        await self.messages_queue.put(self.available)
        return self.device_id

    async def disconnect(self) -> None:
        self.connected = False
        self.device_id = None

    async def write(self, data: bytes) -> None:
        if not self.connected:
            raise DuosidaConnectionError("not connected")
        self.writes.append(data)
        if self.command_responses and data.startswith(b"\x92\x02"):
            await self.messages_queue.put(self.charging)
        elif self.command_responses and data.startswith(b"\xa2\x02"):
            await self.messages_queue.put(self.stopped)

    async def messages(self) -> AsyncIterator[bytes]:
        while self.connected:
            item = await self.messages_queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item


@pytest.fixture
def fake_transport(captures: dict[str, str]) -> FakeTransport:
    return FakeTransport(
        bytes.fromhex(captures["identity"]),
        bytes.fromhex(captures["available"]),
        bytes.fromhex(captures["charging_6a"]),
        bytes.fromhex(captures["stopped_connected"]),
    )


class SilentTransport(FakeTransport):
    async def connect(self) -> str:
        self.connected = True
        self.device_id = "0000000000000000000"
        return self.device_id


async def _connected_client(fake: FakeTransport, *, command_timeout: float = 0.1) -> DuosidaClient:
    client = DuosidaClient(
        "192.0.2.10",
        timeout=0.1,
        command_timeout=command_timeout,
        transport=fake,  # type: ignore[arg-type]
    )
    await client.connect()
    for _ in range(20):
        if client.latest_status is not None:
            break
        await asyncio.sleep(0)
    return client


async def test_context_manager_identity_status_and_callback(fake_transport: FakeTransport) -> None:
    client = DuosidaClient("192.0.2.10", transport=fake_transport)  # type: ignore[arg-type]
    seen = []
    unsubscribe = client.add_state_callback(seen.append)
    async with client:
        assert client.connected
        assert client.device_id == "0000000000000000000"
        assert (await client.get_identity()).model == "DUOSIDA Mode3@32A"
        assert await client.connect() == await client.get_identity()
        for _ in range(20):
            if seen:
                break
            await asyncio.sleep(0)
        assert seen[-1].state is ChargerState.AVAILABLE
        unsubscribe()
    assert not client.connected


async def test_state_stream_gets_latest_snapshot(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)
    stream = client.states()
    status = await anext(stream)
    assert status.state is ChargerState.AVAILABLE
    await stream.aclose()
    await client.disconnect()


async def test_commands_are_serialized_and_confirmed(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)
    current = await client.set_max_current(6)
    assert current.status is CommandStatus.SENT_UNCONFIRMED
    assert current.requested_value == 6

    start = await client.start_charging()
    assert start.status is CommandStatus.CONFIRMED
    assert start.observed_state is ChargerState.CHARGING
    assert client.latest_status is not None and client.latest_status.charging

    already_charging = await client.start_charging()
    assert already_charging.observed_state is ChargerState.CHARGING

    stop = await client.stop_charging()
    assert stop.observed_state is ChargerState.FINISHED
    assert len(fake_transport.writes) == 4
    assert len({receipt.sequence for receipt in (current, start, stop)}) == 3
    await client.disconnect()


async def test_concurrent_current_commands_have_unique_sequences(
    fake_transport: FakeTransport,
) -> None:
    client = await _connected_client(fake_transport)
    receipts = await asyncio.gather(*(client.set_max_current(amps) for amps in (6, 7, 8, 9)))
    assert len({receipt.sequence for receipt in receipts}) == 4
    await client.disconnect()


async def test_invalid_current_is_typed_command_error(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)
    with pytest.raises(DuosidaCommandError, match="between 6 and 32"):
        await client.set_max_current(5)
    await client.disconnect()


async def test_unconfirmed_transition_raises(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport, command_timeout=0.001)
    fake_transport.command_responses = False
    with pytest.raises(DuosidaCommandUnconfirmedError, match="no compatible"):
        await client.start_charging()
    await client.disconnect()


async def test_reader_failure_reaches_state_subscriber(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)
    stream = client.states()
    await anext(stream)
    await fake_transport.messages_queue.put(DuosidaConnectionError("lost"))
    with pytest.raises(DuosidaConnectionError, match="lost"):
        await anext(stream)
    await stream.aclose()
    await client.disconnect()


async def test_disconnected_commands_fail(fake_transport: FakeTransport) -> None:
    client = DuosidaClient("192.0.2.10", transport=fake_transport)  # type: ignore[arg-type]
    assert client.latest_status is None
    with pytest.raises(DuosidaConnectionError, match="not connected"):
        await client.set_max_current(6)


async def test_async_callback_and_text_telemetry(
    fake_transport: FakeTransport, captures: dict[str, str]
) -> None:
    client = await _connected_client(fake_transport)
    callback_called = asyncio.Event()

    async def callback(_status: object) -> None:
        callback_called.set()

    client.add_state_callback(callback)
    await fake_transport.messages_queue.put(bytes.fromhex(captures["text_telemetry"]))
    await asyncio.wait_for(callback_called.wait(), timeout=0.1)
    for _ in range(20):
        if client.latest_status is not None and client.latest_status.power == 1546.55:
            break
        await asyncio.sleep(0)
    assert client.latest_status is not None
    assert client.latest_status.power == pytest.approx(1546.55)
    await client.disconnect()


async def test_latest_only_subscriber_queue(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)
    stream = client.states()
    await anext(stream)
    await fake_transport.messages_queue.put(fake_transport.charging)
    await fake_transport.messages_queue.put(fake_transport.stopped)
    for _ in range(20):
        if client.latest_status is not None and client.latest_status.state is ChargerState.FINISHED:
            break
        await asyncio.sleep(0)
    assert (await anext(stream)).state is ChargerState.FINISHED
    await client.disconnect()


async def test_connection_timeout_without_identity(captures: dict[str, str]) -> None:
    silent = SilentTransport(
        bytes.fromhex(captures["identity"]),
        bytes.fromhex(captures["available"]),
        bytes.fromhex(captures["charging_6a"]),
        bytes.fromhex(captures["stopped_connected"]),
    )
    client = DuosidaClient(
        "192.0.2.10",
        timeout=0.001,
        transport=silent,  # type: ignore[arg-type]
    )
    with pytest.raises(Exception, match="did not announce identity"):
        await client.connect()


async def test_generic_write_failure_is_command_error(fake_transport: FakeTransport) -> None:
    client = await _connected_client(fake_transport)

    async def fail_write(_data: bytes) -> None:
        raise RuntimeError("boom")

    fake_transport.write = fail_write  # type: ignore[method-assign]
    with pytest.raises(DuosidaCommandError, match="could not send"):
        await client.set_max_current(6)
    await client.disconnect()
