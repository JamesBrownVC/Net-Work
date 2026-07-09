"""SQLAlchemy models and idempotent upserts for the unified store (SQLite)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from fabric import schema as S
from fabric.protocol import REPO_ROOT

DB_PATH = REPO_ROOT / "acr.db"


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String, index=True)
    industry: Mapped[str] = mapped_column(String, default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    arr: Mapped[float] = mapped_column(Float, default=0.0)
    renewal_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PersonRow(Base):
    __tablename__ = "people"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    dept: Mapped[str] = mapped_column(String, default="")
    seniority_level: Mapped[str] = mapped_column(String, default="IC")
    email: Mapped[str] = mapped_column(String, index=True)
    phone: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="")
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InteractionRow(Base):
    __tablename__ = "interactions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    company_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, default="outbound")
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    latency_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String, default="")


class DealRow(Base):
    __tablename__ = "deals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, index=True)
    stage: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    products_json: Mapped[str] = mapped_column(Text, default="[]")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SignalRow(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    person_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    ts: Mapped[datetime] = mapped_column(DateTime)
    strength: Mapped[float] = mapped_column(Float, default=0.5)


class OrgEdgeRow(Base):
    __tablename__ = "org_edges"
    src_person: Mapped[str] = mapped_column(String, primary_key=True)
    dst_person: Mapped[str] = mapped_column(String, primary_key=True)
    rel_type: Mapped[str] = mapped_column(String, primary_key=True)
    p_uv: Mapped[float] = mapped_column(Float, default=0.5)
    p_components_json: Mapped[str] = mapped_column(Text, default="{}")


class WarmthRow(Base):
    __tablename__ = "warmth"
    person_id: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    components_json: Mapped[str] = mapped_column(Text, default="{}")
    computed_at: Mapped[datetime] = mapped_column(DateTime)


class TranscriptRow(Base):
    __tablename__ = "transcripts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    call_ts: Mapped[datetime] = mapped_column(DateTime)
    text: Mapped[str] = mapped_column(Text)
    objections_json: Mapped[str] = mapped_column(Text, default="[]")
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)


class ReferenceRow(Base):
    __tablename__ = "references"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_doc: Mapped[str] = mapped_column(String)
    industry: Mapped[str] = mapped_column(String, default="")
    product: Mapped[str] = mapped_column(String, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    metric: Mapped[str] = mapped_column(String, default="")


class IngestStateRow(Base):
    __tablename__ = "ingest_state"
    connector: Mapped[str] = mapped_column(String, primary_key=True)
    last_pull: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rows: Mapped[int] = mapped_column(Integer, default=0)


def get_engine(db_path: Path | None = None) -> Any:
    engine = create_engine(f"sqlite:///{db_path or DB_PATH}", future=True)
    Base.metadata.create_all(engine)
    return engine


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def to_row(entity: S.Entity) -> Base:
    """Map a pydantic entity to its SQLAlchemy row, JSON-encoding dict fields."""
    if isinstance(entity, S.Company):
        return CompanyRow(**entity.model_dump())
    if isinstance(entity, S.Person):
        return PersonRow(**entity.model_dump())
    if isinstance(entity, S.Interaction):
        return InteractionRow(**entity.model_dump())
    if isinstance(entity, S.Deal):
        d = entity.model_dump()
        d["products_json"] = _dump(d["products_json"])
        return DealRow(**d)
    if isinstance(entity, S.Signal):
        d = entity.model_dump()
        d["payload_json"] = _dump(d["payload_json"])
        return SignalRow(**d)
    if isinstance(entity, S.OrgEdge):
        d = entity.model_dump()
        d["p_components_json"] = _dump(d["p_components_json"])
        return OrgEdgeRow(**d)
    if isinstance(entity, S.Warmth):
        d = entity.model_dump()
        d["components_json"] = _dump(d["components_json"])
        return WarmthRow(**d)
    if isinstance(entity, S.Transcript):
        d = entity.model_dump()
        d["objections_json"] = _dump(d["objections_json"])
        return TranscriptRow(**d)
    if isinstance(entity, S.Reference):
        return ReferenceRow(**entity.model_dump())
    raise TypeError(f"unknown entity type: {type(entity)!r}")


def upsert(session: Session, entities: list[S.Entity]) -> int:
    """Idempotent upsert keyed on primary keys. Re-running never duplicates."""
    for entity in entities:
        session.merge(to_row(entity))
    return len(entities)


def table_counts(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        if table.name == "ingest_state":
            continue
        counts[table.name] = session.execute(
            select(func.count()).select_from(table)
        ).scalar_one()
    return counts


def record_ingest(session: Session, connector: str, rows: int, last_pull: datetime) -> None:
    session.merge(IngestStateRow(connector=connector, last_pull=last_pull, rows=rows))
