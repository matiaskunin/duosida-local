"""Small, schema-less Protobuf codec used by the observed Duosida protocol."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .exceptions import DuosidaProtocolError
from .models import Scalar


@dataclass(frozen=True, slots=True)
class ProtoField:
    """Decoded Protobuf field without an assumed semantic meaning."""

    number: int
    wire_type: int
    value: Scalar


class IncompleteMessageError(DuosidaProtocolError):
    """A Protobuf value ends before all declared bytes are available."""


def encode_varint(value: int) -> bytes:
    """Encode a non-negative integer as a Protobuf varint."""

    if value < 0:
        raise ValueError("varints must be non-negative")
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def decode_varint(data: bytes | bytearray, offset: int = 0) -> tuple[int, int]:
    """Decode a Protobuf varint and return ``(value, new_offset)``."""

    result = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise IncompleteMessageError("truncated varint")
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, offset
    raise DuosidaProtocolError("varint exceeds 64 bits")


def encode_varint_field(number: int, value: int) -> bytes:
    """Encode a varint field."""

    return encode_varint(number << 3) + encode_varint(value)


def encode_bytes_field(number: int, value: bytes) -> bytes:
    """Encode a length-delimited field."""

    key = encode_varint((number << 3) | 2)
    return key + encode_varint(len(value)) + value


def encode_string_field(number: int, value: str) -> bytes:
    """Encode a UTF-8 string field."""

    return encode_bytes_field(number, value.encode("utf-8"))


def decode_fields(data: bytes) -> tuple[ProtoField, ...]:
    """Decode supported wire types while preserving ordering and repetition."""

    fields: list[ProtoField] = []
    offset = 0
    while offset < len(data):
        key, offset = decode_varint(data, offset)
        number, wire_type = key >> 3, key & 0x07
        value: Scalar
        if number == 0:
            raise DuosidaProtocolError("field number zero is invalid")
        if wire_type == 0:
            value, offset = decode_varint(data, offset)
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise IncompleteMessageError("truncated fixed64")
            value = data[offset:end]
            offset = end
        elif wire_type == 2:
            length, offset = decode_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise IncompleteMessageError("truncated length-delimited field")
            value = bytes(data[offset:end])
            offset = end
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise IncompleteMessageError("truncated fixed32")
            value = bytes(data[offset:end])
            offset = end
        else:
            raise DuosidaProtocolError(f"unsupported Protobuf wire type {wire_type}")
        fields.append(ProtoField(number, wire_type, value))
    return tuple(fields)


def first_field(fields: tuple[ProtoField, ...], number: int) -> ProtoField | None:
    """Return the first field with ``number``."""

    return next((field for field in fields if field.number == number), None)


def bytes_value(field: ProtoField | None) -> bytes:
    """Return a field as bytes or raise a protocol error."""

    if field is None or not isinstance(field.value, bytes):
        raise DuosidaProtocolError("expected a length-delimited field")
    return field.value


def text_value(field: ProtoField | None) -> str:
    """Decode a UTF-8 field strictly."""

    try:
        return bytes_value(field).decode("utf-8")
    except UnicodeDecodeError as err:
        raise DuosidaProtocolError("invalid UTF-8 protocol string") from err


def float32_value(field: ProtoField | None) -> float:
    """Interpret an observed fixed32 measurement as little-endian float32."""

    value = bytes_value(field)
    if len(value) != 4:
        raise DuosidaProtocolError("expected four bytes for fixed32")
    return float(struct.unpack("<f", value)[0])
