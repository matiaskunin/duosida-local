"""Immutable public models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

Scalar: TypeAlias = int | float | bytes | str


class ChargerState(str, Enum):
    """Known charger states.

    Only AVAILABLE, CHARGING and FINISHED have been physically verified on the
    SES-32-ORW. The remaining named values come from a compatible app protocol
    and remain marked as unverified in the project documentation.
    """

    AVAILABLE = "available"
    PREPARING = "preparing"
    CHARGING = "charging"
    COOLING = "cooling"
    SUSPENDED_EV = "suspended_ev"
    FINISHED = "finished"
    HOLIDAY = "holiday"
    UNKNOWN = "unknown"


class CommandStatus(str, Enum):
    """Level of confirmation available for a command."""

    CONFIRMED = "confirmed"
    SENT_UNCONFIRMED = "sent_unconfirmed"


@dataclass(frozen=True, slots=True)
class RawField:
    """An intentionally unnamed protocol value."""

    number: int
    wire_type: int
    value: Scalar


@dataclass(frozen=True, slots=True)
class ChargerIdentity:
    """Identity announced by a charger."""

    device_id: str
    model: str
    manufacturer: str
    firmware: str


@dataclass(frozen=True, slots=True)
class ChargerStatus:
    """Latest decoded charger measurements."""

    state: ChargerState
    raw_state: int
    voltage: float
    current: float
    power: float
    total_energy: float
    session_energy: float
    station_temperature: float
    cp_voltage: float
    vehicle_connected: bool
    sequence: int
    unknown_fields: tuple[RawField, ...] = ()

    @property
    def charging(self) -> bool:
        """Return whether the charger reports active charging."""

        return self.state is ChargerState.CHARGING


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """Result of a command transmission."""

    command: str
    status: CommandStatus
    sequence: int
    requested_value: int | None = None
    observed_state: ChargerState | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredCharger:
    """A charger discovered on the local network."""

    host: str
    port: int = 9988
    device_id: str | None = None
    mac: str | None = None
    firmware: str | None = None
    raw_response: str | None = None
