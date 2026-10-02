import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.load import list_matches  # noqa: E402

MATCHES = list_matches()
SC_MATCHES = [m for m in MATCHES if not m.startswith("metrica_")]
ME_MATCHES = [m for m in MATCHES if m.startswith("metrica_")]


def pytest_configure(config):
    if not MATCHES:
        raise pytest.UsageError("data/processed is empty - run `python -m src.build` first")
