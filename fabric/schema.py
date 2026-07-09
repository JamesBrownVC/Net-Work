"""Pydantic entities produced by every connector's normalize().

These are the typed, validated shapes that sit between a connector's raw
payload and the unified store. A connector is only "done" once it can turn
its fixtures into a list of these without validation errors.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field


class InteractionKind(str, Enum):
    EMAIL = "email"
    MEETING = "meeting"
    CALL = "call"
    SLACK = "slack"
    NOTE = "note"


class SeniorityLevel(str, Enum):
    IC = "IC"
    MGR = "MGR"
    DIR = "DIR"
    VP = "VP"
    C = "C"


class OrgEdgeType(str, Enum):
    MANAGES = "manages"
    PEER = "peer"
    SKIP = "skip"
    CROSS_DEPT = "cross_dept"
    EXTERNAL_MUTUAL = "external_mutual"


class Direction(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EntityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Company(EntityBase):
    id: str | None = None
    name: str
    domain: str
    industry: str | None = None
    size: str | None = None
    is_customer: bool = False
    arr: float | None = None
    renewal_date: date | None = None


class Person(EntityBase):
    id: str | None = None
    company_id: str
    full_name: str
    title: str | None = None
    dept: str | None = None
    seniority_level: SeniorityLevel | None = None
    email: str | None = None
    phone: str | None = None
    source: str
    enriched_at: datetime | None = None


class Interaction(EntityBase):
    id: str | None = None
    person_id: str | None = None
    company_id: str
    kind: InteractionKind
    direction: Direction | None = None
    ts: datetime
    latency_hours: float | None = None
    sentiment: float | None = None
    summary: str | None = None
    source_ref: str | None = None


class Deal(EntityBase):
    id: str | None = None
    company_id: str
    stage: str
    amount: float
    products_json: list[str] = Field(default_factory=list)
    opened_at: date | None = None
    closed_at: date | None = None


class Signal(EntityBase):
    id: str | None = None
    company_id: str
    person_id: str | None = None
    source: str
    kind: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    ts: datetime
    strength: float = Field(ge=0.0, le=1.0)


class OrgEdge(EntityBase):
    src_person: str
    dst_person: str
    rel_type: OrgEdgeType
    p_uv: float = Field(ge=0.0, le=1.0)
    p_components_json: dict[str, Any] = Field(default_factory=dict)


class Transcript(EntityBase):
    id: str | None = None
    company_id: str
    call_ts: datetime
    text: str
    objections_json: list[str] = Field(default_factory=list)
    sentiment: float | None = None


class Reference(EntityBase):
    id: str | None = None
    source_doc: str
    industry: str | None = None
    product: str | None = None
    outcome: str | None = None
    quote: str | None = None
    metric: str | None = None


Entity = Union[Company, Person, Interaction, Deal, Signal, OrgEdge, Transcript, Reference]
