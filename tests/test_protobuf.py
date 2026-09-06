from __future__ import annotations

import pytest

from duosida_local.exceptions import DuosidaProtocolError
from duosida_local.protobuf import (
    IncompleteMessageError,
    ProtoField,
    bytes_value,
    decode_fields,
    decode_varint,
    encode_bytes_field,
    encode_string_field,
    encode_varint,
    encode_varint_field,
    float32_value,
    text_value,
)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 300, 2**32, 2**63 - 1])
def test_varint_round_trip(value: int) -> None:
    encoded = encode_varint(value)
    assert decode_varint(encoded) == (value, len(encoded))


def test_rejects_negative_and_oversized_varints() -> None:
    with pytest.raises(ValueError):
        encode_varint(-1)
    with pytest.raises(DuosidaProtocolError):
        decode_varint(b"\x80" * 10 + b"\x00")


@pytest.mark.parametrize("payload", [b"\x80", b"\x0a\x05ab", b"\x0d\x00", b"\x09\x00"])
def test_rejects_truncated_fields(payload: bytes) -> None:
    with pytest.raises(IncompleteMessageError):
        decode_fields(payload)


def test_decodes_supported_wire_types_and_repeated_fields() -> None:
    message = (
        encode_varint_field(1, 7)
        + encode_string_field(2, "ok")
        + b"\x09"
        + b"12345678"
        + b"\x15"
        + b"1234"
        + encode_varint_field(1, 8)
    )
    fields = decode_fields(message)
    assert [(field.number, field.wire_type) for field in fields] == [
        (1, 0),
        (2, 2),
        (1, 1),
        (2, 5),
        (1, 0),
    ]
    assert fields[1].value == b"ok"


def test_rejects_invalid_field_and_wire_type() -> None:
    with pytest.raises(DuosidaProtocolError, match="field number zero"):
        decode_fields(b"\x00")
    with pytest.raises(DuosidaProtocolError, match="wire type"):
        decode_fields(b"\x0b")


def test_bytes_field_has_declared_length() -> None:
    assert encode_bytes_field(3, b"abc") == b"\x1a\x03abc"


def test_typed_value_helpers_reject_wrong_data() -> None:
    with pytest.raises(DuosidaProtocolError, match="length-delimited"):
        bytes_value(None)
    with pytest.raises(DuosidaProtocolError, match="UTF-8"):
        text_value(ProtoField(1, 2, b"\xff"))
    with pytest.raises(DuosidaProtocolError, match="four bytes"):
        float32_value(ProtoField(1, 2, b"x"))
