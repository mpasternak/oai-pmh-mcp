"""Wspólne narzędzia testowe: ładowanie nagranych fixture'ów XML."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> bytes:
    """Zwraca surowe bajty pliku fixture (parser pracuje na bajtach)."""
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def fixture():
    return load_fixture
