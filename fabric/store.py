"""The unified store. One SQLite database, one schema, every connector writes here.

Upserts are keyed on each entity's natural key (not its possibly-absent id),
so re-running ingest never duplicates rows. IDs are derived deterministically
from the natural key with uuid5 when a connector does not supply one, which
keeps foreign keys stable across repeated ingests.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, JSON, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from fabric.schema import Company, Deal, Entity, Interaction, OrgEdge, Person, Reference, Signal, Transcript

_ID_NAMESPACE = uuid.UUID("6a2f7e2e-6b0a-4f2e-9d3a-8f2c1a9b0e11")


def _deterministic_id(*parts: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, "|".join(parts)))


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String, unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    size: Mapped[str | None] = mapped_column(String, nullable=True)
    is_customer: Mapped[bool] = mapped_column(default=False)
    arr: Mapped[float | None] = mapped_column(Float, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class PersonRow(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    full_name: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    dept: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InteractionRow(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    latency_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class DealRow(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)
    stage: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    products_json: Mapped[list] = mapped_column(JSON, default=list)
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class SignalRow(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    strength: Mapped[float] = mapped_column(Float)


class OrgEdgeRow(Base):
    __tablename__ = "org_edges"

    src_person: Mapped[str] = mapped_column(ForeignKey("people.id"), primary_key=True)
    dst_person: Mapped[str] = mapped_column(ForeignKey("people.id"), primary_key=True)
    rel_type: Mapped[str] = mapped_column(String, primary_key=True)
    p_uv: Mapped[float] = mapped_column(Float)
    p_components_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WarmthRow(Base):
    """Table exists from Phase 1; populated by the Phase 2 warmth engine."""

    __tablename__ = "warmth"

    person_id: Mapped[str] = mapped_column(ForeignKey("people.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    components_json: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime)


class TranscriptRow(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    call_ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    text: Mapped[str] = mapped_column(String)
    objections_json: Mapped[list] = mapped_column(JSON, default=list)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)


class ReferenceRow(Base):
    __tablename__ = "references"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_doc: Mapped[str] = mapped_column(String, unique=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    product: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    quote: Mapped[str | None] = mapped_column(String, nullable=True)
    metric: Mapped[str | None] = mapped_column(String, nullable=True)


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.environ.get("DATABASE_URL", "sqlite:///acr.db")
    return create_engine(url)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_company(session: Session, company: Company) -> CompanyRow:
    row = session.query(CompanyRow).filter_by(domain=company.domain).one_or_none()
    if row is None:
        row = CompanyRow(id=company.id or _deterministic_id("company", company.domain))
        session.add(row)
    row.name = company.name
    row.domain = company.domain
    row.industry = company.industry
    row.size = company.size
    row.is_customer = company.is_customer
    row.arr = company.arr
    row.renewal_date = company.renewal_date
    session.flush()
    return row


def upsert_person(session: Session, person: Person) -> PersonRow:
    natural_key = person.email or f"{person.company_id}:{person.full_name}"
    query = session.query(PersonRow).filter_by(company_id=person.company_id)
    row = (
        query.filter_by(email=person.email).one_or_none()
        if person.email
        else query.filter_by(full_name=person.full_name).one_or_none()
    )
    if row is None:
        row = PersonRow(id=person.id or _deterministic_id("person", natural_key))
        session.add(row)
    row.company_id = person.company_id
    row.full_name = person.full_name
    row.title = person.title
    row.dept = person.dept
    row.seniority_level = person.seniority_level.value if person.seniority_level else None
    row.email = person.email
    row.phone = person.phone
    row.source = person.source
    row.enriched_at = person.enriched_at
    session.flush()
    return row


def upsert_interaction(session: Session, interaction: Interaction) -> InteractionRow:
    natural_key = interaction.source_ref or f"{interaction.company_id}:{interaction.kind.value}:{interaction.ts.isoformat()}"
    row = (
        session.query(InteractionRow).filter_by(source_ref=interaction.source_ref).one_or_none()
        if interaction.source_ref
        else session.query(InteractionRow)
        .filter_by(company_id=interaction.company_id, kind=interaction.kind.value, ts=interaction.ts)
        .one_or_none()
    )
    if row is None:
        row = InteractionRow(id=interaction.id or _deterministic_id("interaction", natural_key))
        session.add(row)
    row.person_id = interaction.person_id
    row.company_id = interaction.company_id
    row.kind = interaction.kind.value
    row.direction = interaction.direction.value if interaction.direction else None
    row.ts = interaction.ts
    row.latency_hours = interaction.latency_hours
    row.sentiment = interaction.sentiment
    row.summary = interaction.summary
    row.source_ref = interaction.source_ref
    session.flush()
    return row


def upsert_deal(session: Session, deal: Deal) -> DealRow:
    """One active deal row per company; the mock CRM fixture is a current-state snapshot."""
    row = session.query(DealRow).filter_by(company_id=deal.company_id).one_or_none()
    if row is None:
        row = DealRow(id=deal.id or _deterministic_id("deal", deal.company_id))
        session.add(row)
    row.company_id = deal.company_id
    row.stage = deal.stage
    row.amount = deal.amount
    row.products_json = deal.products_json
    row.opened_at = deal.opened_at
    row.closed_at = deal.closed_at
    session.flush()
    return row


def upsert_signal(session: Session, signal: Signal) -> SignalRow:
    natural_key = f"{signal.company_id}:{signal.source}:{signal.kind}:{signal.ts.isoformat()}"
    row = (
        session.query(SignalRow)
        .filter_by(company_id=signal.company_id, source=signal.source, kind=signal.kind, ts=signal.ts)
        .one_or_none()
    )
    if row is None:
        row = SignalRow(id=signal.id or _deterministic_id("signal", natural_key))
        session.add(row)
    row.company_id = signal.company_id
    row.person_id = signal.person_id
    row.source = signal.source
    row.kind = signal.kind
    row.payload_json = signal.payload_json
    row.ts = signal.ts
    row.strength = signal.strength
    session.flush()
    return row


def upsert_org_edge(session: Session, edge: OrgEdge) -> OrgEdgeRow:
    row = (
        session.query(OrgEdgeRow)
        .filter_by(src_person=edge.src_person, dst_person=edge.dst_person, rel_type=edge.rel_type.value)
        .one_or_none()
    )
    if row is None:
        row = OrgEdgeRow(src_person=edge.src_person, dst_person=edge.dst_person, rel_type=edge.rel_type.value)
        session.add(row)
    row.p_uv = edge.p_uv
    row.p_components_json = edge.p_components_json
    session.flush()
    return row


def upsert_transcript(session: Session, transcript: Transcript) -> TranscriptRow:
    row = (
        session.query(TranscriptRow)
        .filter_by(company_id=transcript.company_id, call_ts=transcript.call_ts)
        .one_or_none()
    )
    if row is None:
        row = TranscriptRow(
            id=transcript.id or _deterministic_id("transcript", transcript.company_id, transcript.call_ts.isoformat())
        )
        session.add(row)
    row.company_id = transcript.company_id
    row.call_ts = transcript.call_ts
    row.text = transcript.text
    row.objections_json = transcript.objections_json
    row.sentiment = transcript.sentiment
    session.flush()
    return row


def upsert_reference(session: Session, reference: Reference) -> ReferenceRow:
    row = session.query(ReferenceRow).filter_by(source_doc=reference.source_doc).one_or_none()
    if row is None:
        row = ReferenceRow(id=reference.id or _deterministic_id("reference", reference.source_doc))
        session.add(row)
    row.source_doc = reference.source_doc
    row.industry = reference.industry
    row.product = reference.product
    row.outcome = reference.outcome
    row.quote = reference.quote
    row.metric = reference.metric
    session.flush()
    return row


_UPSERT_DISPATCH = {
    Company: upsert_company,
    Person: upsert_person,
    Interaction: upsert_interaction,
    Deal: upsert_deal,
    Signal: upsert_signal,
    OrgEdge: upsert_org_edge,
    Transcript: upsert_transcript,
    Reference: upsert_reference,
}


def upsert_entity(session: Session, entity: Entity) -> object:
    handler = _UPSERT_DISPATCH.get(type(entity))
    if handler is None:
        raise TypeError(f"No upsert handler registered for entity type {type(entity)!r}")
    return handler(session, entity)
