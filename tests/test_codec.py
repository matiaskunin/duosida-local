from __future__ import annotations

import pytest

from duosida_local.codec import (
    build_handshake_2,
    build_set_max_current,
    build_start_command,
    build_stop_command,
    extract_device_id,
    parse_identity,
    parse_status,
    parse_text_telemetry,
)
from duosida_local.exceptions import DuosidaProtocolError
from duosida_local.models import ChargerState
from duosida_local.protobuf import encode_bytes_field, encode_string_field, encode_varint_field

DEVICE_ID = "0000000000000000000"


def test_identity_and_device_id(captures: dict[str, str]) -> None:
    message = bytes.fromhex(captures["identity"])
    identity = parse_identity(message)
    assert identity is not None
    assert identity.device_id == DEVICE_ID
    assert identity.model == "DUOSIDA Mode3@32A"
    assert identity.manufacturer == "UCHEN"
    assert identity.firmware.startswith("V2.5@")
    assert extract_device_id(message) == DEVICE_ID


@pytest.mark.parametrize(
    ("fixture", "state", "current", "cp", "connected"),
    [
        ("available", ChargerState.AVAILABLE, 0.0, 11.876, False),
        ("charging_6a", ChargerState.CHARGING, 6.8858, 5.872, True),
        ("charging_16a", ChargerState.CHARGING, 14.6133, 5.856, True),
        ("stopped_connected", ChargerState.FINISHED, 0.0, 8.732, True),
    ],
)
def test_status_captures(
    captures: dict[str, str],
    fixture: str,
    state: ChargerState,
    current: float,
    cp: float,
    connected: bool,
) -> None:
    status = parse_status(bytes.fromhex(captures[fixture]))
    assert status is not None
    assert status.state is state
    assert status.current == pytest.approx(current, abs=0.001)
    assert status.cp_voltage == pytest.approx(cp, abs=0.001)
    assert status.vehicle_connected is connected
    assert status.power == pytest.approx(status.voltage * status.current)
    assert status.unknown_fields


def test_text_telemetry(captures: dict[str, str]) -> None:
    telemetry = parse_text_telemetry(bytes.fromhex(captures["text_telemetry"]))
    assert telemetry is not None
    assert telemetry.current == pytest.approx(6.89)
    assert telemetry.energy == pytest.approx(0.02)
    assert telemetry.power == pytest.approx(1546.55)
    assert telemetry.station_temperature == pytest.approx(30.0)
    assert telemetry.voltage == pytest.approx(224.60)


def test_non_matching_messages_return_none(captures: dict[str, str]) -> None:
    identity = bytes.fromhex(captures["identity"])
    assert parse_status(identity) is None
    assert parse_text_telemetry(identity) is None


def test_incomplete_semantic_messages_are_rejected_or_ignored() -> None:
    assert parse_identity(encode_bytes_field(4, b"")) is None
    wrong_wrapper = encode_string_field(2, "Other")
    assert parse_status(encode_bytes_field(16, wrong_wrapper)) is None

    status_without_state = encode_bytes_field(
        16,
        encode_string_field(2, "DataVendorStatusReq") + encode_bytes_field(10, b""),
    )
    with pytest.raises(DuosidaProtocolError, match="connection state"):
        parse_status(status_without_state)

    state_only = encode_varint_field(17, 0)
    status_without_sequence = encode_bytes_field(
        16,
        encode_string_field(2, "DataVendorStatusReq") + encode_bytes_field(10, state_only),
    )
    with pytest.raises(DuosidaProtocolError, match="sequence"):
        parse_status(status_without_sequence)


def test_text_telemetry_partial_and_invalid_values() -> None:
    assert parse_text_telemetry(encode_bytes_field(32, b"")) is None
    records_without_value = encode_bytes_field(2, b"")
    partial = encode_bytes_field(32, encode_bytes_field(3, records_without_value))
    assert parse_text_telemetry(partial) is None
    invalid_record = encode_bytes_field(2, encode_string_field(1, "not-a-number"))
    invalid = encode_bytes_field(32, encode_bytes_field(3, invalid_record))
    with pytest.raises(DuosidaProtocolError, match="non-numeric"):
        parse_text_telemetry(invalid)


def test_handshake_uses_runtime_identifier() -> None:
    assert build_handshake_2(DEVICE_ID).hex() == (
        "1a0a089ee6da910d10001800a2061330303030303030303030303030303030303030a8069e818040"
    )


def test_exact_command_bytes() -> None:
    assert build_set_max_current(DEVICE_ID, 1, 16).hex() == (
        "521d0a1456656e646f724d6178576f726b43757272656e74120531362e3030"
        "a2061330303030303030303030303030303030303030a80601"
    )
    assert build_start_command(DEVICE_ID, 1).hex() == (
        "9202130801120f0a0d58435f52656d6f74655f546167"
        "a2061330303030303030303030303030303030303030a80601"
    )
    assert build_stop_command(DEVICE_ID, 1, 7).hex() == (
        "a202020807a2061330303030303030303030303030303030303030a80601"
    )


@pytest.mark.parametrize("amps", [5, 33])
def test_current_limits(amps: int) -> None:
    with pytest.raises(ValueError, match="between 6 and 32"):
        build_set_max_current(DEVICE_ID, 1, amps)


@pytest.mark.parametrize("device_id", ["", "123", "x" * 19, "1" * 20])
def test_identifier_validation(device_id: str) -> None:
    with pytest.raises(ValueError, match="19 ASCII digits"):
        build_handshake_2(device_id)


def test_negative_sequence_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_stop_command(DEVICE_ID, -1, 1)


def test_cp_voltage_takes_precedence_over_stale_state_code(
    captures: dict[str, str],
) -> None:
    message = bytes.fromhex(captures["stopped_connected"])
    disconnected_cp = message.replace(bytes.fromhex("4d46b60b41"), bytes.fromhex("4d00004041"))
    status = parse_status(disconnected_cp)
    assert status is not None
    assert status.state is ChargerState.FINISHED
    assert status.cp_voltage == pytest.approx(12.0)
    assert not status.vehicle_connected
