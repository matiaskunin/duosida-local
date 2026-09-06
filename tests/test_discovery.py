from __future__ import annotations

import asyncio

from duosida_local import DiscoveredCharger
from duosida_local.discovery import (
    DISCOVERY_DESTINATION_PORT,
    DISCOVERY_PAYLOAD,
    DISCOVERY_SOURCE_PORT,
    _identify,
    discover_chargers,
)
from duosida_local.exceptions import DuosidaConnectionError


class FakeDatagramTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.closed = False

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))

    def close(self) -> None:
        self.closed = True


class FakeLoop:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls = 0
        self.transport = FakeDatagramTransport()

    async def create_datagram_endpoint(self, factory, **kwargs):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise OSError("port busy")
        protocol = factory()
        protocol.datagram_received(
            b"smart_wifi,aa-bb-cc-dd-ee-ff,firmware\x00", ("192.0.2.20", 48899)
        )
        protocol.datagram_received(b"duplicate", ("192.0.2.20", 48899))
        return self.transport, protocol


async def test_discovery_parses_deduplicates_and_sends_broadcast(monkeypatch) -> None:
    loop = FakeLoop()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    devices = await discover_chargers(timeout=0, identify=False)
    assert devices == (
        DiscoveredCharger(
            host="192.0.2.20",
            mac="aa:bb:cc:dd:ee:ff",
            raw_response="smart_wifi,aa-bb-cc-dd-ee-ff,firmware",
        ),
    )
    assert loop.transport.sent == [
        (DISCOVERY_PAYLOAD, ("255.255.255.255", DISCOVERY_DESTINATION_PORT))
    ]
    assert loop.transport.closed


async def test_discovery_falls_back_to_ephemeral_source_port(monkeypatch) -> None:
    loop = FakeLoop(fail_first=True)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    await discover_chargers(timeout=0, identify=False)
    assert loop.calls == 2
    assert DISCOVERY_SOURCE_PORT == 48890


async def test_identify_success_and_failure(monkeypatch) -> None:
    class FakeTransport:
        should_fail = False

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def connect(self) -> str:
            if self.should_fail:
                raise DuosidaConnectionError("offline")
            return "0000000000000000000"

        async def disconnect(self) -> None:
            return None

    monkeypatch.setattr("duosida_local.discovery.DuosidaTransport", FakeTransport)
    device = DiscoveredCharger(host="192.0.2.20")
    assert (await _identify(device, 0.1)).device_id == "0000000000000000000"
    FakeTransport.should_fail = True
    assert await _identify(device, 0.1) == device
