from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from evalkit.storage import SQLiteRepository

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "scenarios" / "examples" / "demo"


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[SQLiteRepository]:
    r = SQLiteRepository(tmp_path / "data")
    r.migrate()
    yield r
    r.close()


@pytest.fixture
def demo_dir() -> Path:
    return DEMO
