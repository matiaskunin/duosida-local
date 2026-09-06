"""Incremental framing for the unlength-prefixed Duosida TCP stream."""

from __future__ import annotations

import re

from .exceptions import DuosidaProtocolError
from .protobuf import IncompleteMessageError, decode_varint

_MESSAGE_END = re.compile(rb"\xa2\x06\x13([0-9]{19})\xa8\x06")


class MessageFramer:
    """Split frames by their observed field-100/field-101 terminator.

    The protocol has no published framing specification. Every captured outer
    message ends with a 19-digit field 100 followed by varint field 101. The
    heuristic is isolated here so it can be replaced if an official rule is
    discovered.
    """

    def __init__(self, *, max_buffer_size: int = 1_048_576) -> None:
        self._buffer = bytearray()
        self._max_buffer_size = max_buffer_size

    @property
    def buffered_bytes(self) -> int:
        """Number of incomplete bytes retained."""

        return len(self._buffer)

    def clear(self) -> None:
        """Discard incomplete bytes."""

        self._buffer.clear()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Append a TCP chunk and return every complete protocol message."""

        self._buffer.extend(chunk)
        if len(self._buffer) > self._max_buffer_size:
            self.clear()
            raise DuosidaProtocolError("framing buffer exceeded its safety limit")

        frames: list[bytes] = []
        consumed = 0
        snapshot = bytes(self._buffer)
        for match in _MESSAGE_END.finditer(snapshot):
            try:
                _, end = decode_varint(snapshot, match.end())
            except IncompleteMessageError:
                break
            frames.append(snapshot[consumed:end])
            consumed = end
        if consumed:
            del self._buffer[:consumed]
        return frames
