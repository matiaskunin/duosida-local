# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Keep alpha distribution on GitHub only until physical validation is complete.
- Retry UDP discovery, preserve the fixed reply port and prefer the charger-advertised IP.
- Derive vehicle connection from measured Control Pilot voltage.
- Format the maximum-current setting with two decimals for the next physical test.
- Clarify that the energy value is the charger's local register, not DSCharge cloud history.

## [0.1.0a1] - 2026-09-01

### Added

- Async TCP client, runtime identifier handshake and incremental framing.
- Schema-less Protobuf codec for verified identity and telemetry fields.
- UDP discovery and optional TCP identification.
- Serialized start, stop and 6–32 A maximum-current commands.
- Typed immutable models, public exceptions and state stream.
- Sanitized capture-derived fixtures and 95% minimum test coverage.

[Unreleased]: https://github.com/matiaskunin/duosida-local/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/matiaskunin/duosida-local/releases/tag/v0.1.0a1
