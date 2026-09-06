# Local protocol notes

This document describes observations, not an official vendor specification.

## Confidence labels

- **Verified:** repeated physical captures agree with the interpretation.
- **Corroborated:** documentation or another implementation agrees, but this
  project has not completed the physical command matrix.
- **Hypothesis:** useful for an alpha experiment and clearly isolated.
- **Unknown:** preserved without a public semantic name.

## Transport and session

| Item | Value | Confidence |
|---|---:|---|
| Charger TCP port | 9988 | Verified |
| Discovery listener/source | UDP 48890 | Corroborated |
| Discovery destination | UDP 48899 | Corroborated |
| Discovery payload | `smart_chargepile_search\0` | Corroborated |
| First handshake | `a2030408001000a20603494f53a80600` | Verified |
| Identifier | outer Protobuf field 100, 19 ASCII digits | Verified |
| Sequence | outer Protobuf field 101, varint | Verified |

TCP is a stream. A socket read may contain part of a message or several
messages. Captured outer messages end with field 100 (the 19-digit identifier)
and field 101 (sequence). `MessageFramer` uses this observed terminator and
enforces a bounded buffer. It is not claimed to be an official length rule.

## Identity

Outer field 4 contains model, identifier, manufacturer and firmware in nested
fields 2 through 5. The captured device announces `DUOSIDA Mode3@32A`, `UCHEN`
and its firmware string.

## Status

Outer field 16 wraps domain `smartchargepile.x-cheng.com`, message type
`DataVendorStatusReq` and its payload in wrapper field 10.

| Payload field | Meaning | Confidence |
|---:|---|---|
| 1 | Voltage (V) | Verified |
| 2 | Current (A) | Verified |
| 3 | Total accumulated energy (kWh) | Verified |
| 4 | Session energy (kWh) | Verified |
| 8 | Station temperature (°C) | Verified |
| 9 | Control Pilot voltage (V) | Verified |
| 17 | Connection state code | Verified for 0, 2 and 5 |

Power is computed from voltage × current. Outer field 32 also carries numeric
text telemetry in the order current, energy, power, station temperature and
voltage; its direct power value supersedes the computed snapshot when present.

Verified state codes are 0 Available, 2 Charging and 5 Finished/connected but
stopped. Codes 1 Preparing, 3 Cooling, 4 SuspendedEV and 6 Holiday are retained
as referenced but not physically verified.

## Commands

- Maximum current: outer field 10 with strings `VendorMaxWorkCurrent` and the
  requested 6–32 A value. Write-only; receipt is `SENT_UNCONFIRMED`.
- Start: outer field 34 containing `XC_Remote_Tag`. Confirmation requires an
  observed Charging state.
- Stop: outer field 36 containing a session value. Confirmation requires an
  observed non-Charging state.

These command encodings are clean-room hypotheses derived from public behavior
and independent protocol analysis. Their bytes are covered by regression tests,
but physical support stays experimental until the compatibility matrix passes.
