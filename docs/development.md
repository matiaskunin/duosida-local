# Development and release process

## Local checks

```bash
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run python -m build
```

`prek run --all-files` runs the repository hooks. Tests must not contact a real
charger unless explicitly marked as a manual hardware test.

## Versioning

Library and Home Assistant integration alphas advance together:

1. Build and test `duosida-local 0.1.0aN`.
2. With GitHub release immutability enabled, publish a new GitHub release with
   the `v0.1.0aN` tag.
3. Pin that exact Git tag in the integration manifest.
4. Release the matching integration `0.1.0aN`.

The library remains GitHub-only during physical validation. Publishing it to
PyPI is a later release decision, after the supported features are repeatable
on real hardware.

Stable `0.1.0` requires the complete SES-32-ORW physical matrix. A release must
not convert a hypothesis into a supported claim merely because CI passes.

## Sanitizing captures

Replace the 19-digit device identifier with a 19-digit placeholder and redact
MAC, IP and serial values. Preserve byte lengths so framing tests remain valid.
Never commit the original photographs or raw unsanitized captures.
