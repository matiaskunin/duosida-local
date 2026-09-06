# duosida-local

[![CI](https://github.com/matiaskunin/duosida-local/actions/workflows/ci.yml/badge.svg)](https://github.com/matiaskunin/duosida-local/actions/workflows/ci.yml)
[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)

An asynchronous, typed Python client that communicates directly with supported
Duosida EV chargers over the local network. It does not call DSCharge or any
cloud service.

> **Alpha software:** passive telemetry is backed by physical captures from one
> SES-32-ORW. Remote start, stop, current setting and UDP discovery still need
> repeatable physical validation before they can be declared stable.

Spanish documentation: [Guía en español](docs/es/README.md).

## Verified hardware

| Model | Electrical rating | Telemetry | Control | Verification |
|---|---|---:|---:|---|
| DUOSIDA SES-32-ORW | 230 V, 32 A, 7.2 kW, single phase | Captured | Experimental | One physical unit |

Other Duosida models are **not verified**. See [compatibility](docs/compatibility.md).

## Install

During physical validation, alpha releases are installed directly from an
immutable GitHub tag and are not published to PyPI:

```bash
python -m pip install "duosida-local@git+https://github.com/matiaskunin/duosida-local.git@v0.1.0a1"
```

For development:

```bash
uv sync --locked --all-groups
uv run pytest
```

## Usage

```python
import asyncio

from duosida_local import DuosidaClient


async def main() -> None:
    async with DuosidaClient("192.168.1.50") as charger:
        identity = await charger.get_identity()
        print(identity)

        async for status in charger.states():
            print(status.state, status.voltage, status.current)


asyncio.run(main())
```

Discovery broadcasts on UDP 48899 and listens on UDP 48890:

```python
from duosida_local import discover_chargers

chargers = await discover_chargers()
```

The persistent charger connection uses TCP 9988. Start and stop only return a
receipt after a compatible state transition is observed. `set_max_current()`
returns `SENT_UNCONFIRMED`: the current protocol evidence does not expose the
stored configuration value.

## Safety and privacy

- Operate only chargers you own or administer.
- Begin physical current tests at 6 A and stay within the installation rating.
- Put the charger on a trusted or isolated LAN; the protocol is not encrypted.
- Do not publish captures until device IDs, MAC addresses, IP addresses and
  serial numbers have been sanitized.
- This project is not affiliated with Duosida, Uchen or DSCharge.

## Documentation

- [Architecture](docs/architecture.md)
- [Protocol and confidence levels](docs/protocol.md)
- [Compatibility matrix](docs/compatibility.md)
- [Development and releases](docs/development.md)
- [Sources and attribution](docs/sources.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)

## License

Copyright (C) 2026 Matias Kunin. Licensed under `GPL-3.0-only`.
