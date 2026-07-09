from __future__ import annotations

import json

from fabric.connectors.mockcrm import MockCRMConnector
from fabric.protocol import Status
from fabric.schema import Company, Deal
from scripts.seed import generate_accounts


def _connector_with_fixture(tmp_path):
    accounts = generate_accounts()
    fixture_path = tmp_path / "accounts.json"
    fixture_path.write_text(json.dumps(accounts), encoding="utf-8")
    return MockCRMConnector(fixture_path=fixture_path), accounts


def test_health_is_mock_when_fixture_present(tmp_path):
    connector, _ = _connector_with_fixture(tmp_path)
    assert connector.health() == Status.MOCK


def test_health_is_red_when_fixture_missing(tmp_path):
    connector = MockCRMConnector(fixture_path=tmp_path / "missing.json")
    assert connector.health() == Status.RED


def test_pull_returns_one_record_per_account(tmp_path):
    connector, accounts = _connector_with_fixture(tmp_path)
    records = connector.pull()
    assert len(records) == len(accounts) == 25


def test_pull_is_deterministic(tmp_path):
    connector, _ = _connector_with_fixture(tmp_path)
    first = connector.pull()
    second = connector.pull()
    assert [r.payload for r in first] == [r.payload for r in second]


def test_normalize_produces_schema_valid_company_and_deal(tmp_path):
    connector, _ = _connector_with_fixture(tmp_path)
    records = connector.pull()

    for raw in records:
        entities = connector.normalize(raw)
        assert len(entities) == 2

        company = next(e for e in entities if isinstance(e, Company))
        deal = next(e for e in entities if isinstance(e, Deal))

        assert 8_000 <= company.arr <= 400_000
        assert company.is_customer is True
        assert deal.company_id == company.id
        assert deal.amount > 0
        assert len(deal.products_json) >= 1


def test_normalize_is_idempotent(tmp_path):
    connector, _ = _connector_with_fixture(tmp_path)
    raw = connector.pull()[0]

    first = connector.normalize(raw)
    second = connector.normalize(raw)

    assert [e.model_dump() for e in first] == [e.model_dump() for e in second]
