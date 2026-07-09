"""The one protocol every ACR connector implements.

Direct Python calls and MCP calls (added in a later phase) hit this same
interface, so a connector written today does not change shape when it grows
an MCP wrapper.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from fabric.schema import Entity


class Status(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    MOCK = "MOCK"


class RawRecord(BaseModel):
    """One unnormalized record as returned by a connector's pull()."""

    model_config = ConfigDict(frozen=True)

    source: str
    source_id: str
    payload: dict[str, Any]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class Connector(Protocol):
    name: str

    def health(self) -> Status: ...

    def pull(self, since: datetime | None = None) -> list[RawRecord]: ...

    def normalize(self, raw: RawRecord) -> list[Entity]: ...
