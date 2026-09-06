"""Public exception hierarchy for :mod:`duosida_local`."""


class DuosidaError(Exception):
    """Base exception for the library."""


class DuosidaConnectionError(DuosidaError):
    """The charger could not be reached or the connection was lost."""


class DuosidaProtocolError(DuosidaError):
    """The charger sent data that does not match the observed protocol."""


class DuosidaCommandError(DuosidaError):
    """A command could not be encoded or sent."""


class DuosidaCommandUnconfirmedError(DuosidaCommandError):
    """A command was sent but no compatible state transition was observed."""
