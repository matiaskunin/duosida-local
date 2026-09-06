from __future__ import annotations

import asyncio

import pytest

from duosida_local.codec import HANDSHAKE_1, build_handshake_2
from duosida_local.exceptions import DuosidaConnectionError, DuosidaProtocolError
from duosida_local.protobuf import encode_string_field, encode_varint_field
from duosida_local.transport import DuosidaTransport

DEVICE_ID = "0000000000000000000"
IDENTIFICATION = encode_string_field(100, DEVICE_ID) + encode_varint_field(101, 1)


class FakeReader:
    def __init__(self, reads: list[bytes | BaseException]) -> None:
        self.reads = reads

    async def read(self, _: int) -> bytes:
        if not self.reads:
            await asyncio.sleep(3600)
        item = self.reads.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeWriter:
    def __init__(self) -> None:
        self.data: list[bytes] = []
        self.closing = False
        self.drain_error: BaseException | None = None

    def write(self, data: bytes) -> None:
        self.data.append(data)

    async def drain(self) -> None:
        if self.drain_error:
            raise self.drain_error

    def is_closing(self) -> bool:
        return self.closing

    def close(self) -> None:
        self.closing = True

    async def wait_closed(self) -> None:
        return None


async def test_transport_handshake_and_stream(monkeypatch, captures: dict[str, str]) -> None:
    status = bytes.fromhex(captures["available"])
    reader = FakeReader([IDENTIFICATION, status[:30], status[30:], b""])
    writer = FakeWriter()

    async def open_connection(host: str, port: int):
        assert (host, port) == ("192.0.2.10", 9988)
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    transport = DuosidaTransport("192.0.2.10", timeout=0.1)
    assert await transport.connect() == DEVICE_ID
    assert writer.data == [HANDSHAKE_1, build_handshake_2(DEVICE_ID)]
    messages = transport.messages()
    assert await anext(messages) == IDENTIFICATION
    assert await anext(messages) == status
    with pytest.raises(DuosidaConnectionError, match="closed"):
        await anext(messages)
    await transport.disconnect()
    assert writer.closing


async def test_transport_rejects_empty_and_invalid_identification(monkeypatch) -> None:
    for response, error in ((b"", DuosidaConnectionError), (b"garbage", DuosidaProtocolError)):
        writer = FakeWriter()

        async def open_connection(*_, response=response, writer=writer):
            return FakeReader([response]), writer

        monkeypatch.setattr(asyncio, "open_connection", open_connection)
        transport = DuosidaTransport("192.0.2.10", timeout=0.1)
        with pytest.raises(error):
            await transport.connect()
        assert not transport.connected


async def test_transport_wraps_open_write_and_read_errors(monkeypatch) -> None:
    async def failed_open(*_):
        raise OSError("no route")

    monkeypatch.setattr(asyncio, "open_connection", failed_open)
    transport = DuosidaTransport("192.0.2.10", timeout=0.1)
    with pytest.raises(DuosidaConnectionError, match="cannot connect"):
        await transport.connect()
    with pytest.raises(DuosidaConnectionError, match="not connected"):
        await transport.write(b"x")

    reader, writer = FakeReader([IDENTIFICATION, OSError("lost")]), FakeWriter()

    async def valid_open(*_):
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", valid_open)
    await transport.connect()
    writer.drain_error = OSError("lost")
    with pytest.raises(DuosidaConnectionError, match="write"):
        await transport.write(b"x")
    writer.drain_error = None
    messages = transport.messages()
    await anext(messages)
    with pytest.raises(DuosidaConnectionError, match="read"):
        await anext(messages)
    await transport.disconnect()


async def test_transport_reports_truncated_tail(monkeypatch) -> None:
    writer = FakeWriter()

    async def open_connection(*_):
        return FakeReader([IDENTIFICATION, b"partial", b""]), writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    transport = DuosidaTransport("192.0.2.10", timeout=0.1)
    await transport.connect()
    messages = transport.messages()
    await anext(messages)
    with pytest.raises(DuosidaProtocolError, match="truncated"):
        await anext(messages)
    await transport.disconnect()
