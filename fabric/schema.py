"""Pydantic entities for the unified data model.

Every derived or probabilistic field travels with a components sibling so no
naked score ever reaches the store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

InteractionKind = Literal["email", "meeting", "call", "slack", "note"]
SeniorityLevel = Literal["IC", "MGR", "DIR", "VP", "C"]
RelType = Literal["manages", "peer", "skip", "cross_dept", "external_mutual"]


class Company(BaseModel):
    id: str
    name: str
    domain: str
    industry: str = ""
    size: int = 0
    is_customer: bool = False
    arr: float = 0.0
    renewal_date: datetime | None = None


class Person(BaseModel):
    id: str
    company_id: str | None = None
    full_name: str
    title: str = ""
    dept: str = ""
    seniority_level: SeniorityLevel = "IC"
    email: str
    phone: str = ""
    source: str = ""
    enriched_at: datetime | None = None


class Interaction(BaseModel):
    id: str
    person_id: str | None = None
    company_id: str | None = None
    kind: InteractionKind
    direction: Literal["inbound", "outbound", "internal"] = "outbound"
    ts: datetime
    latency_hours: float | None = None
    sentiment: float | None = None
    summary: str = ""
    source_ref: str = ""


class Deal(BaseModel):
    id: str
    company_id: str
    stage: str
    amount: float = 0.0
    products_json: list[str] = Field(default_factory=list)
    opened_at: datetime | None = None
    closed_at: datetime | None = None


class Signal(BaseModel):
    id: str
    company_id: str | None = None
    person_id: str | None = None
    source: str
    kind: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    ts: datetime
    strength: float = 0.5


class OrgEdge(BaseModel):
    src_person: str
    dst_person: str
    rel_type: RelType
    p_uv: float = 0.5
    p_components_json: dict[str, Any] = Field(default_factory=dict)


class Warmth(BaseModel):
    person_id: str
    score: float
    components_json: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime


class Transcript(BaseModel):
    id: str
    company_id: str | None = None
    call_ts: datetime
    text: str
    objections_json: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: float | None = None


class Reference(BaseModel):
    id: str
    source_doc: str
    industry: str = ""
    product: str = ""
    outcome: str = ""
    quote: str = ""
    metric: str = ""


Entity = (
    Company | Person | Interaction | Deal | Signal | OrgEdge | Warmth | Transcript | Reference
)


def person_id(email: str) -> str:
    return f"person:{email.lower()}"


def company_id(domain: str) -> str:
    return f"company:{domain.lower()}"
