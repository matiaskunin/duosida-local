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

## Continuous integration

CI runs on pushes to `main`, version tags (`v*`), pull requests and manual
dispatches. Feature-branch pushes do not start an additional run alongside the
pull request. A newer run cancels an older run for the same pull request or ref.

Style and type checks run once on Python 3.14. Tests run independently on Python
3.11–3.14, and a separate build job produces wheel and source artifacts.
Dependabot uses the `uv` ecosystem to update Python dependencies and `uv.lock`
together. Keep `uv sync --locked` in CI so stale lockfiles fail visibly.

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
