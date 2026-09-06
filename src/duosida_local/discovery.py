"""Local UDP discovery for Duosida Wi-Fi chargers."""

from __future__ import annotations

import asyncio
import re
import socket
from dataclasses import replace

from .exceptions import DuosidaConnectionError
from .models import DiscoveredCharger
from .transport import DuosidaTransport

DISCOVERY_SOURCE_PORT = 48890
DISCOVERY_DESTINATION_PORT = 48899
DISCOVERY_PAYLOAD = b"smart_chargepile_search\x00"
_MAC = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.responses: list[tuple[bytes, tuple[str, int]]] = []

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.responses.append((data, addr))


async def discover_chargers(
    *,
    timeout: float = 3.0,
    interface: str = "0.0.0.0",
    destination: str = "255.255.255.255",
    identify: bool = True,
) -> tuple[DiscoveredCharger, ...]:
    """Broadcast the vendor discovery packet and optionally identify replies."""

    loop = asyncio.get_running_loop()
    protocol = _DiscoveryProtocol()
    transport: asyncio.DatagramTransport | None = None
    try:
        try:
            created_transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                local_addr=(interface, DISCOVERY_SOURCE_PORT),
                allow_broadcast=True,
                family=socket.AF_INET,
            )
        except OSError:
            created_transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                local_addr=(interface, 0),
                allow_broadcast=True,
                family=socket.AF_INET,
            )
        transport = created_transport
        transport.sendto(DISCOVERY_PAYLOAD, (destination, DISCOVERY_DESTINATION_PORT))
        await asyncio.sleep(timeout)
    finally:
        if transport is not None:
            transport.close()

    by_host: dict[str, DiscoveredCharger] = {}
    for raw, (host, _) in protocol.responses:
        text = raw.rstrip(b"\x00").decode("utf-8", errors="replace")
        mac_match = _MAC.search(text)
        candidate = DiscoveredCharger(
            host=host,
            mac=mac_match.group(0).lower().replace("-", ":") if mac_match else None,
            raw_response=text,
        )
        current = by_host.get(host)
        if current is None or (current.mac is None and candidate.mac is not None):
            by_host[host] = candidate

    if identify:
        identified = await asyncio.gather(
            *(_identify(device, timeout) for device in by_host.values())
        )
        by_host = {device.host: device for device in identified}
    return tuple(by_host[host] for host in sorted(by_host))


async def _identify(device: DiscoveredCharger, timeout: float) -> DiscoveredCharger:
    transport = DuosidaTransport(device.host, device.port, timeout=timeout)
    try:
        device_id = await transport.connect()
    except DuosidaConnectionError:
        return device
    finally:
        await transport.disconnect()
    return replace(device, device_id=device_id)
