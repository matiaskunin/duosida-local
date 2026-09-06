from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest


@pytest.fixture(scope="session")
def captures() -> dict[str, str]:
    path = Path(__file__).parent / "fixtures" / "captured_messages.json"
    return cast("dict[str, str]", json.loads(path.read_text(encoding="utf-8")))
