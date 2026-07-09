from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_world() -> None:
    seed.main()


def contract_check(name: str) -> None:
    """Shared contract: pull returns RawRecords, normalize yields schema-valid
    entities, and mock health is MOCK."""
    from pydantic import BaseModel

    from fabric import registry
    from fabric.protocol import RawRecord, Status

    connector = registry.get(name)
    assert connector.health() == Status.MOCK
    records = connector.pull(since=None)
    assert records, f"{name}: fixture pull returned nothing"
    for raw in records:
        assert isinstance(raw, RawRecord)
    total = 0
    for raw in records:
        for entity in connector.normalize(raw):
            assert isinstance(entity, BaseModel)
            total += 1
    assert total > 0
