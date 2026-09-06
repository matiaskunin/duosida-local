"""Async TCP transport with deterministic lifecycle semantics."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

from .codec import HANDSHAKE_1, build_handshake_2, extract_device_id
from .exceptions import DuosidaConnectionError, DuosidaProtocolError
from .framing import MessageFramer


class DuosidaTransport:
    """Own one persistent charger connection and expose complete messages."""

    def __init__(self, host: str, port: int = 9988, *, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.device_id: str | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._framer = MessageFramer()
        self._initial_messages: list[bytes] = []

    @property
    def connected(self) -> bool:
        """Return whether a usable writer exists."""

        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> str:
        """Open TCP, discover the identifier and complete both handshakes."""

        if self.connected and self.device_id is not None:
            return self.device_id
        await self.disconnect()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
            await self.write(HANDSHAKE_1)
            reader = self._reader
            if reader is None:
                raise DuosidaConnectionError("TCP reader was not created")
            response = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
            if not response:
                raise DuosidaConnectionError("charger closed during identification")
            frames = self._framer.feed(response)
            if not frames:
                raise DuosidaProtocolError(
                    "identification response did not contain a complete message"
                )
            self.device_id = extract_device_id(frames[0])
            self._initial_messages.extend(frames)
            await self.write(build_handshake_2(self.device_id))
            return self.device_id
        except (TimeoutError, OSError) as err:
            await self.disconnect()
            raise DuosidaConnectionError(f"cannot connect to {self.host}:{self.port}") from err
        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Close the stream and clear protocol state."""

        writer, self._writer = self._writer, None
        self._reader = None
        self.device_id = None
        self._initial_messages.clear()
        self._framer.clear()
        if writer is not None:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), timeout=self.timeout)

    async def write(self, data: bytes) -> None:
        """Write and drain one complete client message."""

        writer = self._writer
        if writer is None or writer.is_closing():
            raise DuosidaConnectionError("charger is not connected")
        try:
            writer.write(data)
            await asyncio.wait_for(writer.drain(), timeout=self.timeout)
        except (TimeoutError, OSError, ConnectionError) as err:
            raise DuosidaConnectionError("failed to write to charger") from err

    async def messages(self) -> AsyncIterator[bytes]:
        """Yield complete messages until the stream closes."""

        while self._initial_messages:
            yield self._initial_messages.pop(0)
        while True:
            reader = self._reader
            if reader is None:
                raise DuosidaConnectionError("charger is not connected")
            try:
                chunk = await reader.read(4096)
            except (OSError, ConnectionError) as err:
                raise DuosidaConnectionError("failed to read from charger") from err
            if not chunk:
                if self._framer.buffered_bytes:
                    raise DuosidaProtocolError("charger closed with a truncated message")
                raise DuosidaConnectionError("charger closed the TCP connection")
            for message in self._framer.feed(chunk):
                yield message
