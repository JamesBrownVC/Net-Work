"""Connector protocol shared by every source. One protocol, no exceptions."""

from __future__ import annotations

import enum
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from fabric.schema import Entity

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"


class Status(enum.StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    MOCK = "MOCK"


class RawRecord(BaseModel):
    """One record straight from a source, before normalization."""

    source: str
    kind: str
    payload: dict[str, Any]


def mock_mode() -> bool:
    """MOCK_MODE defaults to true; live is per-connector opt-in."""
    return os.getenv("MOCK_MODE", "true").strip().lower() != "false"


@runtime_checkable
class Connector(Protocol):
    name: str

    def health(self) -> Status: ...

    def pull(self, since: datetime | None) -> list[RawRecord]: ...

    def normalize(self, raw: RawRecord) -> list[Entity]: ...
