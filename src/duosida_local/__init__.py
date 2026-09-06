"""Local-only asynchronous API for verified Duosida EV chargers."""

from .client import DuosidaClient as DuosidaClient, StateCallback as StateCallback
from .discovery import discover_chargers as discover_chargers
from .exceptions import (
    DuosidaCommandError as DuosidaCommandError,
    DuosidaCommandUnconfirmedError as DuosidaCommandUnconfirmedError,
    DuosidaConnectionError as DuosidaConnectionError,
    DuosidaError as DuosidaError,
    DuosidaProtocolError as DuosidaProtocolError,
)
from .models import (
    ChargerIdentity as ChargerIdentity,
    ChargerState as ChargerState,
    ChargerStatus as ChargerStatus,
    CommandReceipt as CommandReceipt,
    CommandStatus as CommandStatus,
    DiscoveredCharger as DiscoveredCharger,
)

__all__ = [
    "ChargerIdentity",
    "ChargerState",
    "ChargerStatus",
    "CommandReceipt",
    "CommandStatus",
    "DiscoveredCharger",
    "DuosidaClient",
    "DuosidaCommandError",
    "DuosidaCommandUnconfirmedError",
    "DuosidaConnectionError",
    "DuosidaError",
    "DuosidaProtocolError",
    "StateCallback",
    "discover_chargers",
]

__version__ = "0.1.0a1"
