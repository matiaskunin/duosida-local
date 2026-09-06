# Architecture

The package follows a small layered design:

```text
DuosidaClient
  -> commands and immutable models
  -> semantic codec
  -> schema-less Protobuf primitives
  -> incremental message framer
  -> asyncio TCP transport

discover_chargers -> asyncio UDP -> short TCP identification
```

The transport owns sockets but knows no entity semantics. The framer has one
responsibility: turn arbitrary TCP chunks into complete observed messages. The
codec maps only verified fields and retains other scalar fields as `RawField`.
The client serializes commands, publishes snapshots and applies confirmation
rules. No layer imports Home Assistant.

This separation keeps reverse-engineering uncertainty at the boundary. If a
formal framing specification or `.proto` becomes available, the corresponding
layer can be replaced without changing the public models.

## Design decisions

- **Async first:** Home Assistant must not block its event loop.
- **Immutable snapshots:** consumers cannot accidentally mutate shared state.
- **One reader task:** no competing reads from the same TCP stream.
- **Serialized writes:** a lock protects sequence assignment and commands.
- **Push updates:** status frames drive consumers; no unnecessary polling.
- **Typed failure modes:** connection, protocol and command failures remain
  distinguishable.
- **No speculative properties:** unknown fields are retained but unnamed.
