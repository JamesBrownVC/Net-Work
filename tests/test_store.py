from __future__ import annotations

from datetime import date

from fabric.schema import Company, Deal
from fabric.store import (
    CompanyRow,
    DealRow,
    get_engine,
    init_db,
    session_scope,
    upsert_company,
    upsert_deal,
    upsert_entity,
)


def _engine(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    return engine


def test_upsert_company_is_idempotent_and_updates_fields(tmp_path):
    engine = _engine(tmp_path)
    company = Company(
        name="Acme",
        domain="acme.io",
        industry="Fintech",
        is_customer=True,
        arr=100_000,
        renewal_date=date(2026, 6, 1),
    )

    with session_scope(engine) as session:
        upsert_company(session, company)
    with session_scope(engine) as session:
        upsert_company(session, company.model_copy(update={"arr": 150_000, "name": "Acme Inc"}))

    with session_scope(engine) as session:
        rows = session.query(CompanyRow).all()
        assert len(rows) == 1
        assert rows[0].arr == 150_000
        assert rows[0].name == "Acme Inc"
        assert rows[0].domain == "acme.io"


def test_upsert_deal_is_idempotent_per_company(tmp_path):
    engine = _engine(tmp_path)
    company = Company(name="Acme", domain="acme.io", is_customer=True, arr=100_000)
    deal = Deal(
        company_id="acct-acme",
        stage="closed_won",
        amount=100_000,
        products_json=["Expense Management"],
        opened_at=date(2025, 1, 1),
        closed_at=date(2025, 1, 20),
    )

    with session_scope(engine) as session:
        upsert_company(session, company.model_copy(update={"id": "acct-acme"}))
        upsert_deal(session, deal)
    with session_scope(engine) as session:
        upsert_deal(session, deal.model_copy(update={"stage": "renewal_pending"}))

    with session_scope(engine) as session:
        rows = session.query(DealRow).all()
        assert len(rows) == 1
        assert rows[0].stage == "renewal_pending"
        assert rows[0].company_id == "acct-acme"


def test_upsert_entity_dispatches_by_type(tmp_path):
    engine = _engine(tmp_path)
    company = Company(id="acct-acme", name="Acme", domain="acme.io", is_customer=True, arr=50_000)

    with session_scope(engine) as session:
        row = upsert_entity(session, company)
        assert isinstance(row, CompanyRow)

    with session_scope(engine) as session:
        rows = session.query(CompanyRow).all()
        assert len(rows) == 1
