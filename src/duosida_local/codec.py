"""Semantic codec for the verified subset of the charger protocol."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import DuosidaProtocolError
from .models import ChargerIdentity, ChargerState, ChargerStatus, RawField
from .protobuf import (
    bytes_value,
    decode_fields,
    encode_bytes_field,
    encode_string_field,
    encode_varint_field,
    first_field,
    float32_value,
    text_value,
)

HANDSHAKE_1 = bytes.fromhex("a2030408001000a20603494f53a80600")
HANDSHAKE_2_PREFIX = bytes.fromhex("1a0a089ee6da910d10001800")
HANDSHAKE_2_SUFFIX = bytes.fromhex("a8069e818040")

_STATE_BY_CODE = {
    0: ChargerState.AVAILABLE,
    1: ChargerState.PREPARING,
    2: ChargerState.CHARGING,
    3: ChargerState.COOLING,
    4: ChargerState.SUSPENDED_EV,
    5: ChargerState.FINISHED,
    6: ChargerState.HOLIDAY,
}
_KNOWN_STATUS_FIELDS = {1, 2, 3, 4, 8, 9, 17}


@dataclass(frozen=True, slots=True)
class TextTelemetry:
    """Optional human-readable telemetry message."""

    current: float
    energy: float
    power: float
    station_temperature: float
    voltage: float


def build_handshake_2(device_id: str) -> bytes:
    """Build the second handshake using the discovered device identifier."""

    _validate_device_id(device_id)
    return HANDSHAKE_2_PREFIX + encode_string_field(100, device_id) + HANDSHAKE_2_SUFFIX


def extract_device_id(message: bytes) -> str:
    """Extract outer field 100."""

    device_id = text_value(first_field(decode_fields(message), 100))
    _validate_device_id(device_id)
    return device_id


def parse_identity(message: bytes) -> ChargerIdentity | None:
    """Parse an identity message, returning ``None`` for other families."""

    outer = decode_fields(message)
    identity_field = first_field(outer, 4)
    if identity_field is None:
        return None
    identity = decode_fields(bytes_value(identity_field))
    model_field = first_field(identity, 2)
    id_field = first_field(identity, 3)
    manufacturer_field = first_field(identity, 4)
    firmware_field = first_field(identity, 5)
    if None in (model_field, id_field, manufacturer_field, firmware_field):
        return None
    return ChargerIdentity(
        device_id=text_value(id_field),
        model=text_value(model_field),
        manufacturer=text_value(manufacturer_field),
        firmware=text_value(firmware_field),
    )


def parse_status(message: bytes) -> ChargerStatus | None:
    """Parse ``DataVendorStatusReq`` from one complete outer message."""

    outer = decode_fields(message)
    wrapper_field = first_field(outer, 16)
    if wrapper_field is None:
        return None
    wrapper = decode_fields(bytes_value(wrapper_field))
    message_type_field = first_field(wrapper, 2)
    if message_type_field is None or text_value(message_type_field) != "DataVendorStatusReq":
        return None
    payload = decode_fields(bytes_value(first_field(wrapper, 10)))

    raw_state_field = first_field(payload, 17)
    sequence_field = first_field(outer, 101)
    if raw_state_field is None or not isinstance(raw_state_field.value, int):
        raise DuosidaProtocolError("status has no integer connection state")
    if sequence_field is None or not isinstance(sequence_field.value, int):
        raise DuosidaProtocolError("status has no integer sequence")

    voltage = float32_value(first_field(payload, 1))
    current = float32_value(first_field(payload, 2))
    raw_state = raw_state_field.value
    unknown = tuple(
        RawField(field.number, field.wire_type, field.value)
        for field in payload
        if field.number not in _KNOWN_STATUS_FIELDS
    )
    return ChargerStatus(
        state=_STATE_BY_CODE.get(raw_state, ChargerState.UNKNOWN),
        raw_state=raw_state,
        voltage=voltage,
        current=current,
        power=voltage * current,
        total_energy=float32_value(first_field(payload, 3)),
        session_energy=float32_value(first_field(payload, 4)),
        station_temperature=float32_value(first_field(payload, 8)),
        cp_voltage=float32_value(first_field(payload, 9)),
        vehicle_connected=raw_state != 0,
        sequence=sequence_field.value,
        unknown_fields=unknown,
    )


def parse_text_telemetry(message: bytes) -> TextTelemetry | None:
    """Parse the observed outer-field-32 numeric text telemetry family."""

    outer = decode_fields(message)
    telemetry_field = first_field(outer, 32)
    if telemetry_field is None:
        return None
    envelope = decode_fields(bytes_value(telemetry_field))
    records_field = first_field(envelope, 3)
    if records_field is None:
        return None
    records = decode_fields(bytes_value(records_field))
    readings: list[float] = []
    for record_field in (field for field in records if field.number == 2):
        record = decode_fields(bytes_value(record_field))
        value_field = first_field(record, 1)
        if value_field is None:
            continue
        try:
            readings.append(float(text_value(value_field)))
        except ValueError as err:
            raise DuosidaProtocolError("non-numeric text telemetry") from err
    if len(readings) < 5:
        return None
    return TextTelemetry(*readings[:5])


def build_set_max_current(device_id: str, sequence: int, amps: int) -> bytes:
    """Build the write-only maximum-current configuration command."""

    if not 6 <= amps <= 32:
        raise ValueError("maximum current must be between 6 and 32 A")
    payload = encode_string_field(1, "VendorMaxWorkCurrent") + encode_string_field(2, str(amps))
    return _outer_command(10, payload, device_id, sequence)


def build_start_command(device_id: str, sequence: int) -> bytes:
    """Build the experimentally derived remote-start command."""

    remote_tag = encode_string_field(1, "XC_Remote_Tag")
    payload = encode_varint_field(1, 1) + encode_bytes_field(2, remote_tag)
    return _outer_command(34, payload, device_id, sequence)


def build_stop_command(device_id: str, sequence: int, session_id: int) -> bytes:
    """Build the experimentally derived remote-stop command."""

    return _outer_command(36, encode_varint_field(1, session_id), device_id, sequence)


def _outer_command(field_number: int, payload: bytes, device_id: str, sequence: int) -> bytes:
    _validate_device_id(device_id)
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    return (
        encode_bytes_field(field_number, payload)
        + encode_string_field(100, device_id)
        + encode_varint_field(101, sequence)
    )


def _validate_device_id(device_id: str) -> None:
    if len(device_id) != 19 or not device_id.isascii() or not device_id.isdigit():
        raise ValueError("device_id must contain exactly 19 ASCII digits")
