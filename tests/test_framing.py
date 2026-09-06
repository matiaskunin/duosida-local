from __future__ import annotations

import pytest

from duosida_local.exceptions import DuosidaProtocolError
from duosida_local.framing import MessageFramer


def test_fragmented_message(captures: dict[str, str]) -> None:
    message = bytes.fromhex(captures["available"])
    framer = MessageFramer()
    assert framer.feed(message[:17]) == []
    assert framer.buffered_bytes == 17
    assert framer.feed(message[17:-1]) == []
    assert framer.feed(message[-1:]) == [message]
    assert framer.buffered_bytes == 0


def test_concatenated_messages_and_partial_tail(captures: dict[str, str]) -> None:
    first = bytes.fromhex(captures["identity"])
    second = bytes.fromhex(captures["available"])
    third = bytes.fromhex(captures["stopped_connected"])
    framer = MessageFramer()
    assert framer.feed(first + second + third[:20]) == [first, second]
    assert framer.feed(third[20:]) == [third]


def test_clear_and_buffer_limit() -> None:
    framer = MessageFramer(max_buffer_size=3)
    framer.feed(b"abc")
    framer.clear()
    assert framer.buffered_bytes == 0
    with pytest.raises(DuosidaProtocolError, match="safety limit"):
        framer.feed(b"abcd")
    assert framer.buffered_bytes == 0


def test_incomplete_terminal_varint_is_retained(captures: dict[str, str]) -> None:
    message = bytes.fromhex(captures["available"])
    framer = MessageFramer()
    assert framer.feed(message[:-1] + b"\x80") == []
    assert framer.buffered_bytes == len(message)
